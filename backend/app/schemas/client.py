"""Schemas for client and contact person entities.

Схемы валидации для создания, обновления и ответа
клиентов (физ. лица / организации) и контактных лиц.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ClientCreate(BaseModel):
    """Schema for creating a new client.

    Атрибуты:
        name (str): Название клиента / организации.
        client_type (str): Тип клиента — individual или organization.
        address (str | None): Основной адрес.
        phone (str | None): Контактный телефон.
        email (str | None): Email адрес.
        inn (str | None): ИНН (для организаций).
        primary_contact_name (str | None): Контактное лицо (создаётся как основной ClientContact).
        kpp / ogrn / ogrnip / bik / bank_*: Реквизиты юрлица (хранятся в ``extra_data``).
        coordinates (dict | None): GPS координаты {lat, lng}.
        extra_data (dict): Произвольные дополнительные данные.
        notes (str | None): Заметки менеджера.
    """

    name: str = Field(..., max_length=500)
    client_type: str = Field(default="individual", max_length=50)
    address: str | None = None
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    inn: str | None = Field(default=None, max_length=20)
    primary_contact_name: str | None = Field(default=None, max_length=255)
    kpp: str | None = Field(default=None, max_length=20)
    ogrn: str | None = Field(default=None, max_length=20)
    ogrnip: str | None = Field(default=None, max_length=20)
    bik: str | None = Field(default=None, max_length=20)
    bank_account: str | None = Field(default=None, max_length=50)
    corr_account: str | None = Field(default=None, max_length=50)
    bank_name: str | None = Field(default=None, max_length=500)
    coordinates: dict[str, Any] | None = None
    extra_data: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None


class ClientUpdate(BaseModel):
    """Schema for partial client update.

    Атрибуты:
        name (str | None): Название клиента / организации.
        address (str | None): Основной адрес.
        phone (str | None): Контактный телефон.
        email (str | None): Email адрес.
        inn (str | None): ИНН.
        kpp / ogrn / ogrnip / bik / bank_*: Реквизиты (мержатся в ``extra_data``).
        coordinates (dict | None): GPS координаты {lat, lng}.
        extra_data (dict | None): Произвольные дополнительные данные.
        notes (str | None): Заметки менеджера.
    """

    name: str | None = Field(default=None, max_length=500)
    address: str | None = None
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    inn: str | None = Field(default=None, max_length=20)
    kpp: str | None = Field(default=None, max_length=20)
    ogrn: str | None = Field(default=None, max_length=20)
    ogrnip: str | None = Field(default=None, max_length=20)
    bik: str | None = Field(default=None, max_length=20)
    bank_account: str | None = Field(default=None, max_length=50)
    corr_account: str | None = Field(default=None, max_length=50)
    bank_name: str | None = Field(default=None, max_length=500)
    coordinates: dict[str, Any] | None = None
    extra_data: dict[str, Any] | None = None
    notes: str | None = None


class ClientContactCreate(BaseModel):
    """Schema for adding a contact person to a client.

    Атрибуты:
        full_name (str): ФИО контактного лица.
        position (str | None): Должность.
        phone (str | None): Телефон.
        email (str | None): Email.
        is_primary (bool): Признак основного контакта.
    """

    full_name: str = Field(..., max_length=255)
    position: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    is_primary: bool = False


class ClientContactResponse(BaseModel):
    """Schema for contact person API response.

    Атрибуты:
        id (uuid.UUID): Уникальный идентификатор контакта.
        client_id (uuid.UUID): ID клиента-владельца.
        full_name (str): ФИО контактного лица.
        position (str | None): Должность.
        phone (str | None): Телефон.
        email (str | None): Email.
        is_primary (bool): Признак основного контакта.
        created_at (datetime): Дата создания записи.
        updated_at (datetime): Дата последнего обновления.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    full_name: str
    position: str | None = None
    phone: str | None = None
    email: str | None = None
    is_primary: bool
    created_at: datetime
    updated_at: datetime


class ClientResponse(BaseModel):
    """Schema for client API response.

    Атрибуты:
        id (uuid.UUID): Уникальный идентификатор клиента.
        name (str): Название клиента / организации.
        client_type (str): Тип клиента.
        address (str | None): Основной адрес.
        phone (str | None): Контактный телефон.
        email (str | None): Email адрес.
        inn (str | None): ИНН.
        kpp / ogrn / ogrnip / bik / bank_*: Дубли из ``extra_data`` для форм.
        coordinates (dict | None): GPS координаты {lat, lng}.
        extra_data (dict): Дополнительные данные.
        notes (str | None): Заметки менеджера.
        contacts (list[ClientContactResponse]): Контактные лица.
        created_at (datetime): Дата создания записи.
        updated_at (datetime): Дата последнего обновления.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    client_type: str
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    inn: str | None = None
    kpp: str | None = None
    ogrn: str | None = None
    ogrnip: str | None = None
    bik: str | None = None
    bank_account: str | None = None
    corr_account: str | None = None
    bank_name: str | None = None
    coordinates: dict[str, Any] | None = None
    extra_data: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    contacts: list[ClientContactResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
