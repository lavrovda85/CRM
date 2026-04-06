"""SQLAlchemy ORM models package.

Импортирует все модели для регистрации в metadata
и автоматического обнаружения Alembic.
"""

from app.models.base import BaseModel, TenantMixin, TimestampMixin
from app.models.company import Company, UserCompanyMembership
from app.models.user import User
from app.models.client import Client, ClientContact
from app.models.deal import Deal, DealStage
from app.models.task_template import TaskTemplate, TemplateChecklist, TemplateField, TemplateStage
from app.models.task import Task
from app.models.task_status import TaskStatusHistory
from app.models.board import Board
from app.models.checklist import Checklist, ChecklistItem
from app.models.time_entry import TimeEntry
from app.models.warehouse_item import WarehouseItem
from app.models.warehouse_movement import WarehouseMovement, WarehouseReservation
from app.models.equipment import Equipment, EquipmentUsage
from app.models.depreciation_record import DepreciationRecord
from app.models.document import Document, DocumentVersion
from app.models.comment import Comment
from app.models.notification import Notification
from app.models.reference import Reference, ReferenceItem
from app.models.chat import ChatAttachment, ChatMessage, ChatRoom
from app.models.tender import Tender, TenderChecklist, TenderChecklistItem, TenderComment
from app.models.ai_assistant_chat import AiAssistantMessage, AiAssistantSession
from app.models.system_setting import SystemSetting

__all__ = [
    "BaseModel",
    "TenantMixin",
    "TimestampMixin",
    "Company",
    "UserCompanyMembership",
    "User",
    "Client",
    "ClientContact",
    "Deal",
    "DealStage",
    "Tender",
    "TaskTemplate",
    "TemplateStage",
    "TemplateChecklist",
    "TemplateField",
    "Task",
    "TaskStatusHistory",
    "Board",
    "Checklist",
    "ChecklistItem",
    "TimeEntry",
    "WarehouseItem",
    "WarehouseMovement",
    "WarehouseReservation",
    "Equipment",
    "EquipmentUsage",
    "DepreciationRecord",
    "Document",
    "DocumentVersion",
    "TenderChecklist",
    "TenderChecklistItem",
    "Comment",
    "Notification",
    "ChatMessage",
    "ChatAttachment",
    "ChatRoom",
    "TenderComment",
    "Reference",
    "ReferenceItem",
    "AiAssistantMessage",
    "AiAssistantSession",
    "SystemSetting",
]
