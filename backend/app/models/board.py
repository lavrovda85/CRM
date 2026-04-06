"""Board model for Kanban/Scrum views.

Доски группируют задачи по проектам, тендерам
или другим контекстам для визуализации.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Board(BaseModel):
    """Kanban/Scrum board for grouping and visualizing tasks.

    Атрибуты:
        name: Название доски.
        description: Описание.
        board_type: Тип доски (kanban, scrum, tender).
        owner_id: Владелец доски.
        columns: JSON определение колонок (маппинг на статусы).
        is_archived: Доска в архиве.
    """

    __tablename__ = "boards"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    board_type: Mapped[str] = mapped_column(String(50), nullable=False, default="kanban")
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    columns: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    owner = relationship("User", foreign_keys=[owner_id])
    tasks = relationship("Task", back_populates="board")
