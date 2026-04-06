"""Pydantic v2 schemas for tasks: CRUD, transitions, and responses.

Схемы для создания, обновления, перехода статуса задач,
а также для различных уровней детализации ответов API.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import BaseResponse


class TaskCreate(BaseModel):
    """Schema for creating a new task.

    Атрибуты:
        template_id: ID шаблона задачи.
        client_id: ID клиента (опционально).
        deal_id: ID сделки (опционально).
        tender_id: ID тендера (опционально).
        assigned_to: ID назначенного исполнителя (опционально).
        title: Заголовок задачи.
        description: Описание задачи.
        priority: Приоритет (low, medium, high, critical).
        custom_fields: Значения кастомных полей.
        due_date: Крайний срок выполнения.
        board_id: ID доски для отображения.
    """

    model_config = ConfigDict(from_attributes=True)

    template_id: uuid.UUID
    client_id: uuid.UUID | None = None
    deal_id: uuid.UUID | None = None
    tender_id: uuid.UUID | None = None
    assigned_to: uuid.UUID | None = None
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    priority: str = Field(default="medium", pattern=r"^(low|medium|high|critical)$")
    custom_fields: dict[str, Any] | None = Field(default=None)
    due_date: datetime | None = None
    board_id: uuid.UUID | None = None


class TaskUpdate(BaseModel):
    """Schema for partial task update (non-status fields).

    Атрибуты:
        title: Новый заголовок.
        description: Новое описание.
        priority: Новый приоритет.
        assigned_to: Новый исполнитель.
        custom_fields: Обновлённые кастомные поля (merge с существующими).
        due_date: Новый крайний срок.
        board_id: Новая доска.
    """

    model_config = ConfigDict(from_attributes=True)

    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    priority: str | None = Field(default=None, pattern=r"^(low|medium|high|critical)$")
    assigned_to: uuid.UUID | None = None
    custom_fields: dict[str, Any] | None = None
    due_date: datetime | None = None
    board_id: uuid.UUID | None = None


class TaskStatusTransition(BaseModel):
    """Schema for requesting a task status transition via the workflow engine.

    Атрибуты:
        to_status: Целевой статус, в который нужно перевести задачу.
        reason: Комментарий / причина перехода (опционально).
        checklist_data: Дополнительные данные по чек-листам, передаваемые
                        вместе с переходом (например, отметки о выполнении).
    """

    to_status: str = Field(..., min_length=1, max_length=100)
    reason: str | None = None
    checklist_data: dict[str, Any] | None = None


class UserSummary(BaseModel):
    """Compact user reference for embedding in task responses.

    Атрибуты:
        id: UUID пользователя.
        full_name: Полное имя.
        email: Email.
        role: Роль.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str
    email: str
    role: str


class TemplateSummary(BaseModel):
    """Compact template reference for embedding in task responses.

    Атрибуты:
        id: UUID шаблона.
        name: Название шаблона.
        category: Категория.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    category: str


class TaskResponse(BaseResponse):
    """Standard task response with relation summaries.

    Атрибуты:
        template_id: ID шаблона.
        board_id: ID доски.
        client_id: ID клиента.
        deal_id: ID сделки.
        tender_id: ID тендера.
        assigned_to: ID исполнителя.
        created_by: ID создателя.
        title: Заголовок.
        description: Описание.
        status: Текущий статус.
        priority: Приоритет.
        custom_fields: Значения кастомных полей.
        due_date: Крайний срок.
        started_at: Время начала.
        completed_at: Время завершения.
        sla_deadline: Дедлайн SLA.
        assignee: Краткая информация об исполнителе.
        template: Краткая информация о шаблоне.
    """

    template_id: uuid.UUID | None = None
    board_id: uuid.UUID | None = None
    client_id: uuid.UUID | None = None
    deal_id: uuid.UUID | None = None
    tender_id: uuid.UUID | None = None
    assigned_to: uuid.UUID | None = None
    created_by: uuid.UUID | None = None
    title: str
    description: str | None = None
    status: str
    priority: str
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    due_date: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    sla_deadline: datetime | None = None
    assignee: UserSummary | None = None
    template: TemplateSummary | None = None


class TaskListResponse(BaseModel):
    """Compact task representation for list views.

    Атрибуты:
        id: UUID задачи.
        title: Заголовок.
        status: Текущий статус.
        priority: Приоритет.
        assigned_to: ID исполнителя.
        assignee_name: Имя исполнителя.
        due_date: Крайний срок.
        created_at: Дата создания.
        template_name: Название шаблона.
        client_id: ID клиента.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    status: str
    priority: str
    assigned_to: uuid.UUID | None = None
    assignee_name: str | None = None
    due_date: datetime | None = None
    created_at: datetime
    template_name: str | None = None
    client_id: uuid.UUID | None = None


class ChecklistItemResponse(BaseModel):
    """Checklist item nested in task detail.

    Атрибуты:
        id: UUID записи.
        title: Текст пункта.
        is_completed: Отметка о выполнении.
        completed_by: ID пользователя, выполнившего пункт.
        completed_at: Время выполнения.
        order: Порядок.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    is_completed: bool
    completed_by: uuid.UUID | None = None
    completed_at: datetime | None = None
    order: int = 0


class ChecklistResponse(BaseModel):
    """Checklist nested in task detail.

    Атрибуты:
        id: UUID чек-листа.
        title: Название.
        gate_transition: Блокируемый переход.
        is_completed: Все пункты завершены.
        items: Список пунктов.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    gate_transition: str | None = None
    is_completed: bool
    items: list[ChecklistItemResponse] = Field(default_factory=list)


class CommentResponse(BaseModel):
    """Comment nested in task detail.

    Атрибуты:
        id: UUID комментария.
        author_id: ID автора.
        author_name: Имя автора.
        body: Текст комментария.
        mentions: Список упомянутых ID.
        attachments: Список вложений.
        created_at: Дата создания.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    author_id: uuid.UUID
    author_name: str | None = None
    body: str
    mentions: list[Any] = Field(default_factory=list)
    attachments: list[Any] = Field(default_factory=list)
    created_at: datetime


class DocumentResponse(BaseModel):
    """Document nested in task detail.

    Атрибуты:
        id: UUID документа.
        doc_type: Тип документа.
        label: Метка.
        filename: Имя файла.
        mime_type: MIME-тип.
        file_size: Размер в байтах.
        version: Текущая версия.
        uploaded_by: ID загрузившего.
        created_at: Дата загрузки.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    doc_type: str
    label: str | None = None
    filename: str
    mime_type: str
    file_size: int
    version: int
    uploaded_by: uuid.UUID
    created_at: datetime


class TimeEntryResponse(BaseModel):
    """Time entry nested in task detail.

    Атрибуты:
        id: UUID записи.
        user_id: ID сотрудника.
        started_at: Время начала.
        ended_at: Время окончания.
        duration_minutes: Длительность.
        entry_type: Тип (timer, manual).
        is_billable: Оплачиваемое.
        notes: Комментарий.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_minutes: int
    entry_type: str
    is_billable: bool
    notes: str | None = None


class StatusHistoryResponse(BaseModel):
    """Status history entry nested in task detail.

    Атрибуты:
        id: UUID записи.
        from_status: Предыдущий статус.
        to_status: Новый статус.
        changed_by: ID пользователя.
        reason: Комментарий.
        transition_data: Дополнительные данные.
        created_at: Дата перехода.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_status: str
    to_status: str
    changed_by: uuid.UUID
    reason: str | None = None
    transition_data: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class TaskDetail(TaskResponse):
    """Full task representation with all nested relations.

    Атрибуты:
        checklists: Чек-листы задачи с пунктами.
        comments: Комментарии к задаче.
        documents: Прикреплённые документы.
        time_entries: Записи учёта времени.
        status_history: История переходов статусов.
    """

    checklists: list[ChecklistResponse] = Field(default_factory=list)
    comments: list[CommentResponse] = Field(default_factory=list)
    documents: list[DocumentResponse] = Field(default_factory=list)
    time_entries: list[TimeEntryResponse] = Field(default_factory=list)
    status_history: list[StatusHistoryResponse] = Field(default_factory=list)
