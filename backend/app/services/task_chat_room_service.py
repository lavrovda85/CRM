"""Task-linked chat room helpers (private rooms per task)."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatRoom, Task


class TaskChatRoomService:
    """Utilities to create/sync/archive private chat rooms for task discussions."""

    @staticmethod
    def task_room_code(task_id: uuid.UUID) -> str:
        """Build stable room code for a task."""
        return f"task-{task_id}"

    @staticmethod
    def participant_ids_for_task(task: Task) -> list[str]:
        """Collect unique task participant IDs as strings."""
        seen: set[str] = set()
        out: list[str] = []
        for uid in (task.assigned_to, task.requested_by, task.created_by):
            if uid is None:
                continue
            s = str(uid)
            if s not in seen:
                seen.add(s)
                out.append(s)
        for rel in (task.co_assignees or []):
            s = str(rel.id)
            if s not in seen:
                seen.add(s)
                out.append(s)
        for rel in (task.observers or []):
            s = str(rel.id)
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out

    @staticmethod
    async def get_for_task(
        db: AsyncSession,
        *,
        company_id: uuid.UUID,
        task_id: uuid.UUID,
    ) -> ChatRoom | None:
        """Return task room for ``task_id`` in tenant company, if exists."""
        res = await db.execute(
            select(ChatRoom).where(ChatRoom.company_id == company_id, ChatRoom.task_id == task_id),
        )
        return res.scalar_one_or_none()

    @staticmethod
    async def ensure_for_task(db: AsyncSession, *, task: Task, extra_user_ids: list[uuid.UUID] | None = None) -> ChatRoom:
        """Create or update a private room for task comments and participants."""
        participants = set(TaskChatRoomService.participant_ids_for_task(task))
        for uid in extra_user_ids or []:
            participants.add(str(uid))
        participants_sorted = sorted(participants)

        room = await TaskChatRoomService.get_for_task(db, company_id=task.company_id, task_id=task.id)
        if room is None:
            room = ChatRoom(
                company_id=task.company_id,
                name=f"Задача: {(task.title or '').strip()[:150]}",
                code=TaskChatRoomService.task_room_code(task.id),
                is_private=True,
                is_archived=False,
                participant_user_ids=participants_sorted,
                task_id=task.id,
            )
            db.add(room)
            await db.flush()
            await db.refresh(room)
            return room

        changed = False
        if not room.is_private:
            room.is_private = True
            changed = True
        current = {str(x) for x in (room.participant_user_ids or []) if str(x).strip()}
        merged = sorted(current.union(participants))
        if merged != sorted(current):
            room.participant_user_ids = merged
            changed = True
        if changed:
            await db.flush()
            await db.refresh(room)
        return room

    @staticmethod
    async def set_archived_for_task(
        db: AsyncSession,
        *,
        company_id: uuid.UUID,
        task_id: uuid.UUID,
        is_archived: bool,
    ) -> None:
        """Set archive flag for a task room if it exists."""
        await db.execute(
            update(ChatRoom)
            .where(ChatRoom.company_id == company_id, ChatRoom.task_id == task_id)
            .values(is_archived=is_archived),
        )

    @staticmethod
    async def archive_for_task(db: AsyncSession, *, company_id: uuid.UUID, task_id: uuid.UUID) -> None:
        """Archive a task room if it exists."""
        await TaskChatRoomService.set_archived_for_task(
            db,
            company_id=company_id,
            task_id=task_id,
            is_archived=True,
        )
