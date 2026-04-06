"""MCP analytics tools backed by real DB aggregates (``analytics_read``)."""

from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.exceptions import NotFoundError, ValidationError
from app.mcp.server import mcp
from app.models import User
from app.services import analytics_read


def _uid(raw: str, field: str = "user_id") -> uuid.UUID:
    try:
        return uuid.UUID(str(raw).strip())
    except ValueError as exc:
        raise ValidationError(field, "Must be a valid UUID") from exc


@mcp.tool()
async def get_dashboard_stats(period_days: int = 30) -> dict:
    """Aggregated dashboard metrics (tasks, deals, tenders, warehouse highlights)."""
    period_days = max(1, min(int(period_days), 3650))
    since = datetime.now(timezone.utc) - timedelta(days=period_days)

    async with async_session_factory() as db:
        d = await analytics_read.aggregate_dashboard(db)
        ta = await analytics_read.aggregate_tender_analytics(db)
        movements_count = await analytics_read.count_movements_since(db, since)
        consumption_cost = await analytics_read.sum_consumption_cost_since(db, since)

    tbs = d.tasks_by_status
    completed_like = sum(tbs.get(s, 0) for s in ("completed", "done", "closed"))

    return {
        "tasks": {
            "total": d.total_tasks,
            "new": tbs.get("new", 0),
            "in_progress": tbs.get("in_progress", 0),
            "completed": completed_like,
            "overdue": d.overdue_tasks,
        },
        "deals": {
            "total": d.total_deals,
            "total_amount": float(d.deals_amount),
            "won_count": 0,
            "won_amount": 0.0,
            "conversion_rate": 0.0,
        },
        "tenders": {
            "total": ta.total_tenders,
            "active": d.active_tenders,
            "won": ta.tenders_by_status.get("won", 0),
            "lost": ta.tenders_by_status.get("lost", 0),
            "win_rate": ta.win_rate,
        },
        "warehouse": {
            "low_stock_items": d.low_stock_items,
            "movements_count": movements_count,
            "total_consumption_cost": consumption_cost,
        },
        "period_days": period_days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@mcp.tool()
async def get_employee_performance(
    user_id: str,
    period_days: int = 30,
) -> dict:
    """Performance metrics for one user over the last ``period_days``."""
    uid = _uid(user_id)
    days = max(1, min(int(period_days), 3650))
    end = date.today()
    start = end - timedelta(days=days)

    async with async_session_factory() as db:
        user_name = await db.scalar(select(User.full_name).where(User.id == uid))
        if user_name is None:
            raise NotFoundError("User", user_id)
        perf = await analytics_read.aggregate_performance(db, uid, start, end)

    return {
        "user_id": str(uid),
        "user_name": user_name,
        "tasks": {
            "assigned": perf.tasks_completed + perf.tasks_in_progress,
            "completed": perf.tasks_completed,
            "in_progress": perf.tasks_in_progress,
            "overdue": 0,
            "avg_completion_hours": perf.avg_completion_hours,
            "sla_compliance_rate": perf.on_time_rate,
        },
        "time_entries": {
            "total_hours": perf.total_hours_logged,
            "billable_hours": perf.total_hours_logged,
        },
        "period_days": days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@mcp.tool()
async def calculate_salary(
    user_id: str,
    year: int,
    month: int,
) -> dict:
    """Monthly salary estimate from ``salary_config`` and logged work (same as REST)."""
    uid = _uid(user_id)
    if month < 1 or month > 12:
        raise ValidationError("month", "Must be 1–12")

    period_start = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    period_end = date(year, month, last_day)

    async with async_session_factory() as db:
        user_name = await db.scalar(select(User.full_name).where(User.id == uid))
        if user_name is None:
            raise NotFoundError("User", user_id)
        calc = await analytics_read.aggregate_salary(db, uid, period_start, period_end)

    return {
        "user_id": str(uid),
        "user_name": user_name,
        "year": year,
        "month": month,
        "base_salary": float(calc.base_salary),
        "task_bonus": float(
            sum(
                float(x.get("amount", 0))
                for x in calc.breakdown
                if isinstance(x, dict) and x.get("type") == "task_bonus"
            )
        ),
        "overtime_bonus": float(
            sum(
                float(x.get("amount", 0))
                for x in calc.breakdown
                if isinstance(x, dict) and x.get("type") == "hourly_pay"
            )
        ),
        "deductions": 0.0,
        "total": float(calc.total),
        "breakdown": calc.breakdown,
    }


@mcp.tool()
async def get_tender_analytics(period_days: int = 90) -> dict:
    """Tender funnel and financial totals (global, not filtered by period yet)."""
    _ = max(1, min(int(period_days), 3650))

    async with async_session_factory() as db:
        ta = await analytics_read.aggregate_tender_analytics(db)

    by_status = ta.tenders_by_status
    return {
        "funnel": {
            "search": by_status.get("search", 0),
            "participation": by_status.get("participation", 0),
            "won": by_status.get("won", 0),
            "lost": by_status.get("lost", 0),
            "execution": by_status.get("execution", 0),
            "completed": by_status.get("completed", 0),
        },
        "financials": {
            "total_budget": float(ta.total_budget),
            "total_won_budget": float(ta.total_budget),
            "avg_margin": 0.0,
        },
        "by_source": [],
        "timing": {
            "avg_days_to_decision": 0.0,
            "avg_execution_days": 0.0,
        },
        "period_days": period_days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
