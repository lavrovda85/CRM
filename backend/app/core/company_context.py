"""Active company (tenant) scope for API requests."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.exceptions import ValidationError
from app.core.security import CurrentUser, get_current_user
from app.services import company_service
from app.services.user_identity import resolve_users_table_id


@dataclass(frozen=True)
class ActiveCompanyContext:
    """Resolved tenant scope: CRM user id and active company id."""

    company_id: uuid.UUID
    user_db_id: uuid.UUID


async def get_active_company(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    x_company_id: str | None = Header(None, alias="X-Company-Id"),
) -> ActiveCompanyContext:
    """Resolve the active company: explicit ``X-Company-Id`` or the user's default/first company.

    Ensures at least one company exists for the user (bootstrap).
    """
    uid = await resolve_users_table_id(db, user)
    raw = (x_company_id or "").strip()
    if raw:
        try:
            cid = uuid.UUID(raw)
        except ValueError as exc:
            raise ValidationError("X-Company-Id", "Must be a valid UUID") from exc
        await company_service.require_membership(db, user_id=uid, company_id=cid)
        return ActiveCompanyContext(company_id=cid, user_db_id=uid)
    cid = await company_service.get_default_or_first_company_id(db, uid)
    return ActiveCompanyContext(company_id=cid, user_db_id=uid)
