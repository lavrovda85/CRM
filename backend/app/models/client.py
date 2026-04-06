"""Client and contact models for CRM.

Клиенты могут быть физическими лицами или организациями,
с привязкой контактных лиц и координат объекта.
"""

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, TenantMixin


class Client(TenantMixin, BaseModel):
    """Client entity representing a customer or organization.

    Атрибуты:
        name: Название клиента / организации.
        client_type: Тип (individual, organization).
        address: Основной адрес.
        coordinates: GPS координаты {lat, lng}.
        phone: Основной телефон.
        email: Email клиента.
        inn: ИНН (для организаций).
        metadata: Дополнительные данные.
        notes: Заметки менеджера.
    """

    __tablename__ = "clients"

    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    client_type: Mapped[str] = mapped_column(String(50), nullable=False, default="individual")
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    coordinates: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    inn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    extra_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    contacts = relationship("ClientContact", back_populates="client", cascade="all, delete-orphan")
    deals = relationship("Deal", back_populates="client")
    tasks = relationship("Task", back_populates="client")


class ClientContact(BaseModel):
    """Contact person associated with a client.

    Атрибуты:
        client_id: ID клиента.
        full_name: ФИО контактного лица.
        position: Должность.
        phone: Телефон.
        email: Email.
        is_primary: Основной контакт.
    """

    __tablename__ = "client_contacts"

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_primary: Mapped[bool] = mapped_column(default=False)

    client = relationship("Client", back_populates="contacts")
