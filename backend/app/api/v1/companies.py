"""Company (tenant) API: list memberships, create organization."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.company_context import ActiveCompanyContext, get_active_company
from app.core.dependencies import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.company import Company, UserCompanyMembership
from app.schemas.company import (
    CompanyCreate,
    CompanyLoginOption,
    CompanyMembershipInfo,
    CompanyResponse,
)
from app.services import company_service
from app.services.user_identity import resolve_users_table_id

router = APIRouter(prefix="/companies", tags=["Companies"])


@router.get("/login-options", response_model=list[CompanyLoginOption])
async def list_login_company_options(db: AsyncSession = Depends(get_db)) -> list[CompanyLoginOption]:
    """Public list of active companies for the login form (tenant selection).

    Does not expose sensitive data; intended for internal CRM deployments where
    organization names are not secret.
    """
    res = await db.execute(select(Company).where(Company.is_active.is_(True)).order_by(Company.name))
    rows = list(res.scalars().all())
    return [
        CompanyLoginOption(id=c.id, name=c.name, slug=c.slug)
        for c in rows
    ]


@router.get("/mine", response_model=list[CompanyMembershipInfo])
async def list_my_companies(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[CompanyMembershipInfo]:
    """Organizations the current user belongs to (for login / company switcher)."""
    uid = await resolve_users_table_id(db, user)
    if await company_service.is_dev_admin(db, uid):
        companies = await company_service.list_all_active_companies(db)
        mem_rows = (
            await db.execute(select(UserCompanyMembership).where(UserCompanyMembership.user_id == uid))
        ).scalars().all()
        mem_by_cid: dict[uuid.UUID, UserCompanyMembership] = {m.company_id: m for m in mem_rows}
        return [
            CompanyMembershipInfo(
                company=CompanyResponse.model_validate(c),
                is_default=bool(mem_by_cid.get(c.id).is_default) if c.id in mem_by_cid else False,
            )
            for c in companies
        ]

    await company_service.ensure_default_company_for_user(db, uid)
    memberships = (
        await db.execute(select(UserCompanyMembership).where(UserCompanyMembership.user_id == uid))
    ).scalars().all()
    out: list[CompanyMembershipInfo] = []
    for m in memberships:
        co = await company_service.get_company(db, m.company_id)
        out.append(
            CompanyMembershipInfo(
                company=CompanyResponse.model_validate(co),
                is_default=m.is_default,
            )
        )
    return out


@router.post("", response_model=CompanyResponse, status_code=201)
async def create_company(
    body: CompanyCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> CompanyResponse:
    """Create a new company and add the current user as a member."""
    uid = await resolve_users_table_id(db, user)
    co = await company_service.create_company(
        db,
        name=body.name,
        creator_user_id=uid,
        slug=body.slug,
    )
    return CompanyResponse.model_validate(co)


@router.get("/active", response_model=CompanyResponse)
async def get_active_company_info(
    ctx: ActiveCompanyContext = Depends(get_active_company),
    db: AsyncSession = Depends(get_db),
) -> CompanyResponse:
    """Return metadata for the resolved active company (from ``X-Company-Id`` or default)."""
    co = await company_service.get_company(db, ctx.company_id)
    return CompanyResponse.model_validate(co)
