"""FastAPI dependency injection providers.

Централизованные зависимости для инъекции в эндпоинты:
сессия БД, текущий пользователь, пагинация.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import CurrentUser, get_current_user, get_current_user_optional
from app.services.user_identity import resolve_users_table_id

DbSession = AsyncSession
UserDep = CurrentUser


async def get_db(session: AsyncSession = Depends(get_db_session)) -> AsyncGenerator[AsyncSession, None]:
    """Alias dependency for database session injection.

    Yields:
        AsyncSession: Активная сессия БД.
    """
    yield session


class PaginationParams:
    """Query parameter container for paginated endpoints.

    Атрибуты:
        offset: Смещение от начала выборки.
        limit: Максимальное количество записей.
    """

    def __init__(
        self,
        offset: int = Query(default=0, ge=0, description="Offset from the beginning"),
        limit: int = Query(default=50, ge=1, le=200, description="Max records to return"),
    ) -> None:
        self.offset = offset
        self.limit = limit


async def get_crm_user_id(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> UUID:
    """Resolve JWT actor to ``users.id`` (matches ``keycloak_id`` when ids differ)."""
    return await resolve_users_table_id(db, user)


__all__ = [
    "DbSession",
    "PaginationParams",
    "UserDep",
    "get_crm_user_id",
    "get_current_user",
    "get_current_user_optional",
    "get_db",
]
