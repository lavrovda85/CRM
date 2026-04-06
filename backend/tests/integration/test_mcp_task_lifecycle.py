"""Integration: task lifecycle (template workflow) — flagship MCP/REST parity path.

Requires PostgreSQL with migrations. Skips when the database is unreachable.
Avoids importing ``app.core.security`` at module level so collection works
when optional deps (e.g. structlog) are missing from the bare interpreter;
full stack tests still need ``pip install -e .`` from the backend project.
"""

from __future__ import annotations

import os
import uuid
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

DEV_USER_ID = "00000000-0000-0000-0000-000000000001"


async def _ensure_dev_user() -> uuid.UUID:
    """Ensure DEV_USER_ID exists (FK for tasks and history)."""
    from app.core.database import async_session_factory
    from app.models.user import User

    uid = uuid.UUID(DEV_USER_ID)
    async with async_session_factory() as session:
        row = await session.get(User, uid)
        if row is None:
            session.add(
                User(
                    id=uid,
                    keycloak_id=DEV_USER_ID,
                    email="dev-lifecycle-test@hvac-crm.local",
                    full_name="Dev Lifecycle",
                    role="admin",
                )
            )
            await session.commit()
        else:
            await session.rollback()
    return uid


def _linear_workflow() -> dict:
    return {
        "states": ["new", "in_progress", "completed"],
        "initial_state": "new",
        "transitions": [
            {"from": "new", "to": "in_progress"},
            {"from": "in_progress", "to": "completed"},
        ],
    }


@pytest.fixture
async def task_template_id() -> uuid.UUID:
    """Create a disposable task template with a simple linear workflow."""
    from app.core.database import async_session_factory
    from app.models.task_template import TaskTemplate

    await _ensure_dev_user()
    tid = uuid.uuid4()
    async with async_session_factory() as session:
        tpl = TaskTemplate(
            id=tid,
            name=f"MCP lifecycle test {tid.hex[:8]}",
            category="general",
            workflow_definition=_linear_workflow(),
            required_fields=[],
            sla_config={},
            auto_warehouse=[],
            required_documents={},
            is_active=True,
        )
        session.add(tpl)
        await session.commit()
    return tid


def _workflow_user():
    """Minimal user object for WorkflowEngine (matches Keycloak sub / dev user)."""
    return SimpleNamespace(
        sub=DEV_USER_ID,
        roles=["admin", "engineer"],
        email="dev@hvac-crm.local",
        raw_token="",
    )


async def test_workflow_engine_advances_statuses(task_template_id: uuid.UUID) -> None:
    """TaskService + WorkflowEngine: new → in_progress → completed with persistence."""
    from app.core.database import async_session_factory
    from app.models.task import Task
    from app.services.task_service import TaskService
    from app.services.workflow_engine import WorkflowEngine

    actor = {"id": uuid.UUID(DEV_USER_ID)}
    user = _workflow_user()

    async with async_session_factory() as db:
        task = await TaskService.create_task(
            db,
            {
                "title": "Lifecycle integration task",
                "template_id": task_template_id,
                "priority": "medium",
            },
            actor,
        )
        await db.commit()
        task_id = task.id

    async with async_session_factory() as db:
        task = await TaskService.get_task(db, task_id)
        engine = WorkflowEngine(db, user)
        await engine.execute_transition(task, "in_progress", user, db, reason="start")
        await db.commit()

    async with async_session_factory() as db:
        task = await TaskService.get_task(db, task_id)
        engine = WorkflowEngine(db, user)
        await engine.execute_transition(task, "completed", user, db, reason="done")
        await db.commit()

    async with async_session_factory() as db:
        task = await TaskService.get_task(db, task_id)
        assert task.status == "completed"
        assert task.completed_at is not None
        assert await db.get(Task, task_id) is not None


@pytest.fixture
def _patch_mcp_debug():
    with patch("app.mcp.tools.task_tools.get_settings") as m:
        m.return_value.debug = True
        yield m


async def test_mcp_tools_commit_and_match_workflow(
    task_template_id: uuid.UUID,
    _patch_mcp_debug,
) -> None:
    """MCP create_task / transition_task persist changes (commits after fix)."""
    pytest.importorskip("fastmcp", reason="MCP stack requires fastmcp")
    from app.core.database import async_session_factory
    from app.mcp.tools import task_tools
    from app.services.task_service import TaskService

    created = await task_tools.create_task(
        title="MCP parity task",
        template_id=str(task_template_id),
        priority="high",
    )
    task_id = created["id"]
    assert created["status"] == "new"

    t1 = await task_tools.transition_task(task_id, "in_progress", reason="go")
    assert t1["to_status"] == "in_progress"

    t2 = await task_tools.transition_task(task_id, "completed", reason="finish")
    assert t2["to_status"] == "completed"

    async with async_session_factory() as db:
        task = await TaskService.get_task(db, uuid.UUID(task_id))
        assert task.status == "completed"


async def test_mcp_backwards_transition_when_ordered_in_template(
    task_template_id: uuid.UUID,
    _patch_mcp_debug,
) -> None:
    """Backwards move along workflow.states is allowed via MCP WorkflowTransitionError fallback."""
    pytest.importorskip("fastmcp", reason="MCP stack requires fastmcp")
    await _ensure_dev_user()
    from app.mcp.tools import task_tools

    created = await task_tools.create_task(
        title="Backwards test",
        template_id=str(task_template_id),
    )
    task_id = created["id"]
    await task_tools.transition_task(task_id, "in_progress")
    await task_tools.transition_task(task_id, "completed")
    tb = await task_tools.transition_task(task_id, "in_progress", reason="reopen")

    assert tb["to_status"] == "in_progress"
