"""Pydantic schemas for tender comments.

The schemas mirror task comments behaviour:
- author metadata (optional `author_name`)
- mention support
- attachments support via referenced `Document` IDs (stored on backend)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TenderCommentCreate(BaseModel):
    """Payload for creating a tender comment.

    Attributes:
        body: Optional comment text. Can be empty if attachments exist.
        mentions: Mentioned users UUIDs.
        attachment_doc_ids: Documents to attach to this comment.
    """

    body: str = Field(default="", min_length=0, max_length=10000)
    mentions: list[uuid.UUID] = Field(default_factory=list)
    attachment_doc_ids: list[uuid.UUID] = Field(default_factory=list)


class TenderCommentResponse(BaseModel):
    """Tender comment response.

    Attributes:
        id: Comment ID.
        author_id: Author user ID.
        author_name: Optional author display name.
        body: Comment body.
        mentions: Mentioned user IDs (as JSON values).
        attachments: Attached document IDs (as JSON values).
        created_at: Creation timestamp.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    author_id: uuid.UUID
    author_name: str | None = None
    body: str
    mentions: list[Any] = Field(default_factory=list)
    attachments: list[Any] = Field(default_factory=list)
    created_at: datetime

