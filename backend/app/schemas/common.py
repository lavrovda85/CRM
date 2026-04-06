"""Common base schemas reused across the application.

Базовые Pydantic-схемы, предоставляющие общие поля
(UUID, таймстемпы) и стандартные обёртки ответов API.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UUIDModel(BaseModel):
    """Base schema providing a UUID primary key.

    Атрибуты:
        id: UUID первичный ключ сущности.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class TimestampModel(BaseModel):
    """Base schema providing created_at / updated_at timestamps.

    Атрибуты:
        created_at: Дата и время создания записи.
        updated_at: Дата и время последнего обновления.
    """

    model_config = ConfigDict(from_attributes=True)

    created_at: datetime
    updated_at: datetime


class BaseResponse(UUIDModel, TimestampModel):
    """Standard response base combining UUID and timestamps.

    Атрибуты:
        id: UUID первичный ключ.
        created_at: Дата создания.
        updated_at: Дата обновления.
    """


class MessageResponse(BaseModel):
    """Simple text message response.

    Атрибуты:
        message: Текст сообщения.
    """

    message: str


class ErrorDetail(BaseModel):
    """Structured error detail payload.

    Атрибуты:
        code: Машиночитаемый код ошибки.
        message: Человекочитаемое описание ошибки.
        details: Дополнительные данные об ошибке.
    """

    code: str
    message: str
    details: dict | None = Field(default=None)


class ErrorResponse(BaseModel):
    """Standardized error response envelope.

    Атрибуты:
        error: Структурированные данные об ошибке.
    """

    error: ErrorDetail
