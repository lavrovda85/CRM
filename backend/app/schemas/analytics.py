"""Schemas for analytics and reporting endpoints.

Схемы валидации для дашборда, аналитики производительности,
расчёта зарплаты, аналитики тендеров и склада.
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class DashboardStats(BaseModel):
    """Schema for dashboard statistics.

    Атрибуты:
        total_tasks (int): Общее количество задач.
        tasks_by_status (dict): Количество задач по статусам.
        overdue_tasks (int): Просроченные задачи.
        total_deals (int): Общее количество сделок.
        deals_amount (Decimal): Общая сумма сделок.
        active_tenders (int): Количество активных тендеров.
        low_stock_items (int): Позиции с низким остатком.
    """

    total_tasks: int = 0
    tasks_by_status: dict[str, int] = Field(default_factory=dict)
    overdue_tasks: int = 0
    total_deals: int = 0
    deals_amount: Decimal = Decimal("0")
    active_tenders: int = 0
    low_stock_items: int = 0


class PerformanceStats(BaseModel):
    """Schema for employee performance metrics.

    Атрибуты:
        user_id (uuid.UUID): ID сотрудника.
        tasks_completed (int): Завершённых задач.
        tasks_in_progress (int): Задач в работе.
        avg_completion_hours (float): Среднее время завершения (часы).
        total_hours_logged (float): Всего залогированных часов.
        on_time_rate (float): Процент задач, завершённых в срок.
    """

    user_id: uuid.UUID
    tasks_completed: int = 0
    tasks_in_progress: int = 0
    avg_completion_hours: float = 0.0
    total_hours_logged: float = 0.0
    on_time_rate: float = 0.0


class SalaryCalculation(BaseModel):
    """Schema for employee salary calculation.

    Атрибуты:
        user_id (uuid.UUID): ID сотрудника.
        period_start (date): Начало расчётного периода.
        period_end (date): Конец расчётного периода.
        base_salary (Decimal): Базовая ставка.
        hours_worked (float): Отработано часов.
        tasks_completed (int): Завершено задач.
        bonuses (Decimal): Бонусы.
        total (Decimal): Итого к выплате.
        breakdown (list): Детализация расчёта.
    """

    user_id: uuid.UUID
    period_start: date
    period_end: date
    base_salary: Decimal = Decimal("0")
    hours_worked: float = 0.0
    tasks_completed: int = 0
    bonuses: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    breakdown: list[Any] = Field(default_factory=list)


class TenderAnalytics(BaseModel):
    """Schema for tender analytics summary.

    Атрибуты:
        total_tenders (int): Общее количество тендеров.
        tenders_by_status (dict): Тендеры по статусам.
        win_rate (float): Процент выигранных тендеров.
        total_budget (Decimal): Общий бюджет тендеров.
        total_our_price (Decimal): Общая сумма наших заявок.
    """

    total_tenders: int = 0
    tenders_by_status: dict[str, int] = Field(default_factory=dict)
    win_rate: float = 0.0
    total_budget: Decimal = Decimal("0")
    total_our_price: Decimal = Decimal("0")


class WarehouseAnalytics(BaseModel):
    """Schema for warehouse analytics summary.

    Атрибуты:
        total_items (int): Общее количество позиций.
        low_stock_items (list): Позиции с низким остатком.
        total_value (Decimal): Общая стоимость склада.
        movements_summary (dict): Сводка по движениям за период.
    """

    total_items: int = 0
    low_stock_items: list[Any] = Field(default_factory=list)
    total_value: Decimal = Decimal("0")
    movements_summary: dict[str, Any] = Field(default_factory=dict)
