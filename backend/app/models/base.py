"""Base model with common fields for all entities.

Предоставляет базовый класс с UUID primary key
и временными метками создания/обновления.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TimestampMixin:
    """Mixin adding created_at and updated_at timestamps.

    Атрибуты:
        created_at: Дата создания записи (UTC).
        updated_at: Дата последнего обновления (UTC).
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class BaseModel(TimestampMixin, Base):
    """Abstract base model with UUID PK and timestamps.

    Атрибуты:
        id: UUID первичный ключ, генерируемый автоматически.
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
