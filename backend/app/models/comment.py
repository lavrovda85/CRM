"""Comment model for task discussions.

Комментарии к задачам с поддержкой упоминаний
и вложений.
"""

import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Comment(BaseModel):
    """Discussion comment on a task.

    Атрибуты:
        task_id: ID задачи.
        author_id: ID автора комментария.
        body: Текст комментария (поддержка Markdown).
        mentions: JSON массив ID упомянутых пользователей.
        attachments: JSON массив ID прикреплённых документов.
    """

    __tablename__ = "comments"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    mentions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    attachments: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    task = relationship("Task", back_populates="comments")
    author = relationship("User", back_populates="comments")
