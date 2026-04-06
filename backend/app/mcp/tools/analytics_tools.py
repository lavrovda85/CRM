"""MCP tools for analytics and reporting in HVAC CRM/ERP.

Инструменты для получения статистики дашборда, производительности
сотрудников, расчёта зарплаты и аналитики тендеров.
"""

from __future__ import annotations

from datetime import datetime

from app.mcp.server import mcp


@mcp.tool()
async def get_dashboard_stats(period_days: int = 30) -> dict:
    """Get aggregated dashboard statistics for the platform.

    Возвращает сводную статистику платформы за указанный период:
    количество задач, сделок, тендеров, складских операций и финансовые показатели.

    Args:
        period_days (int): Период в днях для расчёта статистики.
            По умолчанию 30 дней.

    Returns:
        dict: Сводка с секциями:
            tasks — {total, new, in_progress, completed, overdue},
            deals — {total, total_amount, won_count, won_amount, conversion_rate},
            tenders — {total, active, won, lost, win_rate},
            warehouse — {low_stock_items, movements_count, total_consumption_cost},
            period_days.

    Example:
        AI agent: "Покажи общую статистику за последний месяц"
        >>> get_dashboard_stats(period_days=30)
    """
    # TODO: SELECT COUNT(*) FROM tasks grouped by status WHERE created_at >= now - period
    # TODO: SELECT COUNT(*), SUM(amount) FROM deals WHERE created_at >= now - period
    # TODO: SELECT COUNT(*) FROM tenders grouped by status WHERE created_at >= now - period
    # TODO: SELECT items WHERE quantity - reserved_quantity < min_quantity (low stock)
    # TODO: SELECT COUNT(*), SUM(quantity * unit_price) FROM warehouse_movements
    now = datetime.utcnow().isoformat()
    return {
        "tasks": {
            "total": 0,
            "new": 0,
            "in_progress": 0,
            "completed": 0,
            "overdue": 0,
        },
        "deals": {
            "total": 0,
            "total_amount": 0.0,
            "won_count": 0,
            "won_amount": 0.0,
            "conversion_rate": 0.0,
        },
        "tenders": {
            "total": 0,
            "active": 0,
            "won": 0,
            "lost": 0,
            "win_rate": 0.0,
        },
        "warehouse": {
            "low_stock_items": 0,
            "movements_count": 0,
            "total_consumption_cost": 0.0,
        },
        "period_days": period_days,
        "generated_at": now,
    }


@mcp.tool()
async def get_employee_performance(
    user_id: str,
    period_days: int = 30,
) -> dict:
    """Get performance metrics for a specific employee.

    Возвращает показатели производительности сотрудника за период:
    количество задач, среднее время выполнения, соблюдение SLA.

    Args:
        user_id (str): UUID сотрудника.
        period_days (int): Период в днях. По умолчанию 30.

    Returns:
        dict: Метрики производительности:
            user_id, user_name,
            tasks — {assigned, completed, in_progress, overdue,
                     avg_completion_hours, sla_compliance_rate},
            time_entries — {total_hours, billable_hours},
            period_days.

    Example:
        AI agent: "Покажи показатели монтажника Иванова за последние 2 недели"
        >>> get_employee_performance(
        ...     user_id="user-uuid-ivanov",
        ...     period_days=14,
        ... )
    """
    # TODO: SELECT tasks WHERE assigned_to = user_id AND updated_at >= period
    # TODO: Calculate avg completion time from started_at to completed_at
    # TODO: Calculate SLA compliance: completed_at <= sla_deadline
    # TODO: SELECT SUM(hours) FROM time_entries WHERE user_id AND period
    now = datetime.utcnow().isoformat()
    return {
        "user_id": user_id,
        "user_name": "Placeholder User",
        "tasks": {
            "assigned": 0,
            "completed": 0,
            "in_progress": 0,
            "overdue": 0,
            "avg_completion_hours": 0.0,
            "sla_compliance_rate": 0.0,
        },
        "time_entries": {
            "total_hours": 0.0,
            "billable_hours": 0.0,
        },
        "period_days": period_days,
        "generated_at": now,
    }


@mcp.tool()
async def calculate_salary(
    user_id: str,
    year: int,
    month: int,
) -> dict:
    """Calculate salary for an employee for a given month.

    Рассчитывает зарплату сотрудника на основе его salary_config,
    выполненных задач и отработанных часов за указанный месяц.

    Args:
        user_id (str): UUID сотрудника.
        year (int): Год расчёта (например, 2026).
        month (int): Месяц расчёта (1-12).

    Returns:
        dict: Расчёт зарплаты:
            user_id, user_name, year, month,
            base_salary, task_bonus, overtime_bonus,
            deductions, total, breakdown (list of components).

    Example:
        AI agent: "Рассчитай зарплату для Иванова за март 2026"
        >>> calculate_salary(
        ...     user_id="user-uuid-ivanov",
        ...     year=2026,
        ...     month=3,
        ... )
    """
    # TODO: SELECT user with salary_config WHERE id = user_id
    # TODO: SELECT completed tasks for the month
    # TODO: SELECT time_entries for the month, calc total hours
    # TODO: Apply salary_config formula (base + per-task bonus + overtime)
    # TODO: Apply deductions if any
    return {
        "user_id": user_id,
        "user_name": "Placeholder User",
        "year": year,
        "month": month,
        "base_salary": 0.0,
        "task_bonus": 0.0,
        "overtime_bonus": 0.0,
        "deductions": 0.0,
        "total": 0.0,
        "breakdown": [],
    }


@mcp.tool()
async def get_tender_analytics(period_days: int = 90) -> dict:
    """Get analytics on tender participation and success rates.

    Возвращает аналитику по тендерам: воронка участия, суммы,
    win-rate по источникам и временные показатели.

    Args:
        period_days (int): Период в днях для анализа. По умолчанию 90.

    Returns:
        dict: Аналитика тендеров:
            funnel — {search, participation, won, lost, execution, completed},
            financials — {total_budget, total_won_budget, avg_margin},
            by_source — list of {source, count, won_count, win_rate},
            timing — {avg_days_to_decision, avg_execution_days},
            period_days.

    Example:
        AI agent: "Покажи аналитику по тендерам за последний квартал"
        >>> get_tender_analytics(period_days=90)
    """
    # TODO: SELECT COUNT(*) FROM tenders grouped by status WHERE created_at >= period
    # TODO: SELECT SUM(budget), SUM(our_price) for won tenders
    # TODO: GROUP BY source for win_rate per source
    # TODO: Calculate avg days from created_at to status change (won/lost)
    now = datetime.utcnow().isoformat()
    return {
        "funnel": {
            "search": 0,
            "participation": 0,
            "won": 0,
            "lost": 0,
            "execution": 0,
            "completed": 0,
        },
        "financials": {
            "total_budget": 0.0,
            "total_won_budget": 0.0,
            "avg_margin": 0.0,
        },
        "by_source": [],
        "timing": {
            "avg_days_to_decision": 0.0,
            "avg_execution_days": 0.0,
        },
        "period_days": period_days,
        "generated_at": now,
    }
