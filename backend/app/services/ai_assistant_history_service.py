"""DB persistence for AI assistant messages and per-user session context."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.tender.tender_external_service import _normalize_url_for_search_dedup

from app.models.ai_assistant_chat import (
    AiAssistantMessage as AiAssistantMessageRow,
    AiAssistantSession,
)

MAX_MESSAGES_PER_USER = 400
KEEP_AFTER_PRUNE = 300


async def get_session_context(db: AsyncSession, user_subject: str) -> dict[str, Any]:
    """Load JSON context blob for ``user_subject`` (JWT sub)."""
    row = await db.get(AiAssistantSession, user_subject)
    if row is None or not row.context:
        return {}
    return dict(row.context)


async def merge_session_context(
    db: AsyncSession,
    user_subject: str,
    patch: dict[str, Any],
) -> dict[str, Any]:
    """Merge ``patch`` into stored context and return the merged dict."""
    if not patch:
        return await get_session_context(db, user_subject)

    row = await db.get(AiAssistantSession, user_subject)
    base: dict[str, Any] = dict(row.context) if row and row.context else {}
    for k, v in patch.items():
        if v is not None:
            base[k] = v
    base["updated_at"] = datetime.now(timezone.utc).isoformat()

    if patch.get("tender_search_reset_seen"):
        base["tender_search_seen_urls"] = []
    if patch.get("last_tender_search_results"):
        nu: list[str] = []
        for r in patch["last_tender_search_results"]:
            if not isinstance(r, dict):
                continue
            u = str(r.get("url") or "").strip()
            if not u:
                continue
            nu.append(_normalize_url_for_search_dedup(u))
        prev = base.get("tender_search_seen_urls") or []
        base["tender_search_seen_urls"] = list(dict.fromkeys([*prev, *nu]))[:500]
    base.pop("tender_search_reset_seen", None)

    if row is None:
        row = AiAssistantSession(user_subject=user_subject, context=base)
        db.add(row)
    else:
        row.context = base
    await db.flush()
    return base


async def list_recent_messages(
    db: AsyncSession,
    user_subject: str,
    *,
    limit: int = 60,
) -> list[dict[str, Any]]:
    """Return recent messages as ``{role, content}`` oldest-first for the model."""
    lim = max(1, min(limit, 100))
    result = await db.execute(
        select(AiAssistantMessageRow)
        .where(AiAssistantMessageRow.user_subject == user_subject)
        .order_by(AiAssistantMessageRow.created_at.desc())
        .limit(lim)
    )
    rows = list(reversed(result.scalars().all()))
    return [{"role": m.role, "content": m.content} for m in rows]


async def append_message(
    db: AsyncSession,
    user_subject: str,
    role: str,
    content: str,
) -> None:
    """Persist one chat line and prune old rows if over cap."""
    db.add(
        AiAssistantMessageRow(
            id=uuid.uuid4(),
            user_subject=user_subject,
            role=role,
            content=content,
        )
    )
    await db.flush()

    cnt = await db.scalar(
        select(func.count())
        .select_from(AiAssistantMessageRow)
        .where(AiAssistantMessageRow.user_subject == user_subject)
    )
    if cnt and cnt > MAX_MESSAGES_PER_USER:
        keep_res = await db.execute(
            select(AiAssistantMessageRow.id)
            .where(AiAssistantMessageRow.user_subject == user_subject)
            .order_by(AiAssistantMessageRow.created_at.desc())
            .limit(KEEP_AFTER_PRUNE)
        )
        keep_ids = [r[0] for r in keep_res.fetchall()]
        if keep_ids:
            await db.execute(
                delete(AiAssistantMessageRow).where(
                    AiAssistantMessageRow.user_subject == user_subject,
                    AiAssistantMessageRow.id.not_in(keep_ids),
                )
            )


async def clear_history(db: AsyncSession, user_subject: str) -> None:
    """Remove all messages and session context for a user (e.g. logout)."""
    await db.execute(
        delete(AiAssistantMessageRow).where(AiAssistantMessageRow.user_subject == user_subject)
    )
    await db.execute(delete(AiAssistantSession).where(AiAssistantSession.user_subject == user_subject))
    await db.flush()


async def list_messages_for_ui(
    db: AsyncSession,
    user_subject: str,
    *,
    limit: int = 120,
) -> list[AiAssistantMessageRow]:
    """Return recent rows oldest-first for the assistant UI."""
    lim = max(1, min(limit, 200))
    result = await db.execute(
        select(AiAssistantMessageRow)
        .where(AiAssistantMessageRow.user_subject == user_subject)
        .order_by(AiAssistantMessageRow.created_at.desc())
        .limit(lim)
    )
    return list(reversed(result.scalars().all()))
