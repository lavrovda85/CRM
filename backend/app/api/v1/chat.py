"""Company-wide chat REST API.

Provides:
- sending messages
- fetching message history (with polling-friendly "after" filter)
"""

from __future__ import annotations

import uuid
from datetime import datetime

import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fastapi import APIRouter, Depends, File, Query, UploadFile
from app.core.config import Settings, get_settings
from app.core.dependencies import PaginationParams, get_current_user, get_db
from app.core.exceptions import ValidationError, NotFoundError
from app.core.pagination import PaginatedResponse
from app.core.security import CurrentUser
from app.models import ChatAttachment, ChatMessage, ChatRoom, User
from app.services.user_identity import resolve_users_table_id
from app.schemas.chat import (
    ChatAttachmentResponse,
    ChatMessageCreate,
    ChatMessageResponse,
    ChatRoomCreate,
    ChatRoomResponse,
)

router = APIRouter(prefix="/chat")

logger = logging.getLogger(__name__)


PRESIGNED_URL_EXPIRY_SECONDS = 3600


def _slugify_room_code(name: str) -> str:
    """Convert a room name into a safe internal code."""
    n = name.strip().lower()
    n = "".join(ch if ch.isalnum() else "-" for ch in n)
    while "--" in n:
        n = n.replace("--", "-")
    return n.strip("-") or "company"


@router.get("/rooms", response_model=list[ChatRoomResponse])
async def list_rooms(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[ChatRoomResponse]:
    """List available chat rooms (direction groups)."""
    _ = user.sub
    res = await db.execute(select(ChatRoom).order_by(ChatRoom.created_at.asc()))
    rooms = res.scalars().all()

    if not rooms:
        # Ensure default room exists for backward compatibility.
        default = ChatRoom(name="Общий чат", code="company")
        db.add(default)
        await db.flush()
        rooms = [default]

    return [ChatRoomResponse.model_validate(r) for r in rooms]


@router.post("/rooms", response_model=ChatRoomResponse, status_code=201)
async def create_room(
    body: ChatRoomCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> ChatRoomResponse:
    """Create new chat room (direction group)."""
    _ = user.sub
    code = body.code.strip() if body.code else _slugify_room_code(body.name)

    # Simple uniqueness check
    res = await db.execute(select(ChatRoom).where(ChatRoom.code == code))
    existing = res.scalar_one_or_none()
    if existing:
        return ChatRoomResponse.model_validate(existing)

    room = ChatRoom(name=body.name.strip(), code=code)
    db.add(room)
    await db.flush()
    await db.refresh(room)
    return ChatRoomResponse.model_validate(room)


def _get_s3_client(settings: Settings):
    """Build a boto3 S3 client configured for MinIO."""
    import boto3
    from botocore.config import Config as BotoConfig

    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=BotoConfig(signature_version="s3v4"),
        region_name="us-east-1",
    )


def _get_presign_s3_client(settings: Settings):
    """Build an S3 client for presigned URL generation.

    The endpoint here must be reachable FROM the user's browser.
    """
    import boto3
    from botocore.config import Config as BotoConfig

    return boto3.client(
        "s3",
        endpoint_url=settings.minio_public_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=BotoConfig(signature_version="s3v4"),
        region_name="us-east-1",
    )


async def _resolve_db_user_id(db: AsyncSession, current_user: CurrentUser) -> uuid.UUID:
    """Resolve current user to local DB UUID (``users.id`` or ``keycloak_id``)."""
    return await resolve_users_table_id(db, current_user)


def _build_storage_key(message_id: uuid.UUID, attachment_id: uuid.UUID, filename: str) -> str:
    return f"chat_messages/{message_id}/{attachment_id}/{filename}"


def _presign_url(s3, *, bucket: str, storage_path: str) -> str:
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": storage_path},
        ExpiresIn=PRESIGNED_URL_EXPIRY_SECONDS,
    )


@router.get("/messages", response_model=PaginatedResponse[ChatMessageResponse])
async def list_messages(
    room: str = Query(default="company", min_length=1, max_length=100),
    after: datetime | None = Query(default=None, description="Fetch messages created after this timestamp"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> PaginatedResponse[ChatMessageResponse]:
    """List chat messages.

    Args:
        room: Chat room identifier.
        after: Optional lower bound for created_at timestamp.
        pagination: Pagination params.
        db: Async database session.
        user: Current authenticated user (authorization check only).

    Returns:
        Paginated response with messages sorted by ascending creation time.
    """
    # NOTE: "user" is only used for auth; chat is available to all active employees.
    _ = user.sub
    base_stmt = (
        select(ChatMessage)
        .options(
            selectinload(ChatMessage.sender),
            selectinload(ChatMessage.attachments),
        )
        .where(ChatMessage.room == room)
    )

    if after is not None:
        base_stmt = base_stmt.where(ChatMessage.created_at > after)

    result = await db.execute(
        base_stmt.order_by(ChatMessage.created_at.asc()).offset(pagination.offset).limit(pagination.limit)
    )
    items = result.scalars().all()
    total = len(items)

    settings = get_settings()
    # Use public endpoint for generating URLs consumed by the browser.
    s3 = _get_presign_s3_client(settings)

    return PaginatedResponse(
        items=[
            ChatMessageResponse(
                id=m.id,
                room=m.room,
                sender_id=m.sender_id,
                sender_name=m.sender_name,
                body=m.body,
                created_at=m.created_at,
                attachments=[
                    ChatAttachmentResponse(
                        id=a.id,
                        filename=a.filename,
                        mime_type=a.mime_type,
                        file_size=a.file_size,
                        download_url=_presign_url(
                            s3,
                            bucket=settings.minio_bucket,
                            storage_path=a.storage_path,
                        ),
                    )
                    for a in (m.attachments or [])
                ],
            )
            for m in items
        ],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.post("/messages", response_model=ChatMessageResponse, status_code=201)
async def create_message(
    body: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> ChatMessageResponse:
    """Create a new chat message.

    Args:
        body: Chat message payload.
        db: Async database session.
        user: Current authenticated user.

    Returns:
        Created message response.
    """
    sender_uuid = await resolve_users_table_id(db, user)

    clean_body = body.body.strip()
    msg = ChatMessage(room=body.room, sender_id=sender_uuid, body=clean_body)
    db.add(msg)
    await db.flush()

    # Re-load with sender/attachments to avoid lazy-loading in async context.
    result = await db.execute(
        select(ChatMessage)
        .options(selectinload(ChatMessage.sender), selectinload(ChatMessage.attachments))
        .where(ChatMessage.id == msg.id)
    )
    msg_with_sender = result.scalar_one()

    # No attachments yet, so no need to presign.
    return ChatMessageResponse(
        id=msg_with_sender.id,
        room=msg_with_sender.room,
        sender_id=msg_with_sender.sender_id,
        sender_name=msg_with_sender.sender_name,
        body=msg_with_sender.body,
        created_at=msg_with_sender.created_at,
        attachments=[],
    )


@router.post("/messages/{message_id}/attachments", response_model=ChatAttachmentResponse, status_code=201)
async def upload_chat_attachment(
    message_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ChatAttachmentResponse:
    """Upload a file attached to a chat message (including voice recordings)."""
    message_res = await db.execute(select(ChatMessage).where(ChatMessage.id == message_id))
    message = message_res.scalar_one_or_none()
    if not message:
        raise NotFoundError("ChatMessage", str(message_id))

    uploader_id = await _resolve_db_user_id(db, user)

    content = await file.read()
    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "unnamed"
    file_size = len(content)

    attachment_id = uuid.uuid4()
    storage_key = _build_storage_key(message_id=message_id, attachment_id=attachment_id, filename=filename)

    # Use internal endpoint for uploading.
    s3 = _get_s3_client(settings)
    try:
        s3.put_object(
            Bucket=settings.minio_bucket,
            Key=storage_key,
            Body=content,
            ContentType=content_type,
        )
    except Exception as exc:
        logger.error("MinIO put_object for chat attachment failed", error=str(exc))
        raise ValidationError("file", "Failed to upload file") from exc

    attachment = ChatAttachment(
        chat_message_id=message_id,
        uploaded_by=uploader_id,
        filename=filename,
        storage_path=storage_key,
        mime_type=content_type,
        file_size=file_size,
        description=None,
    )
    db.add(attachment)
    await db.flush()
    await db.refresh(attachment)

    return ChatAttachmentResponse(
        id=attachment.id,
        filename=attachment.filename,
        mime_type=attachment.mime_type,
        file_size=attachment.file_size,
        download_url=_presign_url(
            _get_presign_s3_client(settings),
            bucket=settings.minio_bucket,
            storage_path=attachment.storage_path,
        ),
    )

