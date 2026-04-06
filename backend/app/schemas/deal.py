"""Schemas for deals and pipeline stages.

Схемы валидации для создания, обновления и ответа
сделок и стадий воронки продаж.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DealStageCreate(BaseModel):
    """Schema for creating a pipeline stage.

    Атрибуты:
        name (str): Название стадии.
        order (int): Порядковый номер в воронке.
        color (str): HEX цвет для UI.
        is_won (bool): Признак выигранной стадии.
        is_lost (bool): Признак потерянной стадии.
    """

    name: str = Field(..., max_length=100)
    order: int
    color: str = Field(default="#6366f1", max_length=7)
    is_won: bool = False
    is_lost: bool = False


class DealStageResponse(BaseModel):
    """Schema for pipeline stage API response.

    Атрибуты:
        id (uuid.UUID): Уникальный идентификатор стадии.
        name (str): Название стадии.
        order (int): Порядковый номер.
        color (str): HEX цвет.
        is_won (bool): Признак выигранной стадии.
        is_lost (bool): Признак потерянной стадии.
        created_at (datetime): Дата создания записи.
        updated_at (datetime): Дата последнего обновления.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    order: int
    color: str
    is_won: bool
    is_lost: bool
    created_at: datetime
    updated_at: datetime


class DealCreate(BaseModel):
    """Schema for creating a new deal.

    Атрибуты:
        client_id (uuid.UUID): ID клиента.
        title (str): Название сделки.
        amount (Decimal): Сумма сделки.
        stage_id (uuid.UUID): ID текущей стадии воронки.
        assigned_to (uuid.UUID | None): ID ответственного менеджера.
        expected_close (date | None): Ожидаемая дата закрытия.
        source (str | None): Источник сделки.
    """

    client_id: uuid.UUID
    title: str = Field(..., max_length=500)
    amount: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    stage_id: uuid.UUID
    assigned_to: uuid.UUID | None = None
    expected_close: date | None = None
    source: str | None = Field(default=None, max_length=100)


class DealUpdate(BaseModel):
    """Schema for partial deal update.

    Атрибуты:
        title (str | None): Название сделки.
        amount (Decimal | None): Сумма сделки.
        stage_id (uuid.UUID | None): ID стадии воронки.
        assigned_to (uuid.UUID | None): ID ответственного менеджера.
        expected_close (date | None): Ожидаемая дата закрытия.
    """

    title: str | None = Field(default=None, max_length=500)
    amount: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    stage_id: uuid.UUID | None = None
    assigned_to: uuid.UUID | None = None
    expected_close: date | None = None


class DealResponse(BaseModel):
    """Schema for deal API response.

    Атрибуты:
        id (uuid.UUID): Уникальный идентификатор сделки.
        client_id (uuid.UUID): ID клиента.
        title (str): Название сделки.
        description (str | None): Описание.
        amount (Decimal): Сумма сделки.
        stage_id (uuid.UUID): ID текущей стадии.
        assigned_to (uuid.UUID | None): ID ответственного менеджера.
        expected_close (date | None): Ожидаемая дата закрытия.
        source (str | None): Источник сделки.
        created_at (datetime): Дата создания записи.
        updated_at (datetime): Дата последнего обновления.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    title: str
    description: str | None = None
    amount: Decimal
    stage_id: uuid.UUID
    assigned_to: uuid.UUID | None = None
    expected_close: date | None = None
    source: str | None = None
    created_at: datetime
    updated_at: datetime
