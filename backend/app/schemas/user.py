"""Pydantic v2 schemas for user management.

Схемы для создания, обновления и ответа API
по управлению пользователями системы.
"""

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import BaseResponse

VALID_ROLES = {"admin", "manager", "engineer", "warehouse_manager", "accountant"}


class UserKeycloakSyncRequest(BaseModel):
    """Password to apply in Keycloak when reconciling an existing CRM user."""

    password: str = Field(..., min_length=6, max_length=128)


class UserCreate(BaseModel):
    """Schema for creating a new user.

    Атрибуты:
        email: Email (уникальный).
        full_name: Полное имя.
        password: Пароль только для Keycloak (в PostgreSQL не хранится).
        role: Роль в системе.
        phone: Телефон.
        position: Должность.
    """

    email: str = Field(..., min_length=3, max_length=255)
    full_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    role: str = Field(default="engineer", pattern=r"^(admin|manager|engineer|warehouse_manager|accountant)$")
    phone: str | None = None
    position: str | None = None


class UserSelfUpdate(BaseModel):
    """Fields the authenticated user may change on their own profile (no admin).

    Атрибуты:
        full_name: Отображаемое имя.
        phone: Телефон (пустая строка снимает значение).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=32)

    @field_validator("phone", mode="before")
    @classmethod
    def _empty_phone_to_none(cls, v: object) -> object:
        if v == "" or v is None:
            return None
        return v


class UserUpdate(BaseModel):
    """Schema for partial user update.

    Атрибуты:
        full_name: Новое имя.
        role: Новая роль.
        phone: Новый телефон.
        position: Новая должность.
        is_active: Статус активности.
        salary_config: Конфигурация расчёта зарплаты.
        password: Новый пароль в Keycloak (в PostgreSQL не сохраняется).
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: str | None = Field(default=None, pattern=r"^(admin|manager|engineer|warehouse_manager|accountant)$")
    phone: str | None = None
    position: str | None = None
    avatar_url: str | None = None
    is_active: bool | None = None
    salary_config: dict[str, Any] | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)

    @field_validator("password", mode="before")
    @classmethod
    def _empty_password_to_none(cls, v: object) -> object:
        if v == "" or v is None:
            return None
        return v


class UserResponse(BaseResponse):
    """Standard user API response.

    Атрибуты:
        keycloak_id: ID в Keycloak.
        email: Email.
        full_name: Полное имя.
        phone: Телефон.
        role: Роль.
        position: Должность.
        is_active: Активен.
        telegram_chat_id: Telegram ID.
    """

    keycloak_id: str
    email: str
    full_name: str
    phone: str | None = None
    role: str
    position: str | None = None
    avatar_url: str | None = None
    is_active: bool
    telegram_chat_id: str | None = None


class UserListItem(BaseModel):
    """Compact user for dropdowns and lists.

    Атрибуты:
        id: UUID.
        full_name: Имя.
        email: Email.
        role: Роль.
        is_active: Активен.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str
    role: str
    is_active: bool
    avatar_url: str | None = None
