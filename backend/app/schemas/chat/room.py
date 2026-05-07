"""Schemas for chat rooms (direction-based groups)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class ChatRoomCreate(BaseModel):
    """Create chat room request.

    Attributes:
        name: Human readable room name.
        code: Optional stable room code used as internal room key.
               If not provided the backend may generate it.
    """

    name: str = Field(..., min_length=1, max_length=200)
    code: str | None = Field(default=None, min_length=1, max_length=100)
    is_private: bool = False
    participant_user_ids: list[uuid.UUID] = Field(default_factory=list)


class ChatRoomUpdate(BaseModel):
    """Partial update payload for room settings and participants."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=3000)
    is_private: bool | None = None
    is_archived: bool | None = None
    participant_user_ids: list[uuid.UUID] | None = None


class ChatRoomResponse(BaseModel):
    """Chat room response.

    Attributes:
        id: Room UUID.
        name: Human readable name.
        code: Internal room code (used by message endpoints).
        description: Optional description.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str
    description: str | None = None
    is_private: bool = False
    is_archived: bool = False
    participant_user_ids: list[uuid.UUID] = Field(default_factory=list)
    task_id: uuid.UUID | None = None

