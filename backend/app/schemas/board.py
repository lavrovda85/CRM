"""Schemas for board entities.

Схемы валидации для создания, обновления и ответа
Kanban/Scrum досок с группировкой задач.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BoardCreate(BaseModel):
    """Schema for creating a new board.

    Атрибуты:
        name (str): Название доски.
        description (str | None): Описание.
        board_type (str): Тип доски — kanban, scrum, tender.
        columns (list): JSON определение колонок.
    """

    name: str = Field(..., max_length=255)
    description: str | None = None
    board_type: str = Field(default="kanban", max_length=50)
    columns: list[Any] = Field(default_factory=list)


class BoardUpdate(BaseModel):
    """Schema for partial board update.

    Атрибуты:
        name (str | None): Название доски.
        description (str | None): Описание.
        columns (list | None): Определение колонок.
        is_archived (bool | None): Архивирована ли доска.
    """

    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    columns: list[Any] | None = None
    is_archived: bool | None = None


class BoardResponse(BaseModel):
    """Schema for board API response.

    Атрибуты:
        id (uuid.UUID): Уникальный идентификатор доски.
        name (str): Название доски.
        description (str | None): Описание.
        board_type (str): Тип доски.
        owner_id (uuid.UUID | None): ID владельца.
        columns (list): Определение колонок.
        is_archived (bool): Архивирована ли доска.
        created_at (datetime): Дата создания.
        updated_at (datetime): Дата обновления.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    board_type: str
    owner_id: uuid.UUID | None = None
    columns: list[Any] = Field(default_factory=list)
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class BoardDetailResponse(BoardResponse):
    """Extended board response with tasks grouped by status.

    Атрибуты:
        tasks_by_status (dict): Задачи, сгруппированные по статусу.
    """

    tasks_by_status: dict[str, list[Any]] = Field(default_factory=dict)
