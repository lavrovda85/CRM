"""Pydantic schemas for in-app notification inbox API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import BaseResponse


class NotificationResponse(BaseResponse):
    """Single notification for the authenticated user's inbox.

    Attributes:
        event_type: Domain event (e.g. task_assigned, task_due_soon).
        title: Short headline.
        body: Human-readable text.
        data: Structured payload (task_id, dedupe_key, etc.).
        is_read: Whether the user dismissed / read the item.
    """

    model_config = ConfigDict(from_attributes=True)

    event_type: str
    title: str
    body: str
    data: dict[str, Any] = Field(default_factory=dict)
    is_read: bool


class NotificationUnreadCount(BaseModel):
    """Count of unread notifications for the current user."""

    unread_count: int
