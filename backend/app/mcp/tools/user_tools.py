"""MCP tools for searching internal CRM users (assignees, staff)."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.exceptions import ValidationError
from app.mcp.server import mcp
from app.models.user import User


def _meaningful_tokens(q: str) -> list[str]:
    """Split query into tokens of length >= 2 (handles «Иванов Петр» vs «Петр Иванов»)."""
    return [t for t in (q or "").strip().split() if len(t) >= 2]


async def _find_active_users_by_query(
    session: AsyncSession,
    q: str,
    *,
    limit: int = 50,
) -> list[User]:
    """Return active users matching name or email.

    Single-token: substring match (legacy). Multi-token: each token must match
    ``full_name`` or ``email`` (order-independent), so «Лавров Дмитрий» finds
    «Дмитрий Лавров» as well.
    """
    term = (q or "").strip()
    if len(term) < 2:
        raise ValidationError("q", "Query must be at least 2 characters")

    tokens = _meaningful_tokens(term)
    if not tokens:
        raise ValidationError("q", "Use words with at least 2 characters each")

    stmt = select(User).where(User.is_active.is_(True))
    if len(tokens) == 1:
        pattern = f"%{tokens[0]}%"
        stmt = stmt.where(or_(User.full_name.ilike(pattern), User.email.ilike(pattern)))
    else:
        for tok in tokens:
            pat = f"%{tok}%"
            stmt = stmt.where(or_(User.full_name.ilike(pat), User.email.ilike(pat)))

    stmt = stmt.order_by(User.full_name.asc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@mcp.tool()
async def search_users(q: str, limit: int = 15) -> list[dict]:
    """Search employees by full name or email (case-insensitive substring).

    Use before ``assign_to`` / ``create_task(assigned_to=...)`` when the user gives
    a Russian name like «Лавров Дмитрий». Pick the correct ``id`` (UUID) from results.

    Args:
        q: Search text (at least 2 characters after strip).
        limit: Max rows (1–50).

    Returns:
        list[dict]: Each item has id, full_name, email, role.
    """
    try:
        lim_raw = int(limit)
    except (TypeError, ValueError):
        lim_raw = 15
    lim = max(1, min(lim_raw, 50))

    async with async_session_factory() as session:
        rows = await _find_active_users_by_query(session, q, limit=lim)

    return [
        {
            "id": str(u.id),
            "full_name": u.full_name,
            "email": u.email,
            "role": u.role,
        }
        for u in rows
    ]
