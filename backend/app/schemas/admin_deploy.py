"""Schemas for admin deploy UI."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DeployJobResponse(BaseModel):
    """Single deploy job row."""

    id: UUID
    branch: str
    status: str
    previous_sha: str | None = None
    new_sha: str | None = None
    log_excerpt: str | None = None
    error_message: str | None = None
    created_at: datetime
    finished_at: datetime | None = None


class DeployTriggerRequest(BaseModel):
    """Start deploy from selected branch."""

    branch: str = Field(..., min_length=1, max_length=512)


class DeployTriggerResponse(BaseModel):
    """Result after deploy-agent finishes (synchronous HTTP)."""

    job_id: UUID
    status: str
    log_excerpt: str | None = None
    error_message: str | None = None


class DeployStatusResponse(BaseModel):
    """Whether deploy UI can be used and agent health."""

    deploy_ui_enabled: bool
    agent_reachable: bool | None = None
    agent_error: str | None = None
    github_repo_configured: bool = False


class BranchListResponse(BaseModel):
    """Remote branch names."""

    branches: list[str] = Field(default_factory=list)


class ProjectLogsResponse(BaseModel):
    """Docker compose logs tail."""

    lines: str = ""
