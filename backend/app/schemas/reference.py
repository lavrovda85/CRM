"""Schemas for dynamic reference dictionary entities.

Схемы валидации для создания, обновления и ответа
справочников и их элементов.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReferenceCreate(BaseModel):
    """Schema for creating a reference dictionary.

    Атрибуты:
        code (str): Машинное имя справочника.
        name (str): Человекочитаемое название.
        description (str | None): Описание.
        is_system (bool): Системный справочник.
    """

    code: str = Field(..., max_length=100)
    name: str = Field(..., max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    is_system: bool = False


class ReferenceItemCreate(BaseModel):
    """Schema for adding an item to a reference dictionary.

    Атрибуты:
        code (str): Машинное имя элемента.
        name (str): Отображаемое название.
        metadata (dict): Дополнительные атрибуты.
        order (int): Порядок сортировки.
        is_active (bool): Активен ли элемент.
    """

    code: str = Field(..., max_length=100)
    name: str = Field(..., max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)
    order: int = 0
    is_active: bool = True


class ReferenceItemUpdate(BaseModel):
    """Schema for partial reference item update.

    Атрибуты:
        name (str | None): Отображаемое название.
        metadata (dict | None): Дополнительные атрибуты.
        order (int | None): Порядок сортировки.
        is_active (bool | None): Активен ли элемент.
    """

    name: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] | None = None
    order: int | None = None
    is_active: bool | None = None


class ReferenceItemResponse(BaseModel):
    """Schema for reference item in API response.

    Атрибуты:
        id (uuid.UUID): Уникальный идентификатор элемента.
        reference_id (uuid.UUID): ID справочника.
        code (str): Машинное имя элемента.
        name (str): Отображаемое название.
        metadata (dict): Дополнительные атрибуты.
        order (int): Порядок сортировки.
        is_active (bool): Активен ли элемент.
        created_at (datetime): Дата создания.
        updated_at (datetime): Дата обновления.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    reference_id: uuid.UUID
    code: str
    name: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ReferenceResponse(BaseModel):
    """Schema for reference dictionary API response.

    Атрибуты:
        id (uuid.UUID): Уникальный идентификатор справочника.
        code (str): Машинное имя справочника.
        name (str): Человекочитаемое название.
        description (str | None): Описание.
        is_system (bool): Системный справочник.
        items (list[ReferenceItemResponse]): Элементы справочника.
        created_at (datetime): Дата создания.
        updated_at (datetime): Дата обновления.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    is_system: bool
    items: list[ReferenceItemResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
