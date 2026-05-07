"""Company-wide chat REST API.

Provides:
- sending messages
- fetching message history (with polling-friendly "after" filter)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from app.core.company_context import ActiveCompanyContext, get_active_company
from app.core.config import Settings, get_settings
from app.core.dependencies import PaginationParams, get_current_user, get_db
from app.core.exceptions import ExternalServiceError, HVACBaseError, NotFoundError, ValidationError
from app.core.file_proxy_token import (
    content_disposition_header,
    decode_chat_attachment_token,
    encode_chat_attachment_token,
)
from app.core.pagination import PaginatedResponse
from app.core.security import CurrentUser
from app.models import ChatAttachment, ChatMessage, ChatRoom, UserCompanyMembership
from app.services.task_chat_room_service import TaskChatRoomService
from app.services.user_identity import resolve_users_table_id
from app.schemas.chat import (
    ChatAttachmentResponse,
    ChatMessageCreate,
    ChatMessageResponse,
    ChatRoomCreate,
    ChatRoomResponse,
    ChatRoomUpdate,
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


def _normalized_participant_ids(raw_ids: list[uuid.UUID | str] | None) -> list[str]:
    """Normalize UUID-ish participant IDs to unique non-empty strings."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in raw_ids or []:
        s = str(raw).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


async def _participant_ids_in_company(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    raw_ids: list[uuid.UUID | str] | None,
) -> list[str]:
    """Return only IDs that are members of the room company."""
    normalized = _normalized_participant_ids(raw_ids)
    if not normalized:
        return []
    uuids: list[uuid.UUID] = []
    for s in normalized:
        try:
            uuids.append(uuid.UUID(s))
        except ValueError:
            continue
    if not uuids:
        return []
    res = await db.execute(
        select(UserCompanyMembership.user_id).where(
            UserCompanyMembership.company_id == company_id,
            UserCompanyMembership.user_id.in_(uuids),
        ),
    )
    return sorted({str(x) for x in res.scalars().all()})


def _room_has_access(room: ChatRoom, *, viewer_id: uuid.UUID) -> bool:
    """Return True if viewer can read room content."""
    if not room.is_private:
        return True
    return str(viewer_id) in _normalized_participant_ids(room.participant_user_ids)


def _assert_room_access(room: ChatRoom, *, viewer_id: uuid.UUID, write: bool = False) -> None:
    """Raise 403 when viewer cannot access room (or room is archived for writes)."""
    if not _room_has_access(room, viewer_id=viewer_id):
        raise HVACBaseError(
            message="You are not a participant of this private room",
            code="CHAT_ROOM_FORBIDDEN",
            status_code=403,
        )
    if write and room.is_archived:
        raise HVACBaseError(
            message="Room is archived and read-only",
            code="CHAT_ROOM_ARCHIVED",
            status_code=409,
        )


async def _ensure_default_room(db: AsyncSession, *, ctx: ActiveCompanyContext) -> None:
    """Create default company chat room in tenant scope if absent."""
    existing = await db.execute(
        select(ChatRoom.id).where(ChatRoom.company_id == ctx.company_id).limit(1),
    )
    if existing.scalar() is not None:
        return
    room = ChatRoom(
        name="Общий чат",
        code="company",
        company_id=ctx.company_id,
        is_private=False,
        is_archived=False,
        participant_user_ids=[],
    )
    db.add(room)
    await db.flush()


async def _room_by_code(
    db: AsyncSession,
    *,
    ctx: ActiveCompanyContext,
    room_code: str,
) -> ChatRoom:
    """Load room by company + code or raise 404."""
    res = await db.execute(
        select(ChatRoom).where(ChatRoom.company_id == ctx.company_id, ChatRoom.code == room_code),
    )
    room = res.scalar_one_or_none()
    if room is None:
        raise NotFoundError("ChatRoom", room_code)
    return room


@router.get("/rooms", response_model=list[ChatRoomResponse])
async def list_rooms(
    include_archived: bool = Query(default=False, description="Include archived groups"),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    ctx: ActiveCompanyContext = Depends(get_active_company),
) -> list[ChatRoomResponse]:
    """List available chat rooms visible to the current user."""
    _ = user.sub
    await _ensure_default_room(db, ctx=ctx)
    query = select(ChatRoom).where(ChatRoom.company_id == ctx.company_id)
    if not include_archived:
        query = query.where(ChatRoom.is_archived.is_(False))
    res = await db.execute(query.order_by(ChatRoom.created_at.asc()))
    rooms = [r for r in res.scalars().all() if _room_has_access(r, viewer_id=ctx.user_db_id)]
    return [ChatRoomResponse.model_validate(r) for r in rooms]


@router.post("/rooms", response_model=ChatRoomResponse, status_code=201)
async def create_room(
    body: ChatRoomCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    ctx: ActiveCompanyContext = Depends(get_active_company),
) -> ChatRoomResponse:
    """Create chat room (public or private) in tenant scope."""
    _ = user.sub
    code = body.code.strip() if body.code else _slugify_room_code(body.name)
    if code == "company":
        raise ValidationError("code", "Code 'company' is reserved for the default room")
    if code.startswith("task-"):
        raise ValidationError("code", "Codes starting with 'task-' are reserved for task rooms")

    # Simple uniqueness check per tenant
    res = await db.execute(
        select(ChatRoom).where(ChatRoom.company_id == ctx.company_id, ChatRoom.code == code),
    )
    existing = res.scalar_one_or_none()
    if existing:
        return ChatRoomResponse.model_validate(existing)

    participants = await _participant_ids_in_company(
        db,
        company_id=ctx.company_id,
        raw_ids=body.participant_user_ids,
    )
    if body.is_private:
        participants = sorted(set(participants + [str(ctx.user_db_id)]))
    else:
        participants = []

    room = ChatRoom(
        name=body.name.strip(),
        code=code,
        company_id=ctx.company_id,
        is_private=body.is_private,
        is_archived=False,
        participant_user_ids=participants,
    )
    db.add(room)
    await db.flush()
    await db.refresh(room)
    return ChatRoomResponse.model_validate(room)


@router.patch("/rooms/{room_id}", response_model=ChatRoomResponse)
async def update_room(
    room_id: uuid.UUID,
    body: ChatRoomUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    ctx: ActiveCompanyContext = Depends(get_active_company),
) -> ChatRoomResponse:
    """Update room metadata, archive flag, privacy and participant list."""
    _ = user.sub
    res = await db.execute(
        select(ChatRoom).where(ChatRoom.id == room_id, ChatRoom.company_id == ctx.company_id),
    )
    room = res.scalar_one_or_none()
    if room is None:
        raise NotFoundError("ChatRoom", str(room_id))

    _assert_room_access(room, viewer_id=ctx.user_db_id, write=False)

    if body.name is not None:
        room.name = body.name.strip()
    if body.description is not None:
        room.description = body.description.strip() or None
    if body.is_archived is not None:
        if room.code == "company" and body.is_archived:
            raise ValidationError("is_archived", "Default company room cannot be archived")
        room.is_archived = bool(body.is_archived)
    if body.is_private is not None:
        room.is_private = bool(body.is_private)
    if body.participant_user_ids is not None:
        participant_ids = await _participant_ids_in_company(
            db,
            company_id=ctx.company_id,
            raw_ids=body.participant_user_ids,
        )
        if room.is_private:
            room.participant_user_ids = sorted(set(participant_ids + [str(ctx.user_db_id)]))
        else:
            room.participant_user_ids = []
    elif room.is_private:
        # Keep editor from locking itself out.
        ids = set(_normalized_participant_ids(room.participant_user_ids))
        ids.add(str(ctx.user_db_id))
        room.participant_user_ids = sorted(ids)

    await db.flush()
    await db.refresh(room)
    return ChatRoomResponse.model_validate(room)


@router.get("/task-room/{task_id}", response_model=ChatRoomResponse)
async def get_task_room(
    task_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    ctx: ActiveCompanyContext = Depends(get_active_company),
) -> ChatRoomResponse:
    """Return task-linked room (if created by first comment)."""
    _ = user.sub
    room = await TaskChatRoomService.get_for_task(db, company_id=ctx.company_id, task_id=task_id)
    if room is None:
        raise NotFoundError("ChatRoom", f"task:{task_id}")
    _assert_room_access(room, viewer_id=ctx.user_db_id, write=False)
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


def _chat_attachment_download_url(
    settings: Settings,
    *,
    attachment_id: uuid.UUID,
    storage_path: str,
    user_sub: str,
) -> str:
    """Public URL for a chat attachment (API proxy with token, or MinIO presigned)."""
    if settings.document_file_proxy_enabled:
        raw = encode_chat_attachment_token(
            settings.secret_key,
            attachment_id=attachment_id,
            user_sub=user_sub or "",
        )
        return f"/api/v1/chat/attachments/{attachment_id}/file?token={quote(raw, safe='')}"
    return _presign_url(
        _get_presign_s3_client(settings),
        bucket=settings.minio_bucket,
        storage_path=storage_path,
    )


@router.get("/messages", response_model=PaginatedResponse[ChatMessageResponse])
async def list_messages(
    room: str = Query(default="company", min_length=1, max_length=100),
    after: datetime | None = Query(default=None, description="Fetch messages created after this timestamp"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    ctx: ActiveCompanyContext = Depends(get_active_company),
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
    _ = user.sub
    room_code = room.strip() or "company"
    await _ensure_default_room(db, ctx=ctx)
    room_row = await _room_by_code(db, ctx=ctx, room_code=room_code)
    _assert_room_access(room_row, viewer_id=ctx.user_db_id, write=False)

    base_stmt = (
        select(ChatMessage)
        .options(
            selectinload(ChatMessage.sender),
            selectinload(ChatMessage.attachments),
        )
        .where(ChatMessage.room == room_code)
    )

    if after is not None:
        base_stmt = base_stmt.where(ChatMessage.created_at > after)

    result = await db.execute(
        base_stmt.order_by(ChatMessage.created_at.asc()).offset(pagination.offset).limit(pagination.limit)
    )
    items = result.scalars().all()
    total = len(items)

    settings = get_settings()

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
                        download_url=_chat_attachment_download_url(
                            settings,
                            attachment_id=a.id,
                            storage_path=a.storage_path,
                            user_sub=user.sub or "",
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
    ctx: ActiveCompanyContext = Depends(get_active_company),
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
    room_code = (body.room or "").strip() or "company"
    await _ensure_default_room(db, ctx=ctx)
    room_row = await _room_by_code(db, ctx=ctx, room_code=room_code)
    _assert_room_access(room_row, viewer_id=ctx.user_db_id, write=True)

    clean_body = body.body.strip()
    msg = ChatMessage(room=room_code, sender_id=sender_uuid, body=clean_body)
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
    ctx: ActiveCompanyContext = Depends(get_active_company),
    settings: Settings = Depends(get_settings),
) -> ChatAttachmentResponse:
    """Upload a file attached to a chat message (including voice recordings)."""
    message_res = await db.execute(select(ChatMessage).where(ChatMessage.id == message_id))
    message = message_res.scalar_one_or_none()
    if not message:
        raise NotFoundError("ChatMessage", str(message_id))

    await _ensure_default_room(db, ctx=ctx)
    room_row = await _room_by_code(db, ctx=ctx, room_code=(message.room or "").strip() or "company")
    _assert_room_access(room_row, viewer_id=ctx.user_db_id, write=True)

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
        download_url=_chat_attachment_download_url(
            settings,
            attachment_id=attachment.id,
            storage_path=attachment.storage_path,
            user_sub=user.sub or "",
        ),
    )


@router.get("/attachments/{attachment_id}/file")
async def stream_chat_attachment_file(
    attachment_id: uuid.UUID,
    token: str = Query(..., min_length=8, description="Signed token from chat attachment download_url"),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Stream a chat attachment from MinIO using an API-issued token (no browser → MinIO hop)."""
    if not settings.document_file_proxy_enabled:
        raise NotFoundError("ChatAttachment", str(attachment_id))

    payload = decode_chat_attachment_token(settings.secret_key, token, max_age=PRESIGNED_URL_EXPIRY_SECONDS)
    if not payload or str(attachment_id) != payload.get("a"):
        raise ValidationError("token", "Invalid or expired download token")

    res = await db.execute(select(ChatAttachment).where(ChatAttachment.id == attachment_id))
    attachment = res.scalar_one_or_none()
    if not attachment:
        raise NotFoundError("ChatAttachment", str(attachment_id))

    def _load() -> tuple[bytes, str]:
        s3 = _get_s3_client(settings)
        resp = s3.get_object(Bucket=settings.minio_bucket, Key=attachment.storage_path)
        body = resp["Body"].read()
        ct = (resp.get("ContentType") or attachment.mime_type or "application/octet-stream").strip()
        return body, ct

    try:
        data, content_type = await asyncio.to_thread(_load)
    except Exception as exc:
        logger.error("MinIO get_object for chat attachment failed", extra={"error": str(exc)})
        raise ExternalServiceError("MinIO", "get_object", str(exc)) from exc

    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": content_disposition_header(attachment.filename, content_type)},
    )

