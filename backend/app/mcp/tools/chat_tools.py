"""MCP tools for company chat (rooms and messages).

Mirrors ``/api/v1/chat`` behaviour; messages are sent as the dev/system user
the MCP / AI actor user when no JWT context exists — same pattern as other MCP tools.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.database import async_session_factory
from app.core.exceptions import NotFoundError, ValidationError
from app.core.security import DEV_USER_ID
from app.mcp.server import mcp
from app.models import ChatMessage, ChatRoom, User
from app.schemas.chat import ChatMessageResponse, ChatRoomResponse


async def _ensure_default_room(session) -> None:
    cnt = await session.execute(select(func.count(ChatRoom.id)))
    if (cnt.scalar() or 0) == 0:
        session.add(ChatRoom(name="Общий чат", code="company"))
        await session.flush()


@mcp.tool()
async def list_chat_rooms() -> list[dict]:
    """List chat rooms (direction groups).

    Returns:
        list[dict]: Room id, name, code, created_at.
    """
    async with async_session_factory() as session:
        await _ensure_default_room(session)
        await session.commit()
    async with async_session_factory() as session:
        res = await session.execute(select(ChatRoom).order_by(ChatRoom.created_at.asc()))
        rooms = res.scalars().all()
        return [ChatRoomResponse.model_validate(r).model_dump(mode="json") for r in rooms]


@mcp.tool()
async def list_chat_messages(
    room: str = "company",
    limit: int = 50,
    after_iso: str | None = None,
) -> list[dict]:
    """List recent chat messages in a room (oldest first within the page).

    Args:
        room: Room code (default ``company``).
        limit: Max messages (1–200).
        after_iso: Optional ISO timestamp — only messages strictly after this time.

    Returns:
        Messages with id, room, sender_id, sender_name, body, created_at.
        Attachments are omitted for MCP (no presigned URLs without MinIO context).
    """
    lim = max(1, min(int(limit), 200))
    after_dt: datetime | None = None
    if after_iso and str(after_iso).strip():
        try:
            after_dt = datetime.fromisoformat(str(after_iso).strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValidationError("after_iso", "Invalid ISO datetime") from exc

    async with async_session_factory() as session:
        await _ensure_default_room(session)
        await session.commit()

    async with async_session_factory() as session:
        stmt = (
            select(ChatMessage)
            .options(selectinload(ChatMessage.sender))
            .where(ChatMessage.room == room.strip())
        )
        if after_dt is not None:
            stmt = stmt.where(ChatMessage.created_at > after_dt)
        stmt = stmt.order_by(ChatMessage.created_at.desc()).limit(lim)
        res = await session.execute(stmt)
        rows = list(reversed(res.scalars().all()))

    out: list[dict] = []
    for m in rows:
        d = ChatMessageResponse(
            id=m.id,
            room=m.room,
            sender_id=m.sender_id,
            sender_name=m.sender_name,
            body=m.body,
            created_at=m.created_at,
            attachments=[],
        ).model_dump(mode="json")
        out.append(d)
    return out


@mcp.tool()
async def send_chat_message(
    body: str,
    room: str = "company",
) -> dict:
    """Post a text message to a chat room as the MCP actor user.

    Args:
        body: Message text (non-empty after strip).
        room: Target room code.

    Returns:
        Created message as dict (no attachment URLs).
    """
    clean = (body or "").strip()
    if not clean:
        raise ValidationError("body", "Message body must not be empty")

    sender_uuid = uuid.UUID(current_mcp_user_sub())
    code = room.strip() or "company"

    async with async_session_factory() as session:
        await _ensure_default_room(session)

        user_row = await session.get(User, sender_uuid)
        if user_row is None:
            raise NotFoundError("User", current_mcp_user_sub())

        room_res = await session.execute(select(ChatRoom).where(ChatRoom.code == code))
        room_row = room_res.scalar_one_or_none()
        if room_row is None:
            raise NotFoundError("ChatRoom", code)

        msg = ChatMessage(room=code, sender_id=sender_uuid, body=clean)
        session.add(msg)
        await session.flush()

        result = await session.execute(
            select(ChatMessage)
            .options(selectinload(ChatMessage.sender), selectinload(ChatMessage.attachments))
            .where(ChatMessage.id == msg.id)
        )
        msg_full = result.scalar_one()
        await session.commit()

    return ChatMessageResponse(
        id=msg_full.id,
        room=msg_full.room,
        sender_id=msg_full.sender_id,
        sender_name=msg_full.sender_name,
        body=msg_full.body,
        created_at=msg_full.created_at,
        attachments=[],
    ).model_dump(mode="json")
