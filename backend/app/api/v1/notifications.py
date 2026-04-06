"""In-app notification inbox: list, unread count, mark read."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import PaginationParams, get_crm_user_id, get_db
from app.core.exceptions import NotFoundError
from app.core.pagination import PaginatedResponse
from app.models.notification import Notification
from app.schemas.notification import NotificationResponse, NotificationUnreadCount

router = APIRouter(prefix="/notifications")


@router.get("/", response_model=PaginatedResponse[NotificationResponse])
async def list_notifications(
    pagination: PaginationParams = Depends(),
    unread_only: bool = Query(default=False, description="Only unread items"),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_crm_user_id),
) -> PaginatedResponse[NotificationResponse]:
    """List notifications for the current user, newest first."""
    base = select(Notification).where(Notification.user_id == user_id)
    count_q = select(func.count(Notification.id)).where(Notification.user_id == user_id)
    if unread_only:
        base = base.where(Notification.is_read.is_(False))
        count_q = count_q.where(Notification.is_read.is_(False))

    total = (await db.execute(count_q)).scalar() or 0
    result = await db.execute(
        base.order_by(Notification.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    rows = result.scalars().all()
    return PaginatedResponse(
        items=[NotificationResponse.model_validate(n) for n in rows],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/unread-count", response_model=NotificationUnreadCount)
async def unread_count(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_crm_user_id),
) -> NotificationUnreadCount:
    """Return the number of unread notifications."""
    q = select(func.count(Notification.id)).where(
        Notification.user_id == user_id,
        Notification.is_read.is_(False),
    )
    n = (await db.execute(q)).scalar() or 0
    return NotificationUnreadCount(unread_count=int(n))


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_crm_user_id),
) -> NotificationResponse:
    """Mark one notification as read (only if it belongs to the current user)."""
    res = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise NotFoundError("Notification", str(notification_id))
    row.is_read = True
    await db.flush()
    await db.refresh(row)
    return NotificationResponse.model_validate(row)


@router.post("/mark-all-read", response_model=NotificationUnreadCount)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID = Depends(get_crm_user_id),
) -> NotificationUnreadCount:
    """Mark all notifications as read for the current user."""
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    await db.flush()
    return NotificationUnreadCount(unread_count=0)
