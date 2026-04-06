"""Schemas for equipment and depreciation entities.

Схемы валидации для учёта оборудования, амортизации
и операций списания.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EquipmentCreate(BaseModel):
    """Schema for registering new equipment.

    Атрибуты:
        name (str): Название оборудования.
        serial_number (str): Серийный номер.
        category (str): Категория — power_tool, measuring, hand_tool, safety, vehicle.
        purchase_price (Decimal): Цена покупки.
        purchase_date (date): Дата покупки.
        service_life_months (int): Расчётный срок службы в месяцах.
        assigned_to (uuid.UUID | None): Закреплено за сотрудником.
        location (str | None): Местонахождение.
        notes (str | None): Заметки.
    """

    name: str = Field(..., max_length=500)
    serial_number: str = Field(..., max_length=200)
    category: str = Field(default="hand_tool", max_length=100)
    purchase_price: Decimal = Field(..., ge=0, decimal_places=2)
    purchase_date: date
    service_life_months: int = Field(default=36, ge=1)
    assigned_to: uuid.UUID | None = None
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class EquipmentUpdate(BaseModel):
    """Schema for partial equipment update.

    Атрибуты:
        name (str | None): Название оборудования.
        category (str | None): Категория.
        status (str | None): Статус — active, maintenance, written_off, lost.
        assigned_to (uuid.UUID | None): Закреплено за сотрудником.
        location (str | None): Местонахождение.
        notes (str | None): Заметки.
    """

    name: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default=None, max_length=100)
    status: str | None = Field(default=None, max_length=50)
    assigned_to: uuid.UUID | None = None
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class EquipmentWriteOff(BaseModel):
    """Schema for writing off equipment.

    Атрибуты:
        reason (str): Причина списания.
    """

    reason: str


class DepreciationRecordResponse(BaseModel):
    """Schema for depreciation record in API response.

    Атрибуты:
        id (uuid.UUID): ID записи.
        period_date (date): Дата периода начисления.
        amount (Decimal): Сумма амортизации.
        accumulated (Decimal): Накопленная амортизация.
        remaining_value (Decimal): Остаточная стоимость.
        method (str): Метод начисления.
        notes (str | None): Комментарий.
        created_at (datetime): Дата создания.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    period_date: date
    amount: Decimal
    accumulated: Decimal
    remaining_value: Decimal
    method: str
    notes: str | None = None
    created_at: datetime


class EquipmentResponse(BaseModel):
    """Schema for equipment API response.

    Атрибуты:
        id (uuid.UUID): Уникальный идентификатор.
        name (str): Название оборудования.
        serial_number (str): Серийный номер.
        category (str): Категория.
        purchase_price (Decimal): Цена покупки.
        purchase_date (date): Дата покупки.
        service_life_months (int): Срок службы в месяцах.
        current_value (Decimal): Текущая остаточная стоимость.
        status (str): Статус оборудования.
        assigned_to (uuid.UUID | None): Закреплено за сотрудником.
        location (str | None): Местонахождение.
        notes (str | None): Заметки.
        created_at (datetime): Дата создания.
        updated_at (datetime): Дата обновления.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    serial_number: str
    category: str
    purchase_price: Decimal
    purchase_date: date
    service_life_months: int
    current_value: Decimal
    status: str
    assigned_to: uuid.UUID | None = None
    location: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class EquipmentDetailResponse(EquipmentResponse):
    """Extended equipment response with depreciation records.

    Атрибуты:
        depreciation_records (list[DepreciationRecordResponse]): Записи амортизации.
    """

    depreciation_records: list[DepreciationRecordResponse] = Field(default_factory=list)
