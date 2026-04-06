"""Schemas for work time tracking entries and timer controls.

Схемы валидации для создания, обновления и ответа
записей рабочего времени с поддержкой ручного ввода и таймера.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TimeEntryCreate(BaseModel):
    """Schema for creating a time entry.

    Атрибуты:
        task_id (uuid.UUID): ID задачи.
        started_at (datetime | None): Время начала работы.
        ended_at (datetime | None): Время окончания работы.
        duration_minutes (int | None): Длительность в минутах (ручной ввод).
        entry_type (str): Тип записи — manual или timer.
        is_billable (bool): Оплачиваемое время.
        notes (str | None): Комментарий.
    """

    task_id: uuid.UUID
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=0)
    entry_type: str = Field(default="manual", max_length=20)
    is_billable: bool = True
    notes: str | None = None


class TimeEntryUpdate(BaseModel):
    """Schema for partial time entry update.

    Атрибуты:
        ended_at (datetime | None): Время окончания работы.
        duration_minutes (int | None): Длительность в минутах.
        notes (str | None): Комментарий.
    """

    ended_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=0)
    notes: str | None = None


class TimeEntryResponse(BaseModel):
    """Schema for time entry API response.

    Атрибуты:
        id (uuid.UUID): Уникальный идентификатор записи.
        task_id (uuid.UUID): ID задачи.
        user_id (uuid.UUID): ID сотрудника.
        started_at (datetime | None): Время начала работы.
        ended_at (datetime | None): Время окончания работы.
        duration_minutes (int): Длительность в минутах.
        entry_type (str): Тип записи.
        is_billable (bool): Оплачиваемое время.
        notes (str | None): Комментарий.
        created_at (datetime): Дата создания записи.
        updated_at (datetime): Дата последнего обновления.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    user_id: uuid.UUID
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_minutes: int
    entry_type: str
    is_billable: bool
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class TimerStart(BaseModel):
    """Schema for starting a work timer on a task.

    Атрибуты:
        task_id (uuid.UUID): ID задачи для отслеживания.
        notes (str | None): Комментарий при старте.
    """

    task_id: uuid.UUID
    notes: str | None = None


class TimerStop(BaseModel):
    """Schema for stopping the running timer.

    Атрибуты:
        notes (str | None): Комментарий при остановке.
    """

    notes: str | None = None
