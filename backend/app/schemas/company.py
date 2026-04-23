"""Pydantic schemas for companies (tenants)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator


def _uuid_str_or_none(v: Any) -> str | None:
    """Normalize settings value to UUID string or None."""
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return str(uuid.UUID(s))
    except (ValueError, TypeError):
        return None


class CompanyResponse(BaseModel):
    """Company row for API/UI."""

    id: uuid.UUID
    name: str
    slug: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    field_work_board_id: str | None = None
    default_field_task_template_id: str | None = None

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _workspace_from_company_settings(cls, data: Any) -> Any:
        from app.models.company import Company as CompanyModel

        if isinstance(data, CompanyModel):
            st = data.settings if isinstance(data.settings, dict) else {}
            return {
                "id": data.id,
                "name": data.name,
                "slug": data.slug,
                "is_active": data.is_active,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
                "field_work_board_id": _uuid_str_or_none(st.get("field_work_board_id")),
                "default_field_task_template_id": _uuid_str_or_none(st.get("default_field_task_template_id")),
            }
        if isinstance(data, dict) and "field_work_board_id" not in data and "settings" in data:
            st = data.get("settings") or {}
            if isinstance(st, dict):
                data = {
                    **data,
                    "field_work_board_id": _uuid_str_or_none(st.get("field_work_board_id")),
                    "default_field_task_template_id": _uuid_str_or_none(st.get("default_field_task_template_id")),
                }
        return data


class CompanyWorkspaceSettingsPatch(BaseModel):
    """Partial update for ``Company.settings`` keys used by the field-work board."""

    field_work_board_id: str | None = Field(
        default=None,
        description="UUID of the Kanban board for crew/field tasks; null clears",
    )
    default_field_task_template_id: str | None = Field(
        default=None,
        description="UUID of default task template for new field-work tasks; null clears",
    )


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
