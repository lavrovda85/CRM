"""Schemas for tender/bid entities.

Схемы валидации для создания, обновления и ответа
тендеров с собственным жизненным циклом.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TenderCreate(BaseModel):
    """Schema for creating a new tender.

    Атрибуты:
        title (str): Название тендера.
        source (str | None): Источник / площадка.
        budget (Decimal | None): Бюджет тендера.
        our_price (Decimal | None): Наша ценовая заявка.
        status (str): Текущий статус тендера.
        deadline (date | None): Крайний срок подачи заявки.
        assigned_to (uuid.UUID | None): ID ответственного менеджера.
        requirements (dict): Требования тендера (JSON).
        notes (str | None): Заметки.
    """

    title: str = Field(..., max_length=500)
    source: str | None = Field(default=None, max_length=255)
    budget: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    our_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    status: str = Field(default="search", max_length=50)
    deadline: date | None = None
    assigned_to: uuid.UUID | None = None
    requirements: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None


class TenderUpdate(BaseModel):
    """Schema for partial tender update.

    Атрибуты:
        title (str | None): Название тендера.
        status (str | None): Текущий статус.
        budget (Decimal | None): Бюджет тендера.
        our_price (Decimal | None): Наша ценовая заявка.
        deadline (date | None): Крайний срок подачи заявки.
        execution_deadline (date | None): Крайний срок выполнения.
        assigned_to (uuid.UUID | None): ID ответственного менеджера.
        requirements (dict | None): Требования тендера.
        notes (str | None): Заметки.
    """

    title: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, max_length=50)
    budget: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    our_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    deadline: date | None = None
    execution_deadline: date | None = None
    assigned_to: uuid.UUID | None = None
    requirements: dict[str, Any] | None = None
    notes: str | None = None


class TenderResponse(BaseModel):
    """Schema for tender API response.

    Атрибуты:
        id (uuid.UUID): Уникальный идентификатор тендера.
        title (str): Название тендера.
        description (str | None): Описание тендера.
        source (str | None): Источник / площадка.
        budget (Decimal | None): Бюджет тендера.
        our_price (Decimal | None): Наша ценовая заявка.
        status (str): Текущий статус.
        deadline (date | None): Крайний срок подачи.
        execution_deadline (date | None): Крайний срок выполнения.
        assigned_to (uuid.UUID | None): ID ответственного менеджера.
        requirements (dict): Требования тендера.
        documents_url (str | None): Ссылка на тендерную документацию.
        notes (str | None): Заметки.
        created_at (datetime): Дата создания записи.
        updated_at (datetime): Дата последнего обновления.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None = None
    source: str | None = None
    budget: Decimal | None = None
    our_price: Decimal | None = None
    status: str
    deadline: date | None = None
    execution_deadline: date | None = None
    assigned_to: uuid.UUID | None = None
    requirements: dict[str, Any] = Field(default_factory=dict)
    documents_url: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
