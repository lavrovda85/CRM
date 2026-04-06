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

