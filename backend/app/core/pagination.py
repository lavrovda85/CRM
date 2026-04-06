"""Generic pagination response wrapper.

Предоставляет типизированный контейнер для постраничных ответов API.
"""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated API response container.

    Атрибуты:
        items: Список элементов текущей страницы.
        total: Общее количество элементов.
        offset: Текущее смещение.
        limit: Размер страницы.
    """

    items: list[T]
    total: int
    offset: int
    limit: int
