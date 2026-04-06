"""Admin-only runtime settings endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.permissions import ADMIN_ONLY
from app.core.security import CurrentUser
from app.schemas.admin_settings import (
    AdminSettingsEnvelope,
    SchedulerRuleCreate,
    SchedulerRuleResponse,
    SchedulerSettingsResponse,
    SchedulerSettingsUpdate,
)
from app.services.admin_settings_service import (
    create_scheduler_rule,
    delete_scheduler_rule,
    env_preview,
    get_scheduler_rules,
    get_scheduler_settings,
    patch_scheduler_settings,
    update_scheduler_rule,
)
from app.workers.scheduled_tasks import run_scheduler_rule_once

router = APIRouter(prefix="/admin/settings", tags=["Admin Settings"])


@router.get("", response_model=AdminSettingsEnvelope)
async def get_admin_settings(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(ADMIN_ONLY),
) -> AdminSettingsEnvelope:
    """Get admin settings and selected env preview."""
    _ = user
    scheduler = await get_scheduler_settings(db)
    return AdminSettingsEnvelope(
        scheduler=SchedulerSettingsResponse(**scheduler),
        scheduler_rules=[SchedulerRuleResponse(**r) for r in await get_scheduler_rules(db)],
        env_preview=env_preview(),
    )


@router.patch("/scheduler", response_model=SchedulerSettingsResponse)
async def update_scheduler_settings(
    body: SchedulerSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(ADMIN_ONLY),
) -> SchedulerSettingsResponse:
    """Patch scheduler settings (persistent DB overrides)."""
    _ = user
    patch = body.model_dump(exclude_unset=True)
    updated = await patch_scheduler_settings(db, patch)
    return SchedulerSettingsResponse(**updated)


@router.get("/scheduler/rules", response_model=list[SchedulerRuleResponse])
async def list_scheduler_rules(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(ADMIN_ONLY),
) -> list[SchedulerRuleResponse]:
    """List scheduler rules."""
    _ = user
    return [SchedulerRuleResponse(**r) for r in await get_scheduler_rules(db)]


@router.post("/scheduler/rules", response_model=SchedulerRuleResponse, status_code=201)
async def add_scheduler_rule(
    body: SchedulerRuleCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(ADMIN_ONLY),
) -> SchedulerRuleResponse:
    """Create scheduler rule."""
    _ = user
    created = await create_scheduler_rule(db, body.model_dump())
    return SchedulerRuleResponse(**created)


@router.patch("/scheduler/rules/{rule_id}", response_model=SchedulerRuleResponse)
async def patch_scheduler_rule(
    rule_id: str,
    body: SchedulerSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(ADMIN_ONLY),
) -> SchedulerRuleResponse:
    """Patch scheduler rule."""
    _ = user
    updated = await update_scheduler_rule(db, rule_id, body.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail="Scheduler rule not found")
    return SchedulerRuleResponse(**updated)


@router.delete("/scheduler/rules/{rule_id}", status_code=204)
async def remove_scheduler_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(ADMIN_ONLY),
) -> None:
    """Delete scheduler rule."""
    _ = user
    ok = await delete_scheduler_rule(db, rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Scheduler rule not found")


@router.post("/scheduler/rules/{rule_id}/run")
async def run_scheduler_rule_now(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(ADMIN_ONLY),
) -> dict:
    """Run scheduler rule immediately (manual trigger)."""
    _ = (db, user)
    result = await run_scheduler_rule_once(rule_id=rule_id, force=True)
    return {"ok": True, **result}

