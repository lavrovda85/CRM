"""Persistent AI assistant chat history and session memory per authenticated user.

История диалога и краткий контекст (например, последняя созданная задача) хранятся в БД,
ключ — JWT ``sub`` (строка), чтобы работать и с Keycloak UUID, и с dev-user.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AiAssistantSession(Base):
    """One row per user: JSON session facts updated after each assistant turn."""

    __tablename__ = "ai_assistant_sessions"

    user_subject: Mapped[str] = mapped_column(String(512), primary_key=True)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AiAssistantMessage(Base):
    """A single user or assistant chat line for the AI assistant UI."""

    __tablename__ = "ai_assistant_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_subject: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
