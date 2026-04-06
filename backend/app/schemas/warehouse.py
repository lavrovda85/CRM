"""Schemas for warehouse items, movements, and reservations.

Схемы валидации для складских позиций, операций движения
(приход, расход, списание, перемещение) и резервирования под задачи.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class WarehouseItemCreate(BaseModel):
    """Schema for creating a warehouse item.

    Атрибуты:
        name (str): Название материала / товара.
        sku (str): Артикул (уникальный).
        category (str): Категория — materials, tools, consumables, equipment.
        unit (str): Единица измерения — pcs, m, kg, l.
        quantity (Decimal): Начальное количество на складе.
        min_quantity (Decimal): Минимальный остаток для уведомлений.
        price (Decimal): Цена за единицу.
        description (str | None): Описание.
        location (str | None): Место хранения на складе.
    """

    name: str = Field(..., max_length=500)
    sku: str = Field(..., max_length=100)
    category: str = Field(default="materials", max_length=100)
    unit: str = Field(default="pcs", max_length=20)
    quantity: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=3)
    min_quantity: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=3)
    price: Decimal = Field(default=Decimal("0"), ge=0, decimal_places=2)
    description: str | None = None
    location: str | None = Field(default=None, max_length=255)


class WarehouseItemUpdate(BaseModel):
    """Schema for partial warehouse item update.

    Атрибуты:
        name (str | None): Название материала / товара.
        quantity (Decimal | None): Количество на складе.
        min_quantity (Decimal | None): Минимальный остаток.
        price (Decimal | None): Цена за единицу.
        location (str | None): Место хранения.
        description (str | None): Описание.
    """

    name: str | None = Field(default=None, max_length=500)
    quantity: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    min_quantity: Decimal | None = Field(default=None, ge=0, decimal_places=3)
    price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    location: str | None = Field(default=None, max_length=255)
    description: str | None = None


class WarehouseItemResponse(BaseModel):
    """Schema for warehouse item API response.

    Атрибуты:
        id (uuid.UUID): Уникальный идентификатор позиции.
        name (str): Название материала / товара.
        sku (str): Артикул.
        category (str): Категория.
        unit (str): Единица измерения.
        quantity (Decimal): Текущее количество.
        reserved_quantity (Decimal): Зарезервированное количество.
        min_quantity (Decimal): Минимальный остаток.
        price (Decimal): Цена за единицу.
        description (str | None): Описание.
        location (str | None): Место хранения.
        created_at (datetime): Дата создания записи.
        updated_at (datetime): Дата последнего обновления.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    sku: str
    category: str
    unit: str
    quantity: Decimal
    reserved_quantity: Decimal
    min_quantity: Decimal
    price: Decimal
    description: str | None = None
    location: str | None = None
    created_at: datetime
    updated_at: datetime


class WarehouseMovementCreate(BaseModel):
    """Schema for creating a warehouse movement.

    Атрибуты:
        item_id (uuid.UUID): ID складской позиции.
        movement_type (str): Тип движения — intake, consumption, write_off, transfer, return.
        quantity (Decimal): Количество (положительное).
        task_id (uuid.UUID | None): ID задачи (при привязке к задаче).
        reason (str | None): Причина / комментарий.
        destination (str | None): Место назначения (для перемещений).
    """

    item_id: uuid.UUID
    movement_type: str = Field(..., max_length=50)
    quantity: Decimal = Field(..., gt=0, decimal_places=3)
    task_id: uuid.UUID | None = None
    reason: str | None = None
    destination: str | None = Field(default=None, max_length=255)


class WarehouseMovementResponse(BaseModel):
    """Schema for warehouse movement API response.

    Атрибуты:
        id (uuid.UUID): Уникальный идентификатор операции.
        item_id (uuid.UUID): ID складской позиции.
        task_id (uuid.UUID | None): ID задачи.
        user_id (uuid.UUID): ID пользователя, выполнившего операцию.
        movement_type (str): Тип движения.
        quantity (Decimal): Количество.
        unit_price (Decimal | None): Цена за единицу на момент операции.
        reason (str | None): Причина / комментарий.
        destination (str | None): Место назначения.
        created_at (datetime): Дата создания записи.
        updated_at (datetime): Дата последнего обновления.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    task_id: uuid.UUID | None = None
    user_id: uuid.UUID
    movement_type: str
    quantity: Decimal
    unit_price: Decimal | None = None
    reason: str | None = None
    destination: str | None = None
    created_at: datetime
    updated_at: datetime


class ReservationCreate(BaseModel):
    """Schema for reserving warehouse items for a task.

    Атрибуты:
        item_id (uuid.UUID): ID складской позиции.
        task_id (uuid.UUID): ID задачи.
        quantity (Decimal): Количество для резервирования.
    """

    item_id: uuid.UUID
    task_id: uuid.UUID
    quantity: Decimal = Field(..., gt=0, decimal_places=3)


class ReservationResponse(BaseModel):
    """Schema for reservation API response.

    Атрибуты:
        id (uuid.UUID): Уникальный идентификатор резерва.
        item_id (uuid.UUID): ID складской позиции.
        task_id (uuid.UUID): ID задачи.
        quantity (Decimal): Зарезервированное количество.
        status (str): Статус резерва — reserved, consumed, cancelled.
        created_at (datetime): Дата создания записи.
        updated_at (datetime): Дата последнего обновления.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    item_id: uuid.UUID
    task_id: uuid.UUID
    quantity: Decimal
    status: str
    created_at: datetime
    updated_at: datetime
