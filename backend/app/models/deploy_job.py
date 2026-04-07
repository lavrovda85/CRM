"""Admin deploy job history (triggered from UI, executed by deploy-agent)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class DeployJob(BaseModel):
    """One deploy attempt: branch selection, git SHAs, log excerpt, outcome."""

    __tablename__ = "deploy_jobs"

    branch: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    previous_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    new_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    log_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
