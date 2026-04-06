"""Company (tenant) CRUD and membership checks."""

from __future__ import annotations

import re
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import HVACBaseError, NotFoundError, ValidationError
from app.models.company import Company, UserCompanyMembership
from app.models.user import User


def _slugify(name: str) -> str:
    s = re.sub(r"[^\w\s-]", "", name.lower())
    s = re.sub(r"[-\s]+", "-", s).strip("-")
    return s[:80] or "company"


async def get_membership(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    company_id: uuid.UUID,
) -> UserCompanyMembership | None:
    """Return membership row if the user belongs to the company."""
    res = await db.execute(
        select(UserCompanyMembership).where(
            UserCompanyMembership.user_id == user_id,
            UserCompanyMembership.company_id == company_id,
        )
    )
    return res.scalar_one_or_none()


async def is_dev_admin(db: AsyncSession, user_id: uuid.UUID) -> bool:
    """True if this CRM user is configured as Dev Admin (sees all tenants)."""
    s = get_settings()
    id_set = {str(x).strip().lower() for x in s.dev_admin_user_ids if str(x).strip()}
    if str(user_id).lower() in id_set:
        return True
    u = await db.get(User, user_id)
    if u is None:
        return False
    emails = {(e or "").strip().lower() for e in s.dev_admin_emails if (e or "").strip()}
    if (u.email or "").strip().lower() in emails:
        return True
    return False


async def require_membership(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    company_id: uuid.UUID,
) -> UserCompanyMembership | None:
    """Raise if the user is not allowed to use this company (membership or Dev Admin)."""
    if await is_dev_admin(db, user_id):
        await get_company(db, company_id)
        return await get_membership(db, user_id=user_id, company_id=company_id)
    m = await get_membership(db, user_id=user_id, company_id=company_id)
    if m is None:
        raise HVACBaseError(
            message="You are not a member of this company",
            code="COMPANY_ACCESS_DENIED",
            status_code=403,
            details={"company_id": str(company_id)},
        )
    return m


async def list_companies_for_user(db: AsyncSession, user_id: uuid.UUID) -> list[Company]:
    """All active companies the user belongs to."""
    res = await db.execute(
        select(Company)
        .join(UserCompanyMembership, UserCompanyMembership.company_id == Company.id)
        .where(
            UserCompanyMembership.user_id == user_id,
            Company.is_active.is_(True),
        )
        .order_by(Company.name)
    )
    return list(res.scalars().all())


async def list_all_active_companies(db: AsyncSession) -> list[Company]:
    """All active companies (for Dev Admin company switcher)."""
    res = await db.execute(select(Company).where(Company.is_active.is_(True)).order_by(Company.name))
    return list(res.scalars().all())


async def get_or_create_testing_company(db: AsyncSession) -> Company:
    """Return the configured testing tenant (default: «Спец-строй», slug ``spec-stroy``)."""
    s = get_settings()
    slug = (s.testing_company_slug or "spec-stroy").strip()[:100] or "spec-stroy"
    name = (s.testing_company_name or "Спец-строй").strip()[:255] or "Спец-строй"
    res = await db.execute(select(Company).where(Company.slug == slug))
    row = res.scalar_one_or_none()
    if row is not None:
        return row
    co = Company(name=name, slug=slug, is_active=True, settings={})
    db.add(co)
    await db.flush()
    await db.refresh(co)
    return co


async def _pick_default_company_id(db: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    """Resolve default company id from existing memberships."""
    res = await db.execute(
        select(UserCompanyMembership.company_id)
        .where(UserCompanyMembership.user_id == user_id, UserCompanyMembership.is_default.is_(True))
        .limit(1)
    )
    row = res.scalar_one_or_none()
    if row is not None:
        return row
    res2 = await db.execute(
        select(UserCompanyMembership.company_id)
        .where(UserCompanyMembership.user_id == user_id)
        .order_by(UserCompanyMembership.created_at)
        .limit(1)
    )
    r2 = res2.scalar_one_or_none()
    if r2 is not None:
        return r2
    spec = await get_or_create_testing_company(db)
    return spec.id


async def ensure_default_company_for_user(db: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    """If the user has no company memberships, attach them to the testing company (Спец-строй).

    Returns:
        A company id the user can use as default context.
    """
    cnt_res = await db.execute(
        select(func.count())
        .select_from(UserCompanyMembership)
        .where(UserCompanyMembership.user_id == user_id)
    )
    if (cnt_res.scalar() or 0) > 0:
        return await _pick_default_company_id(db, user_id)

    spec = await get_or_create_testing_company(db)
    db.add(
        UserCompanyMembership(
            user_id=user_id,
            company_id=spec.id,
            role=None,
            is_default=True,
        )
    )
    await db.flush()
    return spec.id


async def bootstrap_testing_tenant(db: AsyncSession) -> None:
    """Idempotent: ensure «Спец-строй» exists; bind all non–Dev Admin users to it as default.

    Dev Admin users are left unchanged so they can switch across all companies without
    forced membership rows (``require_membership`` / ``X-Company-Id`` still allows access).
    """
    spec = await get_or_create_testing_company(db)
    users_res = await db.execute(select(User))
    users = list(users_res.scalars().unique().all())
    for u in users:
        if await is_dev_admin(db, u.id):
            continue
        await db.execute(
            update(UserCompanyMembership)
            .where(UserCompanyMembership.user_id == u.id)
            .values(is_default=False)
        )
        existing = await get_membership(db, user_id=u.id, company_id=spec.id)
        if existing is not None:
            existing.is_default = True
        else:
            db.add(
                UserCompanyMembership(
                    user_id=u.id,
                    company_id=spec.id,
                    role=None,
                    is_default=True,
                )
            )
    await db.flush()


async def create_company(
    db: AsyncSession,
    *,
    name: str,
    creator_user_id: uuid.UUID,
    slug: str | None = None,
) -> Company:
    """Create a company and add the creator as member (default)."""
    nm = (name or "").strip()
    if not nm:
        raise ValidationError("name", "Company name is required")
    sg = (slug or "").strip() or _slugify(nm)
    co = Company(name=nm[:255], slug=sg[:100] if sg else None, is_active=True, settings={})
    db.add(co)
    await db.flush()
    mem = UserCompanyMembership(
        user_id=creator_user_id,
        company_id=co.id,
        role="admin",
        is_default=False,
    )
    db.add(mem)
    await db.flush()
    return co


async def get_default_or_first_company_id(db: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    """Return ``is_default`` membership company, else first membership, else create default."""
    await ensure_default_company_for_user(db, user_id)
    return await _pick_default_company_id(db, user_id)


async def get_company(db: AsyncSession, company_id: uuid.UUID) -> Company:
    co = await db.get(Company, company_id)
    if co is None or not co.is_active:
        raise NotFoundError("Company", str(company_id))
    return co
