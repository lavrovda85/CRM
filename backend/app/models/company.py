"""Multi-tenant company (organization) and user membership.

Each CRM record belongs to exactly one company; users may belong to several
companies and select the active one per request (``X-Company-Id`` header).
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Company(BaseModel):
    """Tenant organization: isolated data scope for tasks, tenders, warehouse, etc."""

    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    memberships = relationship("UserCompanyMembership", back_populates="company", cascade="all, delete-orphan")


class UserCompanyMembership(BaseModel):
    """Links a CRM user to a company with optional default flag."""

    __tablename__ = "user_company_memberships"
    __table_args__ = (UniqueConstraint("user_id", "company_id", name="uq_user_company_membership"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user = relationship("User", back_populates="company_memberships")
    company = relationship("Company", back_populates="memberships")
