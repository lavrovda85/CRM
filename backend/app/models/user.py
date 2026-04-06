"""User model representing system employees.

Пользователи синхронизируются с Keycloak и содержат
дополнительные данные для расчёта зарплаты и трекинга.
"""

from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class User(BaseModel):
    """Employee/user entity synced with Keycloak.

    Атрибуты:
        keycloak_id: UUID пользователя в Keycloak.
        email: Email адрес (уникальный).
        full_name: Полное имя сотрудника.
        phone: Номер телефона.
        role: Основная роль (admin, manager, engineer, warehouse_manager, accountant).
        position: Должность.
        telegram_chat_id: ID чата Telegram для уведомлений.
        salary_config: JSON конфигурация расчёта зарплаты.
        is_active: Активен ли пользователь в системе.
    """

    __tablename__ = "users"

    keycloak_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="engineer")
    position: Mapped[str] = mapped_column(String(255), nullable=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    salary_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    assigned_tasks = relationship("Task", back_populates="assignee", foreign_keys="Task.assigned_to")
    time_entries = relationship("TimeEntry", back_populates="user")
    comments = relationship("Comment", back_populates="author")
