"""FastAPI dependency injection providers.

Централизованные зависимости для инъекции в эндпоинты:
сессия БД, текущий пользователь, пагинация.
"""

from collections.abc import AsyncGenerator

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.security import CurrentUser, get_current_user

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


__all__ = [
    "DbSession",
    "PaginationParams",
    "UserDep",
    "get_current_user",
    "get_db",
]
