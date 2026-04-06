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
    tender_link: str = Field(..., max_length=1000)
    customer_id: uuid.UUID | None = None
    guarantee_amount: Decimal = Field(..., ge=0, decimal_places=2)
    max_price: Decimal = Field(..., ge=0, decimal_places=2)
    min_price: Decimal = Field(..., ge=0, decimal_places=2)
    trade_start_at: datetime = Field(...)
    trade_end_at: datetime | None = None
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
    tender_link: str | None = Field(default=None, max_length=1000)
    customer_id: uuid.UUID | None = None
    guarantee_amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    max_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    min_price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    trade_start_at: datetime | None = None
    trade_end_at: datetime | None = None
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
    tender_link: str | None = None
    customer_id: uuid.UUID | None = None
    customer_name: str | None = None
    guarantee_amount: Decimal | None = None
    max_price: Decimal | None = None
    min_price: Decimal | None = None
    trade_start_at: datetime | None = None
    trade_end_at: datetime | None = None
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
    tender_analysis: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class TenderChecklistItemResponse(BaseModel):
    """Tender checklist item response.

    Attributes:
        id: Checklist item ID.
        title: Item title.
        item_type: Machine-readable type.
        is_completed: Whether the item is completed.
        completed_by: User ID of completer (nullable).
        completed_at: Completion timestamp (nullable).
        calculation_task_id: Linked task id for calculation item (nullable).
        scheduled_offset_hours: Offset (hours) from `trade_start_at` for scheduled checks (nullable).
    """

    id: uuid.UUID
    title: str
    item_type: str
    is_completed: bool
    completed_by: uuid.UUID | None = None
    completed_at: datetime | None = None
    calculation_task_id: uuid.UUID | None = None
    scheduled_offset_hours: int | None = None

    model_config = ConfigDict(from_attributes=True)


class TenderChecklistResponse(BaseModel):
    """Tender checklist response.

    Attributes:
        id: Checklist ID.
        title: Checklist title.
        items: Checklist items.
    """

    id: uuid.UUID
    title: str
    items: list[TenderChecklistItemResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class TenderBillOfWorksPatch(BaseModel):
    """Client-edited bill of works merged into ``tender_analysis`` JSON."""

    bill_of_works: list[dict[str, Any]] = Field(default_factory=list)
    bill_of_works_notes: str | None = Field(default=None, max_length=8000)


class TenderTasksFromBillRequest(BaseModel):
    """Create one task per selected row of the current bill of works."""

    assigned_to: uuid.UUID | None = None
    row_indices: list[int] | None = Field(
        default=None,
        description="If set, only these zero-based indices; otherwise all rows.",
    )


class TenderTransitionRequest(BaseModel):
    """Request body for moving a tender along the pipeline.

    Attributes:
        to_status: Target status (must be allowed from current).
        reason: Optional note appended to tender notes on transition.
    """

    to_status: str = Field(..., min_length=1, max_length=50)
    reason: str | None = Field(default=None, max_length=2000)


class TenderChecklistItemUpdate(BaseModel):
    """Update payload for tender checklist item.

    Attributes:
        calculation_task_id: Task ID to link with calculation item.
        is_completed: Optional completion flag.
    """

    calculation_task_id: uuid.UUID | None = None
    is_completed: bool | None = None
