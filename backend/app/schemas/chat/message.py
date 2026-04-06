"""Schemas for the company-wide chat module."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageCreate(BaseModel):
    """Create chat message request schema.

    Args:
        room: Chat room identifier (defaults to "company").
        body: Message text.
    """

    room: str = Field(default="company", min_length=1, max_length=100)
    body: str = Field(default="", min_length=0, max_length=4000)


class ChatMessageResponse(BaseModel):
    """Chat message response schema.

    Args:
        id: Message UUID.
        room: Chat room identifier.
        sender_id: UUID of the sender.
        sender_name: Sender full name.
        body: Message text.
        created_at: Creation timestamp (UTC).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    room: str
    sender_id: uuid.UUID
    sender_name: str | None = None
    body: str
    created_at: datetime
    attachments: list[ChatAttachmentResponse] = Field(default_factory=list)


class ChatAttachmentResponse(BaseModel):
    """Chat attachment response.

    Args:
        id: Attachment UUID.
        filename: Original filename.
        mime_type: MIME type.
        file_size: File size in bytes.
        download_url: Presigned URL to download the file.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    mime_type: str
    file_size: int
    download_url: str

