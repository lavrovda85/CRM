"""Tender comment model.

This model stores discussion comments for tenders and supports attachments
by referencing uploaded `Document` records via `attachments` JSON field.
"""

import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class TenderComment(BaseModel):
    """Discussion comment on a tender.

    Attributes:
        tender_id: Tender ID.
        author_id: Author (user) ID.
        body: Comment body text.
        mentions: JSON array of mentioned user UUIDs (stored as list).
        attachments: JSON array of document IDs referenced in the comment.
    """

    __tablename__ = "tender_comments"

    tender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    mentions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    attachments: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    tender = relationship("Tender", back_populates="comments")
    author = relationship("User")

