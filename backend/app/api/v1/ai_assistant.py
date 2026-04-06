"""REST endpoints for the OpenAI-powered CRM assistant (MCP-equivalent tools)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.dependencies import get_current_user, get_current_user_optional, get_db
from app.core.exceptions import AiAssistantUnavailableError
from app.core.security import CurrentUser
from app.services.ai_assistant_history_service import (
    append_message,
    clear_history,
    get_session_context,
    list_messages_for_ui,
    list_recent_messages,
    merge_session_context,
)
from app.services.ai_assistant_media import AttachmentBuildResult, build_upload_parts
from app.services.ai_assistant_service import run_ai_chat

router = APIRouter(prefix="/ai-assistant")


class AiChatMessage(BaseModel):
    """Legacy optional body field (ignored; history is server-side per user)."""

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=32000)


class AiChatRequest(BaseModel):
    """User message only; conversation history is loaded from the database."""

    message: str = Field(..., min_length=1, max_length=12000)
    messages: list[AiChatMessage] = Field(
        default_factory=list,
        max_length=50,
        description="Deprecated: ignored. History is stored per user on the server.",
    )


class AiMessageItem(BaseModel):
    """One chat row returned to the UI."""

    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class AiUploadFileSummary(BaseModel):
    """Per-file outcome for multipart /chat/upload (UI + debugging)."""

    name: str
    kind: str
    included_in_context: bool = True
    text_chars: int | None = None
    note: str | None = None


class AiUploadContext(BaseModel):
    """Confirms which attachments were merged into the model request."""

    merged_into_model: bool = True
    total_document_text_chars: int | None = None
    images_for_vision: int = 0
    files: list[AiUploadFileSummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AiChatResponse(BaseModel):
    """Assistant reply and full recent thread for client sync."""

    reply: str
    messages: list[AiMessageItem]
    upload_context: AiUploadContext | None = None


class AiAssistantStatus(BaseModel):
    """Whether the assistant is configured (no secrets exposed)."""

    enabled: bool
    model: str


def _user_subject(user: CurrentUser) -> str:
    """Stable key for chat storage (JWT ``sub``)."""
    return (user.sub or "").strip() or "anonymous"


@router.get("/status", response_model=AiAssistantStatus)
async def assistant_status() -> AiAssistantStatus:
    """Return configuration status for the UI (no API keys)."""
    s = get_settings()
    key_ok = bool(s.openai_api_key and str(s.openai_api_key).strip())
    return AiAssistantStatus(enabled=key_ok, model=s.openai_model)


@router.get("/messages", response_model=list[AiMessageItem])
async def assistant_list_messages(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[AiMessageItem]:
    """Return persisted chat for the current user (oldest first)."""
    rows = await list_messages_for_ui(db, _user_subject(user), limit=120)
    return [
        AiMessageItem(
            id=str(m.id),
            role=m.role if m.role in ("user", "assistant") else "assistant",
            content=m.content,
            created_at=m.created_at,
        )
        for m in rows
    ]


@router.post("/clear")
async def assistant_clear_history(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser | None = Depends(get_current_user_optional),
) -> dict[str, bool]:
    """Delete AI assistant history for the authenticated user, or no-op if unauthenticated.

    Missing or invalid tokens return ``ok`` without 401 so logout/login pages do not
    spam the logs when the UI best-effort clears server-side state.
    """
    if user is not None:
        await clear_history(db, _user_subject(user))
        await db.commit()
    return {"ok": True}


@router.post("/chat", response_model=AiChatResponse)
async def assistant_chat(
    body: AiChatRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> AiChatResponse:
    """Run one assistant turn; persist user + assistant lines and session context."""
    s = get_settings()
    if not s.openai_api_key or not str(s.openai_api_key).strip():
        raise AiAssistantUnavailableError()

    sub = _user_subject(user)
    prior = await list_recent_messages(db, sub, limit=60)
    ctx = await get_session_context(db, sub)

    await append_message(db, sub, "user", body.message.strip())
    await db.commit()

    turn = await run_ai_chat(
        user=user,
        user_message=body.message,
        prior_messages=prior,
        session_context=ctx,
        settings=s,
    )

    await merge_session_context(db, sub, turn.context_patch)
    await append_message(db, sub, "assistant", turn.reply)
    await db.commit()

    rows = await list_messages_for_ui(db, sub, limit=120)
    items = [
        AiMessageItem(
            id=str(m.id),
            role=m.role if m.role in ("user", "assistant") else "assistant",
            content=m.content,
            created_at=m.created_at,
        )
        for m in rows
    ]
    return AiChatResponse(reply=turn.reply, messages=items, upload_context=None)


def _upload_context_from_build(built: AttachmentBuildResult) -> AiUploadContext:
    files = [
        AiUploadFileSummary(
            name=str(s.get("name") or ""),
            kind=str(s.get("kind") or "unknown"),
            included_in_context=bool(s.get("included_in_context")),
            text_chars=s.get("text_chars"),
            note=s.get("note"),
        )
        for s in built.file_summaries
    ]
    return AiUploadContext(
        merged_into_model=True,
        total_document_text_chars=built.total_document_text_chars or None,
        images_for_vision=built.vision_image_count,
        files=files,
        warnings=list(built.warnings),
    )


@router.post("/chat/upload", response_model=AiChatResponse)
async def assistant_chat_with_files(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    message: str = Form(""),
    files: list[UploadFile] | None = File(None),
) -> AiChatResponse:
    """Same as ``/chat``, but accepts multipart files: PDF, DOCX, XLSX, CSV, images (scans)."""
    s = get_settings()
    if not s.openai_api_key or not str(s.openai_api_key).strip():
        raise AiAssistantUnavailableError()

    file_list = files or []
    if not file_list:
        raise HTTPException(
            status_code=400,
            detail="Добавьте хотя бы один файл или используйте POST /ai-assistant/chat с JSON.",
        )

    sub = _user_subject(user)
    prior = await list_recent_messages(db, sub, limit=60)
    ctx = await get_session_context(db, sub)

    try:
        built = await build_upload_parts(message, file_list)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    display = built.history_line
    if built.warnings:
        display = f"{display}\n\n" + "\n".join(built.warnings)
    await append_message(db, sub, "user", display[:50000])
    await db.commit()

    short_log = (message or "").strip()[:500] or "(вложения)"
    turn = await run_ai_chat(
        user=user,
        user_message=short_log,
        prior_messages=prior,
        session_context=ctx,
        settings=s,
        multimodal_user_content=built.content_parts,
    )

    await merge_session_context(db, sub, turn.context_patch)
    await append_message(db, sub, "assistant", turn.reply)
    await db.commit()

    rows = await list_messages_for_ui(db, sub, limit=120)
    items = [
        AiMessageItem(
            id=str(m.id),
            role=m.role if m.role in ("user", "assistant") else "assistant",
            content=m.content,
            created_at=m.created_at,
        )
        for m in rows
    ]
    return AiChatResponse(
        reply=turn.reply,
        messages=items,
        upload_context=_upload_context_from_build(built),
    )
