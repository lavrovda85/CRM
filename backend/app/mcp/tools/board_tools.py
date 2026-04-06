"""MCP tools for Kanban/board management.

Aligned with ``/api/v1/boards``; boards are owned by the MCP / AI actor user.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import async_session_factory
from app.core.exceptions import NotFoundError, ValidationError
from app.mcp.actor_context import current_mcp_user_sub
from app.mcp.server import mcp
from app.models import Board, Task
from app.schemas.board import BoardDetailResponse, BoardResponse
from app.schemas.task import TaskResponse


def _board_id(raw: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(raw).strip())
    except ValueError as exc:
        raise ValidationError("board_id", "Must be a valid UUID") from exc


@mcp.tool()
async def list_boards(limit: int = 50) -> list[dict]:
    """List non-archived boards (paginated by limit, ordered by name).

    Returns:
        Board list as JSON dicts (``BoardResponse`` shape).
    """
    lim = max(1, min(int(limit), 200))
    async with async_session_factory() as session:
        result = await session.execute(
            select(Board)
            .where(Board.is_archived.is_(False))
            .order_by(Board.name)
            .limit(lim)
        )
        boards = result.scalars().all()
    return [BoardResponse.model_validate(b).model_dump(mode="json") for b in boards]


@mcp.tool()
async def create_board(
    name: str,
    description: str | None = None,
    board_type: str = "kanban",
) -> dict:
    """Create a board owned by the MCP service user."""
    clean = (name or "").strip()
    if not clean:
        raise ValidationError("name", "Board name must not be empty")

    owner = uuid.UUID(current_mcp_user_sub())
    async with async_session_factory() as session:
        board = Board(
            name=clean,
            description=description,
            board_type=(board_type or "kanban").strip() or "kanban",
            owner_id=owner,
            columns=[],
        )
        session.add(board)
        await session.flush()
        await session.refresh(board)
        await session.commit()
        data = BoardResponse.model_validate(board).model_dump(mode="json")
    return data


async def _board_detail(session: AsyncSession, board_id: uuid.UUID) -> BoardDetailResponse:
    result = await session.execute(
        select(Board).options(
            selectinload(Board.tasks).selectinload(Task.assignee),
            selectinload(Board.tasks).selectinload(Task.template),
            selectinload(Board.tasks).selectinload(Task.creator),
            selectinload(Board.tasks).selectinload(Task.requester_user),
            selectinload(Board.tasks).selectinload(Task.co_assignees),
            selectinload(Board.tasks).selectinload(Task.observers),
        ).where(Board.id == board_id)
    )
    board = result.scalar_one_or_none()
    if not board:
        raise NotFoundError("Board", str(board_id))

    tasks_by_status: dict[str, list] = defaultdict(list)
    for t in board.tasks:
        if t.deleted_at is not None:
            continue
        tasks_by_status[t.status].append(TaskResponse.model_validate(t).model_dump(mode="json"))

    base = BoardResponse.model_validate(board).model_dump()
    base["tasks_by_status"] = dict(tasks_by_status)
    return BoardDetailResponse(**base)


@mcp.tool()
async def get_board(board_id: str) -> dict:
    """Return board metadata and tasks grouped by workflow status."""
    bid = _board_id(board_id)
    async with async_session_factory() as session:
        detail = await _board_detail(session, bid)
    return detail.model_dump(mode="json")
