"""Read-only analytics aggregations shared by REST and MCP.

Keeps dashboard / tender / performance / salary queries in one place
so MCP tools return the same numbers as ``/api/v1/analytics/*``.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models import Deal, Task, Tender, TimeEntry, User, WarehouseItem, WarehouseMovement
from app.models.task import task_co_assignees
from app.schemas.analytics import DashboardStats, PerformanceStats, SalaryCalculation, TenderAnalytics


def _task_involves_user(user_id: uuid.UUID):
    """Primary assignee OR co-assignee."""
    co_exists = (
        select(1)
        .select_from(task_co_assignees)
        .where(
            task_co_assignees.c.task_id == Task.id,
            task_co_assignees.c.user_id == user_id,
        )
        .exists()
    )
    return or_(Task.assigned_to == user_id, co_exists)


async def aggregate_dashboard(db: AsyncSession) -> DashboardStats:
    """Same logic as ``GET /analytics/dashboard``."""
    total_tasks_q = await db.execute(
        select(func.count(Task.id)).where(Task.active_filter())
    )
    total_tasks = total_tasks_q.scalar() or 0

    tasks_by_status_q = await db.execute(
        select(Task.status, func.count(Task.id))
        .where(Task.active_filter())
        .group_by(Task.status)
    )
    tasks_by_status = {row[0]: row[1] for row in tasks_by_status_q.all()}

    now = datetime.now(timezone.utc)
    final_task_statuses = ("completed", "done", "closed")
    start_today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    start_tomorrow = start_today + timedelta(days=1)

    overdue_q = await db.execute(
        select(func.count(Task.id)).where(
            and_(
                Task.active_filter(),
                Task.due_date < now,
                Task.completed_at.is_(None),
            )
        )
    )
    overdue_tasks = overdue_q.scalar() or 0

    completed_today_q = await db.execute(
        select(func.count(Task.id)).where(
            and_(
                Task.active_filter(),
                Task.status.in_(final_task_statuses),
                Task.completed_at.is_not(None),
                Task.completed_at >= start_today,
                Task.completed_at < start_tomorrow,
            )
        )
    )
    completed_today = completed_today_q.scalar() or 0

    active_tasks_q = await db.execute(
        select(func.count(Task.id)).where(
            and_(
                Task.active_filter(),
                ~Task.status.in_(final_task_statuses),
                Task.status != "cancelled",
            )
        )
    )
    active_tasks = active_tasks_q.scalar() or 0

    deals_q = await db.execute(
        select(func.count(Deal.id), func.coalesce(func.sum(Deal.amount), 0))
    )
    deals_row = deals_q.one()
    total_deals = deals_row[0] or 0
    deals_amount = deals_row[1] or Decimal("0")

    active_tenders_q = await db.execute(
        select(func.count(Tender.id)).where(
            Tender.status.in_(["search", "participation", "execution"])
        )
    )
    active_tenders = active_tenders_q.scalar() or 0

    low_stock_q = await db.execute(
        select(func.count(WarehouseItem.id)).where(
            WarehouseItem.quantity <= WarehouseItem.min_quantity
        )
    )
    low_stock_items = low_stock_q.scalar() or 0

    return DashboardStats(
        total_tasks=total_tasks,
        tasks_by_status=tasks_by_status,
        active_tasks=active_tasks,
        completed_today=completed_today,
        overdue_tasks=overdue_tasks,
        total_deals=total_deals,
        deals_amount=deals_amount,
        active_tenders=active_tenders,
        low_stock_items=low_stock_items,
    )


async def aggregate_tender_analytics(db: AsyncSession) -> TenderAnalytics:
    """Same logic as ``GET /analytics/tenders``."""
    total_q = await db.execute(select(func.count(Tender.id)))
    total_tenders = total_q.scalar() or 0

    by_status_q = await db.execute(
        select(Tender.status, func.count(Tender.id)).group_by(Tender.status)
    )
    tenders_by_status = {row[0]: row[1] for row in by_status_q.all()}

    won_count = tenders_by_status.get("won", 0)
    closed_count = won_count + tenders_by_status.get("lost", 0)
    win_rate = round(won_count / closed_count * 100, 2) if closed_count > 0 else 0.0

    sums_q = await db.execute(
        select(
            func.coalesce(func.sum(Tender.budget), 0),
            func.coalesce(func.sum(Tender.our_price), 0),
        )
    )
    sums_row = sums_q.one()

    return TenderAnalytics(
        total_tenders=total_tenders,
        tenders_by_status=tenders_by_status,
        win_rate=win_rate,
        total_budget=sums_row[0] or Decimal("0"),
        total_our_price=sums_row[1] or Decimal("0"),
    )


async def aggregate_performance(
    db: AsyncSession,
    user_id: uuid.UUID,
    date_from: date | None,
    date_to: date | None,
) -> PerformanceStats:
    """Same logic as ``GET /analytics/performance/{user_id}`` with optional window."""
    user_check = await db.execute(select(User).where(User.id == user_id))
    if not user_check.scalar_one_or_none():
        raise NotFoundError("User", str(user_id))

    dt_from: datetime | None = None
    dt_to: datetime | None = None
    if date_from:
        dt_from = datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc)
    if date_to:
        dt_to = datetime(date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=timezone.utc)

    completed_q = select(func.count(Task.id)).where(
        and_(
            Task.active_filter(),
            _task_involves_user(user_id),
            Task.status.in_(["completed", "done", "closed"]),
        )
    )
    in_progress_q = select(func.count(Task.id)).where(
        and_(
            Task.active_filter(),
            _task_involves_user(user_id),
            Task.status == "in_progress",
        )
    )

    if dt_from:
        completed_q = completed_q.where(Task.completed_at >= dt_from)
    if dt_to:
        completed_q = completed_q.where(Task.completed_at <= dt_to)

    tasks_completed = (await db.execute(completed_q)).scalar() or 0
    tasks_in_progress = (await db.execute(in_progress_q)).scalar() or 0

    hours_q = select(func.coalesce(func.sum(TimeEntry.duration_minutes), 0)).where(
        TimeEntry.user_id == user_id
    )
    if dt_from:
        hours_q = hours_q.where(TimeEntry.started_at >= dt_from)
    if dt_to:
        hours_q = hours_q.where(TimeEntry.started_at <= dt_to)
    total_minutes = (await db.execute(hours_q)).scalar() or 0

    avg_hours = 0.0
    if tasks_completed > 0:
        avg_q = await db.execute(
            select(
                func.avg(
                    func.extract("epoch", Task.completed_at - Task.started_at) / 3600
                )
            ).where(
                and_(
                    Task.active_filter(),
                    _task_involves_user(user_id),
                    Task.completed_at.is_not(None),
                    Task.started_at.is_not(None),
                )
            )
        )
        avg_hours = float(avg_q.scalar() or 0)

    on_time_total_q = await db.execute(
        select(
            func.count(Task.id),
            func.sum(case((Task.completed_at <= Task.due_date, 1), else_=0)),
        ).where(
            and_(
                Task.active_filter(),
                _task_involves_user(user_id),
                Task.completed_at.is_not(None),
                Task.due_date.is_not(None),
            )
        )
    )
    on_time_row = on_time_total_q.one()
    on_time_rate = 0.0
    if on_time_row[0] and on_time_row[0] > 0:
        on_time_rate = round((on_time_row[1] or 0) / on_time_row[0] * 100, 2)

    return PerformanceStats(
        user_id=user_id,
        tasks_completed=tasks_completed,
        tasks_in_progress=tasks_in_progress,
        avg_completion_hours=round(avg_hours, 2),
        total_hours_logged=round(total_minutes / 60, 2),
        on_time_rate=on_time_rate,
    )


async def aggregate_salary(
    db: AsyncSession,
    user_id: uuid.UUID,
    period_start: date,
    period_end: date,
) -> SalaryCalculation:
    """Same logic as ``GET /analytics/salary/{user_id}``."""
    user_result = await db.execute(select(User).where(User.id == user_id))
    db_user = user_result.scalar_one_or_none()
    if not db_user:
        raise NotFoundError("User", str(user_id))

    dt_from = datetime(period_start.year, period_start.month, period_start.day, tzinfo=timezone.utc)
    dt_to = datetime(period_end.year, period_end.month, period_end.day, 23, 59, 59, tzinfo=timezone.utc)

    hours_q = await db.execute(
        select(func.coalesce(func.sum(TimeEntry.duration_minutes), 0)).where(
            and_(
                TimeEntry.user_id == user_id,
                TimeEntry.started_at >= dt_from,
                TimeEntry.started_at <= dt_to,
            )
        )
    )
    total_minutes = hours_q.scalar() or 0
    hours_worked = round(total_minutes / 60, 2)

    tasks_q = await db.execute(
        select(func.count(Task.id)).where(
            and_(
                Task.active_filter(),
                _task_involves_user(user_id),
                Task.completed_at >= dt_from,
                Task.completed_at <= dt_to,
            )
        )
    )
    tasks_completed = tasks_q.scalar() or 0

    config = db_user.salary_config or {}
    base_salary = Decimal(str(config.get("base_salary", 0)))
    hourly_rate = Decimal(str(config.get("hourly_rate", 0)))
    task_bonus = Decimal(str(config.get("task_bonus", 0)))

    hourly_pay = hourly_rate * Decimal(str(hours_worked))
    task_pay = task_bonus * tasks_completed
    bonuses = hourly_pay + task_pay
    total = base_salary + bonuses

    breakdown = [
        {"type": "base_salary", "amount": float(base_salary)},
        {"type": "hourly_pay", "hours": hours_worked, "rate": float(hourly_rate), "amount": float(hourly_pay)},
        {"type": "task_bonus", "tasks": tasks_completed, "per_task": float(task_bonus), "amount": float(task_pay)},
    ]

    return SalaryCalculation(
        user_id=user_id,
        period_start=period_start,
        period_end=period_end,
        base_salary=base_salary,
        hours_worked=hours_worked,
        tasks_completed=tasks_completed,
        bonuses=bonuses,
        total=total,
        breakdown=breakdown,
    )


async def count_movements_since(db: AsyncSession, since: datetime) -> int:
    """Count warehouse movements with created_at >= since."""
    q = await db.execute(
        select(func.count(WarehouseMovement.id)).where(WarehouseMovement.created_at >= since)
    )
    return int(q.scalar() or 0)


async def sum_consumption_cost_since(db: AsyncSession, since: datetime) -> float:
    """Approximate cost of consumption movements since ``since``."""
    q = await db.execute(
        select(
            func.coalesce(
                func.sum(WarehouseMovement.quantity * func.coalesce(WarehouseMovement.unit_price, 0)),
                0,
            )
        ).where(
            and_(
                WarehouseMovement.created_at >= since,
                WarehouseMovement.movement_type == "consumption",
            )
        )
    )
    val = q.scalar() or 0
    return float(Decimal(str(val)).quantize(Decimal("0.01")))
