"""Orchestrate admin-triggered deploy via optional deploy-agent sidecar."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.deploy_job import DeployJob as DeployJobModel
from app.services.deploy_log_utils import parse_shas_from_deploy_log

_MAX_LOG_STORE = 120_000
_HTTP_TIMEOUT = httpx.Timeout(connect=30.0, read=3600.0, write=60.0, pool=30.0)


def deploy_ui_allowed(settings: Settings) -> bool:
    """True when admin deploy feature is configured."""
    if not settings.admin_deploy_enabled:
        return False
    url = (settings.deploy_agent_url or "").strip()
    return bool(url)


async def check_agent_health(settings: Settings) -> tuple[bool, str | None]:
    """Return (ok, error_message) for deploy-agent /health."""
    url = (settings.deploy_agent_url or "").strip()
    if not url:
        return False, "DEPLOY_AGENT_URL is not set"
    health = url.rstrip("/") + "/health"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            r = await client.get(health)
            if r.status_code == 200:
                return True, None
            return False, f"HTTP {r.status_code}"
    except httpx.HTTPError as exc:
        return False, str(exc)


async def fetch_branches(settings: Settings) -> list[str]:
    """Proxy to deploy-agent GET /branches."""
    base = (settings.deploy_agent_url or "").strip().rstrip("/")
    if not base:
        return []
    url = f"{base}/branches"
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        r = await client.get(url)
        r.raise_for_status()
        data: dict[str, Any] = r.json()
        raw = data.get("branches") or []
        return [str(x) for x in raw if x]


async def fetch_project_logs(settings: Settings, tail: int = 400) -> str:
    """Proxy to deploy-agent GET /project-logs."""
    base = (settings.deploy_agent_url or "").strip().rstrip("/")
    if not base:
        return ""
    tail = max(50, min(tail, 5000))
    url = f"{base}/project-logs?tail={tail}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.json()
        return str(data.get("lines") or "")


async def run_deploy_agent(
    settings: Settings,
    *,
    branch: str,
    job_id: uuid.UUID,
) -> tuple[int, str]:
    """POST /deploy to agent; return (exit_code, full_log_text)."""
    base = (settings.deploy_agent_url or "").strip().rstrip("/")
    url = f"{base}/deploy"
    payload = {"branch": branch.strip(), "job_id": str(job_id)}
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        r = await client.post(url, json=payload)
        text = r.text
        try:
            data = r.json()
        except Exception:
            return (1 if r.status_code >= 400 else 0), text
        log = str(data.get("log") or text)
        code = int(data.get("exit_code", 1 if r.status_code >= 400 else 0))
        return code, log


def _truncate_log(text: str) -> str:
    if len(text) <= _MAX_LOG_STORE:
        return text
    return text[-_MAX_LOG_STORE:]


async def create_job(db: AsyncSession, branch: str) -> DeployJobModel:
    """Insert deploy_jobs row in running state."""
    row = DeployJobModel(
        branch=branch.strip(),
        status="running",
        previous_sha=None,
        new_sha=None,
        log_excerpt=None,
        error_message=None,
        finished_at=None,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def finalize_job(
    db: AsyncSession,
    job_id: uuid.UUID,
    *,
    status: str,
    previous_sha: str | None,
    new_sha: str | None,
    log_text: str,
    error_message: str | None,
) -> DeployJobModel:
    """Update job after deploy-agent returns."""
    row = (
        await db.execute(select(DeployJobModel).where(DeployJobModel.id == job_id))
    ).scalar_one()
    row.status = status
    row.previous_sha = previous_sha
    row.new_sha = new_sha
    row.log_excerpt = _truncate_log(log_text)
    row.error_message = error_message
    row.finished_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(row)
    return row


async def mark_job_failed(db: AsyncSession, job_id: uuid.UUID, message: str, log: str = "") -> None:
    """Mark job failed (e.g. agent unreachable)."""
    row = (
        await db.execute(select(DeployJobModel).where(DeployJobModel.id == job_id))
    ).scalar_one_or_none()
    if row is None:
        return
    row.status = "failed"
    row.error_message = message[:8000]
    row.log_excerpt = _truncate_log(log) if log else None
    row.finished_at = datetime.now(timezone.utc)
    await db.commit()


async def list_jobs(db: AsyncSession, limit: int = 30) -> list[DeployJobModel]:
    """Recent deploy jobs, newest first."""
    limit = max(1, min(limit, 100))
    q = await db.execute(
        select(DeployJobModel).order_by(DeployJobModel.created_at.desc()).limit(limit),
    )
    return list(q.scalars().all())


async def get_job(db: AsyncSession, job_id: uuid.UUID) -> DeployJobModel | None:
    """Fetch one job."""
    return (
        await db.execute(select(DeployJobModel).where(DeployJobModel.id == job_id))
    ).scalar_one_or_none()


async def execute_deploy_flow(db: AsyncSession, branch: str) -> DeployJobModel:
    """Create job, call agent, persist outcome."""
    settings = get_settings()
    job = await create_job(db, branch)
    ok_health, herr = await check_agent_health(settings)
    if not ok_health:
        await mark_job_failed(db, job.id, herr or "deploy-agent health check failed")
        return (await get_job(db, job.id)) or job

    exit_code, log_text = await run_deploy_agent(settings, branch=branch, job_id=job.id)
    # Parse SHAs from log lines if agent prints them — optional markers DEPLOY_PREV_SHA= / DEPLOY_NEW_SHA=
    prev_sha, new_sha = parse_shas_from_deploy_log(log_text)
    if exit_code == 0:
        status = "success"
        err = None
    elif "ROLLBACK" in log_text.upper() or "rolling back" in log_text.lower():
        status = "rolled_back"
        err = "Deploy failed; rollback was executed"
    else:
        status = "failed"
        err = f"deploy script exited with code {exit_code}"

    return await finalize_job(
        db,
        job.id,
        status=status,
        previous_sha=prev_sha,
        new_sha=new_sha,
        log_text=log_text,
        error_message=err,
    )


