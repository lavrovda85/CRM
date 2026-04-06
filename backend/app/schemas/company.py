"""Pydantic schemas for companies (tenants)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CompanyResponse(BaseModel):
    """Company row for API/UI."""

    id: uuid.UUID
    name: str
    slug: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CompanyCreate(BaseModel):
    """Create a new organization (user becomes a member)."""

    name: str = Field(..., min_length=1, max_length=255)
    slug: str | None = Field(None, max_length=100)


class CompanyMembershipInfo(BaseModel):
    """Company plus membership hint for login/switcher."""

    company: CompanyResponse
    is_default: bool = False


class CompanyLoginOption(BaseModel):
    """Minimal company row for the public login screen (no auth)."""

    id: uuid.UUID
    name: str
    slug: str | None = None
