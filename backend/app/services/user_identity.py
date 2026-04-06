"""Resolve CRM ``users.id`` from JWT-backed ``CurrentUser``.

Используется MCP/AI и сервисами, где внешний ``sub`` может совпадать с
``users.id`` или храниться в ``users.keycloak_id``.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.security import CurrentUser
from app.models.user import User


async def resolve_users_table_id(db: AsyncSession, user: CurrentUser) -> uuid.UUID:
    """Return primary key ``users.id`` for FK columns (created_by, changed_by, …).

    Tries ``User.id == sub`` when ``sub`` parses as UUID, then ``User.keycloak_id == sub``.

    Args:
        db: Database session.
        user: Authenticated actor (JWT or dev).

    Returns:
        Internal user UUID.

    Raises:
        NotFoundError: No matching active user row.
    """
    sub = (user.sub or "").strip()
    if not sub:
        raise NotFoundError("User", "missing subject")

    as_uuid: uuid.UUID | None
    try:
        as_uuid = uuid.UUID(sub)
    except ValueError:
        as_uuid = None

    if as_uuid is not None:
        res = await db.execute(select(User.id).where(User.id == as_uuid, User.is_active.is_(True)))
        row = res.scalar_one_or_none()
        if row is not None:
            return row

    res = await db.execute(select(User.id).where(User.keycloak_id == sub, User.is_active.is_(True)))
    row = res.scalar_one_or_none()
    if row is None:
        raise NotFoundError("User", sub)
    return row
