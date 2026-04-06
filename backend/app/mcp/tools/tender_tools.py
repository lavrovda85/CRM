"""MCP tools for tender management in HVAC CRM/ERP.

Инструменты для создания, обновления статуса, привязки задач
и просмотра тендеров через MCP-протокол.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from app.mcp.server import mcp


@mcp.tool()
async def create_tender(
    title: str,
    source: str | None = None,
    budget: float | None = None,
    deadline: str | None = None,
    assigned_to: str | None = None,
) -> dict:
    """Create a new tender/bid in the system.

    Создаёт новый тендер с начальным статусом "search".
    Тендеры — отдельная от сделок сущность с собственным жизненным циклом.

    Args:
        title (str): Название тендера
            (например, "Поставка и монтаж VRF — ТЦ Мега").
        source (str | None): Источник тендера (площадка или заказчик,
            например, "zakupki.gov.ru", "Прямой заказчик").
        budget (float | None): Бюджет тендера в рублях.
        deadline (str | None): Крайний срок подачи заявки в формате ISO 8601
            (например, "2026-04-30").
        assigned_to (str | None): UUID ответственного менеджера.

    Returns:
        dict: Созданный тендер с полями id, title, source, budget, status,
            deadline, assigned_to, created_at.

    Example:
        AI agent: "Зарегистрируй новый тендер с zakupki.gov.ru"
        >>> create_tender(
        ...     title="Поставка и монтаж VRF-системы — Школа №5",
        ...     source="zakupki.gov.ru",
        ...     budget=2500000.0,
        ...     deadline="2026-04-30",
        ...     assigned_to="user-uuid-...",
        ... )
    """
    # TODO: INSERT INTO tenders (title, source, budget, deadline, assigned_to)
    # TODO: Set initial status = "search"
    tender_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    return {
        "id": tender_id,
        "title": title,
        "source": source,
        "budget": budget,
        "status": "search",
        "deadline": deadline,
        "assigned_to": assigned_to,
        "created_at": now,
    }


@mcp.tool()
async def update_tender_status(
    tender_id: str,
    status: str,
) -> dict:
    """Update the status of a tender.

    Обновляет статус тендера. Допустимые переходы:
    search -> participation -> won/lost, won -> execution -> completed.

    Args:
        tender_id (str): UUID тендера.
        status (str): Новый статус. Допустимые значения:
            "search", "participation", "won", "lost",
            "execution", "completed".

    Returns:
        dict: Обновлённый тендер с полями id, title, from_status,
            to_status, updated_at.

    Example:
        AI agent: "Мы выиграли тендер — обнови статус"
        >>> update_tender_status(
        ...     tender_id="tender-uuid-...",
        ...     status="won",
        ... )
    """
    # TODO: SELECT tender by tender_id, raise NotFoundError if absent
    # TODO: Validate status transition from current to new
    # TODO: UPDATE tenders SET status = status WHERE id = tender_id
    now = datetime.utcnow().isoformat()
    return {
        "id": tender_id,
        "title": "Placeholder tender",
        "from_status": "participation",
        "to_status": status,
        "updated_at": now,
    }


@mcp.tool()
async def link_tasks_to_tender(
    tender_id: str,
    task_ids: list[str],
) -> dict:
    """Link existing tasks to a tender.

    Привязывает одну или несколько задач к тендеру. Задачи получают
    ссылку на тендер для группировки и отчётности.

    Args:
        tender_id (str): UUID тендера.
        task_ids (list[str]): Список UUID задач для привязки.

    Returns:
        dict: Результат привязки с полями tender_id, linked_count,
            task_ids, linked_at.

    Example:
        AI agent: "Привяжи задачи монтажа и пусконаладки к тендеру"
        >>> link_tasks_to_tender(
        ...     tender_id="tender-uuid-...",
        ...     task_ids=["task-uuid-1", "task-uuid-2"],
        ... )
    """
    # TODO: SELECT tender by tender_id, raise NotFoundError if absent
    # TODO: UPDATE tasks SET tender_id = tender_id WHERE id IN (task_ids)
    # TODO: Verify all task_ids exist, collect not-found IDs
    now = datetime.utcnow().isoformat()
    return {
        "tender_id": tender_id,
        "linked_count": len(task_ids),
        "task_ids": task_ids,
        "linked_at": now,
    }


@mcp.tool()
async def list_tenders(
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List tenders with optional status filter.

    Возвращает список тендеров с возможностью фильтрации по статусу.
    Результаты отсортированы по дедлайну подачи (ближайшие первыми).

    Args:
        status (str | None): Фильтр по статусу тендера:
            "search", "participation", "won", "lost",
            "execution", "completed". Если не указан — все тендеры.
        limit (int): Максимальное количество результатов.
            По умолчанию 50, макс. 200.

    Returns:
        list[dict]: Список тендеров, каждый содержит id, title, source,
            budget, status, deadline, assigned_to, created_at.

    Example:
        AI agent: "Покажи все тендеры, в которых мы участвуем"
        >>> list_tenders(status="participation", limit=20)
    """
    # TODO: SELECT * FROM tenders WHERE status = status (if provided)
    # TODO: ORDER BY deadline ASC NULLS LAST, LIMIT min(limit, 200)
    return [
        {
            "id": str(uuid.uuid4()),
            "title": "Placeholder tender",
            "source": None,
            "budget": None,
            "status": status or "search",
            "deadline": None,
            "assigned_to": None,
            "created_at": datetime.utcnow().isoformat(),
        }
    ]
