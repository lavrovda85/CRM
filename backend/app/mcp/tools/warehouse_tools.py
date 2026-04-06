"""MCP tools for warehouse/inventory management in HVAC CRM/ERP.

Инструменты для проверки остатков, резервирования материалов
и учёта складских движений через MCP-протокол.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from app.mcp.server import mcp


@mcp.tool()
async def check_stock(
    item_id: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """Check warehouse stock levels for items.

    Проверяет текущие остатки на складе. Можно запросить конкретную
    позицию по ID или отфильтровать по категории.

    Args:
        item_id (str | None): UUID конкретной складской позиции.
            Если указан — возвращается одна позиция.
        category (str | None): Фильтр по категории:
            "materials", "tools", "consumables", "equipment".
            Если не указан — все позиции.

    Returns:
        list[dict]: Список складских позиций, каждая содержит id, name,
            sku, category, unit, quantity, reserved_quantity,
            available (quantity - reserved_quantity), min_quantity, price.

    Example:
        AI agent: "Проверь остатки медной трубки на складе"
        >>> check_stock(category="materials")
        AI agent: "Сколько осталось позиции с артикулом X?"
        >>> check_stock(item_id="item-uuid-...")
    """
    # TODO: If item_id — SELECT * FROM warehouse_items WHERE id = item_id
    # TODO: If category — SELECT * FROM warehouse_items WHERE category = category
    # TODO: Calculate available = quantity - reserved_quantity
    # TODO: Return list sorted by name
    return [
        {
            "id": item_id or str(uuid.uuid4()),
            "name": "Placeholder item",
            "sku": "PH-001",
            "category": category or "materials",
            "unit": "pcs",
            "quantity": 100.0,
            "reserved_quantity": 10.0,
            "available": 90.0,
            "min_quantity": 20.0,
            "price": 500.0,
        }
    ]


@mcp.tool()
async def reserve_materials(
    task_id: str,
    items: list[dict],
) -> dict:
    """Reserve materials from warehouse for a specific task.

    Резервирует материалы под задачу. Увеличивает reserved_quantity
    у позиций и создаёт записи WarehouseReservation.

    Args:
        task_id (str): UUID задачи, для которой резервируются материалы.
        items (list[dict]): Список позиций для резервирования, каждая:
            {"item_id": "uuid", "quantity": 5.0}.
            item_id — UUID складской позиции, quantity — количество.

    Returns:
        dict: Результат резервирования с полями task_id, reserved_items
            (список {item_id, quantity, status}), total_cost, reserved_at.

    Example:
        AI agent: "Зарезервируй 10 метров медной трубки и 2 кронштейна для задачи монтажа"
        >>> reserve_materials(
        ...     task_id="task-uuid-...",
        ...     items=[
        ...         {"item_id": "copper-tube-uuid", "quantity": 10.0},
        ...         {"item_id": "bracket-uuid", "quantity": 2.0},
        ...     ],
        ... )
    """
    # TODO: For each item in items:
    #   - SELECT warehouse_item, check available >= quantity
    #   - Raise WarehouseInsufficientStockError if not enough
    #   - UPDATE warehouse_items SET reserved_quantity += quantity
    #   - INSERT INTO warehouse_reservations (item_id, task_id, quantity, status='reserved')
    # TODO: Calculate total_cost = sum(quantity * item.price)
    now = datetime.utcnow().isoformat()
    reserved_items = [
        {"item_id": item["item_id"], "quantity": item["quantity"], "status": "reserved"}
        for item in items
    ]
    return {
        "task_id": task_id,
        "reserved_items": reserved_items,
        "total_cost": 0.0,
        "reserved_at": now,
    }


@mcp.tool()
async def record_movement(
    item_id: str,
    movement_type: str,
    quantity: float,
    task_id: str | None = None,
    reason: str | None = None,
) -> dict:
    """Record an inventory movement (intake, consumption, write-off, etc.).

    Регистрирует складское движение: приход, расход, списание, перемещение
    или возврат. Обновляет текущее количество на складе.

    Args:
        item_id (str): UUID складской позиции.
        movement_type (str): Тип движения:
            "intake" — приход на склад,
            "consumption" — расход (списание на задачу),
            "write_off" — списание (брак, истечение срока),
            "transfer" — перемещение между складами,
            "return" — возврат на склад.
        quantity (float): Количество (всегда положительное число).
        task_id (str | None): UUID задачи (для расхода, привязанного к задаче).
        reason (str | None): Причина / комментарий к операции.

    Returns:
        dict: Запись о движении с полями id, item_id, movement_type,
            quantity, task_id, reason, new_quantity, recorded_at.

    Example:
        AI agent: "Зафиксируй расход 5 метров медной трубки на задачу монтажа"
        >>> record_movement(
        ...     item_id="copper-tube-uuid",
        ...     movement_type="consumption",
        ...     quantity=5.0,
        ...     task_id="task-uuid-...",
        ...     reason="Использовано при монтаже сплит-системы",
        ... )
    """
    # TODO: SELECT warehouse_item by item_id, raise NotFoundError if absent
    # TODO: Validate movement_type in allowed set
    # TODO: For consumption/write_off: check quantity <= available
    # TODO: UPDATE warehouse_items.quantity (+ for intake/return, - for consumption/write_off)
    # TODO: If consumption from reservation: UPDATE reservation status to 'consumed'
    # TODO: INSERT INTO warehouse_movements
    movement_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    return {
        "id": movement_id,
        "item_id": item_id,
        "movement_type": movement_type,
        "quantity": quantity,
        "task_id": task_id,
        "reason": reason,
        "new_quantity": 0.0,
        "recorded_at": now,
    }
