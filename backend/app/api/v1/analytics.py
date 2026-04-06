"""Analytics and reporting API endpoints.

Дашборд, аналитика производительности сотрудников,
расчёт зарплаты, аналитика тендеров и склада.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.security import CurrentUser
from app.models import WarehouseItem, WarehouseMovement
from app.schemas.analytics import (
    DashboardStats,
    PerformanceStats,
    SalaryCalculation,
    TenderAnalytics,
    WarehouseAnalytics,
)
from app.services import analytics_read

router = APIRouter(prefix="/analytics")


@router.get("/dashboard", response_model=DashboardStats)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> DashboardStats:
    """Get dashboard statistics overview.

    Возвращает сводную статистику по задачам, сделкам,
    тендерам и складу для отображения на дашборде.

    Аргументы:
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Сводную статистику для дашборда.
    """
    return await analytics_read.aggregate_dashboard(db)


@router.get("/performance/{user_id}", response_model=PerformanceStats)
async def get_performance(
    user_id: uuid.UUID,
    date_from: date | None = Query(default=None, description="Period start"),
    date_to: date | None = Query(default=None, description="Period end"),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> PerformanceStats:
    """Get employee performance metrics.

    Возвращает метрики производительности сотрудника:
    завершённые задачи, средняя скорость, залогированные часы.

    Аргументы:
        user_id: UUID сотрудника.
        date_from: Начало периода.
        date_to: Конец периода.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Метрики производительности.
    """
    return await analytics_read.aggregate_performance(db, user_id, date_from, date_to)


@router.get("/salary/{user_id}", response_model=SalaryCalculation)
async def get_salary(
    user_id: uuid.UUID,
    period_start: date = Query(..., description="Calculation period start"),
    period_end: date = Query(..., description="Calculation period end"),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> SalaryCalculation:
    """Calculate employee salary for a period.

    Рассчитывает зарплату сотрудника за указанный период
    на основе salary_config пользователя, отработанных часов
    и завершённых задач.

    Аргументы:
        user_id: UUID сотрудника.
        period_start: Начало расчётного периода.
        period_end: Конец расчётного периода.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Детализированный расчёт зарплаты.
    """
    return await analytics_read.aggregate_salary(db, user_id, period_start, period_end)


@router.get("/tenders", response_model=TenderAnalytics)
async def get_tender_analytics(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TenderAnalytics:
    """Get tender analytics summary.

    Возвращает сводную аналитику по тендерам: количество,
    разбивка по статусам, процент побед, суммы.

    Аргументы:
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Аналитику по тендерам.
    """
    return await analytics_read.aggregate_tender_analytics(db)


@router.get("/warehouse", response_model=WarehouseAnalytics)
async def get_warehouse_analytics(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> WarehouseAnalytics:
    """Get warehouse analytics (low stock, movement summary).

    Возвращает аналитику по складу: общее количество позиций,
    позиции с низким остатком, общая стоимость и сводка движений.

    Аргументы:
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Аналитику по складу.
    """
    total_q = await db.execute(select(func.count(WarehouseItem.id)))
    total_items = total_q.scalar() or 0

    low_stock_q = await db.execute(
        select(WarehouseItem).where(
            WarehouseItem.quantity <= WarehouseItem.min_quantity
        )
    )
    low_stock_rows = low_stock_q.scalars().all()
    low_stock_items = [
        {
            "id": str(item.id),
            "name": item.name,
            "sku": item.sku,
            "quantity": float(item.quantity),
            "min_quantity": float(item.min_quantity),
        }
        for item in low_stock_rows
    ]

    value_q = await db.execute(
        select(func.coalesce(func.sum(WarehouseItem.quantity * WarehouseItem.price), 0))
    )
    total_value = value_q.scalar() or Decimal("0")

    movements_q = await db.execute(
        select(
            WarehouseMovement.movement_type,
            func.count(WarehouseMovement.id),
            func.coalesce(func.sum(WarehouseMovement.quantity), 0),
        ).group_by(WarehouseMovement.movement_type)
    )
    movements_summary = {
        row[0]: {"count": row[1], "total_quantity": float(row[2])}
        for row in movements_q.all()
    }

    return WarehouseAnalytics(
        total_items=total_items,
        low_stock_items=low_stock_items,
        total_value=total_value,
        movements_summary=movements_summary,
    )
