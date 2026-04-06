"""Task template models defining reusable task blueprints.

Шаблоны задач содержат определение workflow, чек-листов,
обязательных полей и SLA конфигурацию.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel, TenantMixin


class TaskTemplate(TenantMixin, BaseModel):
    """Reusable task template with workflow, checklists, and field definitions.

    Атрибуты:
        name: Название шаблона.
        category: Категория (installation, maintenance, repair, inspection).
        description: Описание шаблона.
        workflow_definition: JSON определение конечного автомата (states + transitions).
        required_fields: JSON массив обязательных полей с типами.
        sla_config: JSON конфигурация SLA (max_duration, warning_at_percent).
        auto_warehouse: JSON правила автоматического списания со склада.
        required_documents: JSON правила обязательных документов по стадиям.
        is_active: Активен ли шаблон.
    """

    __tablename__ = "task_templates"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="general", index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    workflow_definition: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    required_fields: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    sla_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    auto_warehouse: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    required_documents: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    stages = relationship("TemplateStage", back_populates="template", cascade="all, delete-orphan",
                          order_by="TemplateStage.order")
    checklists = relationship("TemplateChecklist", back_populates="template", cascade="all, delete-orphan")
    fields = relationship("TemplateField", back_populates="template", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="template")


class TemplateStage(BaseModel):
    """Stage definition within a task template.

    Атрибуты:
        template_id: ID шаблона.
        name: Название стадии.
        status_id: ID статуса из workflow_definition.
        order: Порядковый номер.
        description: Описание стадии.
    """

    __tablename__ = "template_stages"

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("task_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status_id: Mapped[str] = mapped_column(String(100), nullable=False)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    template = relationship("TaskTemplate", back_populates="stages")


class TemplateChecklist(BaseModel):
    """Checklist definition within a task template.

    Атрибуты:
        template_id: ID шаблона.
        checklist_id: Уникальный идентификатор чек-листа в шаблоне.
        title: Название чек-листа.
        gate_transition: Переход, который блокируется до заполнения (from->to).
        items: JSON массив пунктов чек-листа.
    """

    __tablename__ = "template_checklists"

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("task_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    checklist_id: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    gate_transition: Mapped[str | None] = mapped_column(String(200), nullable=True)
    items: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    template = relationship("TaskTemplate", back_populates="checklists")


class TemplateField(BaseModel):
    """Custom field definition within a task template.

    Атрибуты:
        template_id: ID шаблона.
        key: Машинное имя поля.
        label: Человекочитаемая метка.
        field_type: Тип поля (string, integer, decimal, enum, reference, address, date).
        is_required: Обязательное поле.
        options: JSON опции для enum-типа.
        ref_table: Таблица-справочник для reference-типа.
        default_value: Значение по умолчанию.
        order: Порядок отображения.
    """

    __tablename__ = "template_fields"

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("task_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    field_type: Mapped[str] = mapped_column(String(50), nullable=False, default="string")
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    options: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    ref_table: Mapped[str | None] = mapped_column(String(100), nullable=True)
    default_value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    template = relationship("TaskTemplate", back_populates="fields")
