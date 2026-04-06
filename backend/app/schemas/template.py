"""Schemas for task template entities.

Схемы валидации для создания, обновления и ответа
шаблонов задач с workflow, чек-листами и полями.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TemplateChecklistCreate(BaseModel):
    """Schema for a checklist item when creating/updating a template.

    Атрибуты:
        title: Название чек-листа.
        gate_transition: Блокируемый переход (например in_progress->testing).
        items: Список пунктов (строки или объекты с title).
    """

    title: str = Field(..., max_length=255)
    gate_transition: str | None = Field(default=None, max_length=200)
    items: list[str | dict[str, Any]] = Field(default_factory=list)


class TemplateCreate(BaseModel):
    """Schema for creating a task template.

    Атрибуты:
        name (str): Название шаблона.
        category (str): Категория — installation, maintenance, repair, inspection, general.
        description (str | None): Описание шаблона.
        workflow_definition (dict): JSON определение конечного автомата.
        required_fields (list): JSON массив обязательных полей.
        sla_config (dict): JSON конфигурация SLA.
        auto_warehouse (list): JSON правила автоматического списания.
        required_documents (dict): JSON правила обязательных документов.
        is_active (bool): Активен ли шаблон.
        checklists (list): Чек-листы шаблона.
    """

    name: str = Field(..., max_length=255)
    category: str = Field(default="general", max_length=100)
    description: str | None = None
    workflow_definition: dict[str, Any] = Field(default_factory=dict)
    required_fields: list[Any] = Field(default_factory=list)
    sla_config: dict[str, Any] = Field(default_factory=dict)
    auto_warehouse: list[Any] = Field(default_factory=list)
    required_documents: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True
    checklists: list[TemplateChecklistCreate] = Field(default_factory=list)


class TemplateUpdate(BaseModel):
    """Schema for partial template update.

    Атрибуты:
        name (str | None): Название шаблона.
        category (str | None): Категория.
        description (str | None): Описание.
        workflow_definition (dict | None): Определение workflow.
        sla_config (dict | None): Конфигурация SLA.
        is_active (bool | None): Активен ли шаблон.
        checklists (list | None): Чек-листы (при передаче заменяют текущие).
    """

    name: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    description: str | None = None
    workflow_definition: dict[str, Any] | None = None
    sla_config: dict[str, Any] | None = None
    is_active: bool | None = None
    checklists: list[TemplateChecklistCreate] | None = None


class TemplateStageResponse(BaseModel):
    """Schema for template stage in API response.

    Атрибуты:
        id (uuid.UUID): ID стадии.
        name (str): Название стадии.
        status_id (str): ID статуса из workflow.
        order (int): Порядковый номер.
        description (str | None): Описание стадии.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    status_id: str
    order: int
    description: str | None = None


class TemplateChecklistResponse(BaseModel):
    """Schema for template checklist in API response.

    Атрибуты:
        id (uuid.UUID): ID чек-листа.
        checklist_id (str): Уникальный идентификатор в шаблоне.
        title (str): Название чек-листа.
        gate_transition (str | None): Блокируемый переход.
        items (list): Пункты чек-листа.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    checklist_id: str
    title: str
    gate_transition: str | None = None
    items: list = Field(default_factory=list)


class TemplateFieldResponse(BaseModel):
    """Schema for template field in API response.

    Атрибуты:
        id (uuid.UUID): ID поля.
        key (str): Машинное имя поля.
        label (str): Человекочитаемая метка.
        field_type (str): Тип поля.
        is_required (bool): Обязательное ли поле.
        options (list | None): Опции для enum-типа.
        default_value (str | None): Значение по умолчанию.
        order (int): Порядок отображения.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    label: str
    field_type: str
    is_required: bool
    options: list | None = None
    default_value: str | None = None
    order: int


class TemplateResponse(BaseModel):
    """Schema for task template API response.

    Атрибуты:
        id (uuid.UUID): Уникальный идентификатор шаблона.
        name (str): Название шаблона.
        category (str): Категория.
        description (str | None): Описание.
        workflow_definition (dict): Определение workflow.
        required_fields (list): Обязательные поля.
        sla_config (dict): Конфигурация SLA.
        auto_warehouse (list): Правила списания.
        required_documents (dict): Обязательные документы.
        is_active (bool): Активен ли шаблон.
        stages (list): Стадии шаблона.
        checklists (list): Чек-листы шаблона.
        fields (list): Кастомные поля шаблона.
        created_at (datetime): Дата создания.
        updated_at (datetime): Дата обновления.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category: str
    description: str | None = None
    workflow_definition: dict[str, Any] = Field(default_factory=dict)
    required_fields: list[Any] = Field(default_factory=list)
    sla_config: dict[str, Any] = Field(default_factory=dict)
    auto_warehouse: list[Any] = Field(default_factory=list)
    required_documents: dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    stages: list[TemplateStageResponse] = Field(default_factory=list)
    checklists: list[TemplateChecklistResponse] = Field(default_factory=list)
    fields: list[TemplateFieldResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class InstantiateTemplate(BaseModel):
    """Schema for creating a task from a template.

    Атрибуты:
        client_id (uuid.UUID | None): ID клиента.
        deal_id (uuid.UUID | None): ID сделки.
        tender_id (uuid.UUID | None): ID тендера.
        board_id (uuid.UUID | None): ID доски.
        assigned_to (uuid.UUID | None): ID исполнителя.
        title (str | None): Переопределение заголовка задачи.
        custom_fields (dict): Начальные значения кастомных полей.
        observer_ids (list[uuid.UUID]): Наблюдатели для инстанцированной задачи.
    """

    client_id: uuid.UUID | None = None
    deal_id: uuid.UUID | None = None
    tender_id: uuid.UUID | None = None
    board_id: uuid.UUID | None = None
    assigned_to: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=500)
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    observer_ids: list[uuid.UUID] = Field(default_factory=list)


# ------------------------------------------------------------------
# Workflow definition (typed) — used by WorkflowEngine
# ------------------------------------------------------------------


class WorkflowRequiredDocument(BaseModel):
    """Required document rule for a workflow transition.

    Атрибуты:
        type: Тип документа (например, "photo", "signed_act").
        min_count: Минимальное количество документов этого типа.
    """

    type: str = Field(..., min_length=1, max_length=50)
    min_count: int = Field(default=1, ge=1, le=100)


class WorkflowTransition(BaseModel):
    """Typed workflow transition entry.

    Атрибуты:
        from_state: Исходный статус (в JSON хранится как ключ \"from\").
        to: Целевой статус (ключ \"to\").
        required_roles: Список ролей, которые могут выполнить переход.
        required_fields: Список полей, которые должны быть заполнены.
        required_checklists: Список чек-листов/гейтов, которые должны быть завершены.
        required_documents: Требуемые документы по типам и количеству.
        auto_actions: Автоматические действия (произвольные объекты).
    """

    model_config = ConfigDict(populate_by_name=True)

    from_state: str = Field(..., alias="from", min_length=1, max_length=100)
    to: str = Field(..., min_length=1, max_length=100)
    required_roles: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)
    required_checklists: list[str] = Field(default_factory=list)
    required_documents: list[WorkflowRequiredDocument] = Field(default_factory=list)
    auto_actions: list[Any] = Field(default_factory=list)


class WorkflowDefinition(BaseModel):
    """Typed workflow definition stored in TaskTemplate.workflow_definition.

    Атрибуты:
        initial_state: Начальный статус (опционально).
        states: Упорядоченный список статусов.
        transitions: Список допустимых переходов.
    """

    initial_state: str | None = None
    states: list[str] = Field(default_factory=list)
    transitions: list[WorkflowTransition] = Field(default_factory=list)
