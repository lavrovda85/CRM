"""Integration: soft-delete and restore tasks (PostgreSQL).

Skipped when DB is unreachable; requires dev user from conftest patterns.
"""

from __future__ import annotations

import uuid

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

DEV_USER_ID = "00000000-0000-0000-0000-000000000001"


async def _ensure_dev_user() -> uuid.UUID:
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
                    email="dev-soft-delete@hvac-crm.local",
                    full_name="Dev Soft Delete",
                    role="admin",
                )
            )
            await session.commit()
        else:
            await session.rollback()
    return uid


async def test_soft_delete_hides_from_list_and_restore_brings_back() -> None:
    from app.core.database import async_session_factory
    from app.services.task_service import TaskService

    actor = {"id": await _ensure_dev_user()}

    async with async_session_factory() as db:
        task = await TaskService.create_task(
            db,
            {"title": "Soft delete integration", "priority": "low"},
            actor,
        )
        await db.commit()
        tid = task.id

    async with async_session_factory() as db:
        rows = await TaskService.list_tasks(
            db, {"limit": 500, "viewer_user_id": actor["id"]}
        )
        assert any(r.id == tid for r in rows)

    async with async_session_factory() as db:
        await TaskService.delete_task(db, tid, actor)
        await db.commit()

    async with async_session_factory() as db:
        rows = await TaskService.list_tasks(
            db, {"limit": 500, "viewer_user_id": actor["id"]}
        )
        assert not any(r.id == tid for r in rows)
        deleted, total = await TaskService.list_deleted_tasks(db, limit=50, offset=0)
        assert total >= 1
        assert any(t.id == tid for t in deleted)

    async with async_session_factory() as db:
        restored = await TaskService.restore_task(db, tid, actor)
        await db.commit()
        assert restored.deleted_at is None

    async with async_session_factory() as db:
        rows = await TaskService.list_tasks(
            db, {"limit": 500, "viewer_user_id": actor["id"]}
        )
        assert any(r.id == tid for r in rows)
