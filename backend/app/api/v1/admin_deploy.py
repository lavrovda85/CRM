"""Admin-only deploy and project log endpoints (requires deploy-agent on server)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.permissions import ADMIN_ONLY
from app.core.security import CurrentUser
from app.schemas.admin_deploy import (
    BranchListResponse,
    DeployJobResponse,
    DeployStatusResponse,
    DeployTriggerRequest,
    ProjectLogsResponse,
)
from app.models.deploy_job import DeployJob
from app.services import deploy_service

router = APIRouter(prefix="/admin/deploy", tags=["Admin Deploy"])


def _job_to_response(row: DeployJob) -> DeployJobResponse:
    return DeployJobResponse(
        id=row.id,
        branch=row.branch,
        status=row.status,
        previous_sha=row.previous_sha,
        new_sha=row.new_sha,
        log_excerpt=row.log_excerpt,
        error_message=row.error_message,
        created_at=row.created_at,
        finished_at=row.finished_at,
    )


@router.get("/status", response_model=DeployStatusResponse)
async def deploy_status(
    user: CurrentUser = Depends(ADMIN_ONLY),
) -> DeployStatusResponse:
    """Whether deploy UI is enabled and deploy-agent responds."""
    _ = user
    from app.core.config import get_settings

    s = get_settings()
    enabled = deploy_service.deploy_ui_allowed(s)
    reachable: bool | None = None
    err: str | None = None
    if enabled:
        reachable, err = await deploy_service.check_agent_health(s)
    return DeployStatusResponse(
        deploy_ui_enabled=enabled,
        agent_reachable=reachable,
        agent_error=err,
        github_repo_configured=bool((s.github_repo_url or "").strip()),
    )


@router.get("/branches", response_model=BranchListResponse)
async def deploy_branches(
    user: CurrentUser = Depends(ADMIN_ONLY),
) -> BranchListResponse:
    """List remote branches via deploy-agent."""
    _ = user
    from app.core.config import get_settings

    s = get_settings()
    if not deploy_service.deploy_ui_allowed(s):
        raise HTTPException(status_code=503, detail="Deploy is not configured")
    try:
        branches = await deploy_service.fetch_branches(s)
        return BranchListResponse(branches=sorted(branches))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/run", response_model=DeployJobResponse)
async def deploy_run(
    body: DeployTriggerRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(ADMIN_ONLY),
) -> DeployJobResponse:
    """Run deploy for the selected branch (blocking until deploy-agent finishes)."""
    _ = user
    from app.core.config import get_settings

    s = get_settings()
    if not deploy_service.deploy_ui_allowed(s):
        raise HTTPException(status_code=503, detail="Deploy is not configured (ADMIN_DEPLOY_ENABLED + DEPLOY_AGENT_URL)")
    row = await deploy_service.execute_deploy_flow(db, body.branch.strip())
    return _job_to_response(row)


@router.get("/jobs", response_model=list[DeployJobResponse])
async def deploy_jobs_list(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(ADMIN_ONLY),
    limit: int = Query(30, ge=1, le=100),
) -> list[DeployJobResponse]:
    """Recent deploy jobs."""
    _ = user
    rows = await deploy_service.list_jobs(db, limit=limit)
    return [_job_to_response(r) for r in rows]


@router.get("/jobs/{job_id}", response_model=DeployJobResponse)
async def deploy_job_get(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(ADMIN_ONLY),
) -> DeployJobResponse:
    """Single deploy job (includes log excerpt)."""
    _ = user
    row = await deploy_service.get_job(db, job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_response(row)


@router.get("/logs/project", response_model=ProjectLogsResponse)
async def project_logs(
    user: CurrentUser = Depends(ADMIN_ONLY),
    tail: int = Query(400, ge=50, le=5000),
) -> ProjectLogsResponse:
    """Tail of docker compose logs (backend, worker, nginx) via deploy-agent."""
    _ = user
    from app.core.config import get_settings

    s = get_settings()
    if not deploy_service.deploy_ui_allowed(s):
        raise HTTPException(status_code=503, detail="Deploy is not configured")
    try:
        lines = await deploy_service.fetch_project_logs(s, tail=tail)
        return ProjectLogsResponse(lines=lines)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
