"""MCP tools for warehouse/inventory management in SPEC CRM/ERP.

Uses ``warehouse_operations`` and ORM — same rules as REST ``/api/v1/warehouse``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.exceptions import NotFoundError, ValidationError
from app.mcp.actor_context import current_mcp_user_sub
from app.mcp.server import mcp
from app.models import Task, WarehouseItem
from app.schemas.warehouse import ReservationResponse, WarehouseMovementResponse
from app.services import warehouse_operations


def _parse_uuid(raw: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(raw).strip())
    except ValueError as exc:
        raise ValidationError(field, "Must be a valid UUID") from exc


@mcp.tool()
async def check_stock(
    item_id: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """Check warehouse stock levels for items.

    Args:
        item_id: If set, return that single item (if it exists).
        category: Optional filter: materials, tools, consumables, equipment.

    Returns:
        List of stock rows: id, name, sku, category, unit, quantity,
        reserved_quantity, available, min_quantity, price.
    """
    async with async_session_factory() as session:
        stmt = select(WarehouseItem).order_by(WarehouseItem.name)
        if item_id:
            iid = _parse_uuid(item_id, "item_id")
            stmt = stmt.where(WarehouseItem.id == iid)
        elif category and str(category).strip():
            stmt = stmt.where(WarehouseItem.category == str(category).strip())

        result = await session.execute(stmt.limit(500))
        rows = result.scalars().all()

    return [
        {
            "id": str(it.id),
            "name": it.name,
            "sku": it.sku,
            "category": it.category,
            "unit": it.unit,
            "quantity": float(it.quantity),
            "reserved_quantity": float(it.reserved_quantity),
            "available": float(it.quantity - it.reserved_quantity),
            "min_quantity": float(it.min_quantity),
            "price": float(it.price),
        }
        for it in rows
    ]


@mcp.tool()
async def reserve_materials(
    task_id: str,
    items: list[dict],
) -> dict:
    """Reserve materials from warehouse for a specific task.

    Args:
        task_id: Task UUID.
        items: Each element: {"item_id": "uuid", "quantity": number}.

    Returns:
        task_id, reserved_items, total_cost, reserved_at.
    """
    tid = _parse_uuid(task_id, "task_id")

    async with async_session_factory() as session:
        task_row = await session.get(Task, tid)
        if task_row is None:
            raise NotFoundError("Task", task_id)

        reserved_items: list[dict] = []
        total_cost = Decimal("0")
        for entry in items or []:
            if not isinstance(entry, dict):
                raise ValidationError("items", "Each item must be an object with item_id and quantity")
            raw_iid = entry.get("item_id")
            qty_raw = entry.get("quantity")
            if raw_iid is None or qty_raw is None:
                raise ValidationError("items", "Each item needs item_id and quantity")
            iid = _parse_uuid(str(raw_iid), "item_id")
            try:
                qty = Decimal(str(qty_raw))
            except Exception as exc:
                raise ValidationError("items", f"Invalid quantity for item {raw_iid!r}") from exc
            if qty <= 0:
                raise ValidationError("items", "quantity must be positive")

            item_before = await session.get(WarehouseItem, iid)
            if item_before is None:
                raise NotFoundError("WarehouseItem", str(iid))
            price = item_before.price
            res = await warehouse_operations.create_reservation(session, item_id=iid, task_id=tid, quantity=qty)
            total_cost += qty * Decimal(str(price))
            reserved_items.append(
                {
                    "item_id": str(iid),
                    "quantity": float(qty),
                    "status": res.status,
                }
            )

        await session.commit()

    return {
        "task_id": str(tid),
        "reserved_items": reserved_items,
        "total_cost": float(total_cost.quantize(Decimal("0.01"))),
        "reserved_at": datetime.now(timezone.utc).isoformat(),
    }


@mcp.tool()
async def record_movement(
    item_id: str,
    movement_type: str,
    quantity: float,
    task_id: str | None = None,
    reason: str | None = None,
) -> dict:
    """Record an inventory movement (intake, consumption, write-off, transfer, return)."""
    iid = _parse_uuid(item_id, "item_id")
    actor = uuid.UUID(current_mcp_user_sub())
    try:
        qty = Decimal(str(quantity))
    except Exception as exc:
        raise ValidationError("quantity", "Must be a positive number") from exc
    if qty <= 0:
        raise ValidationError("quantity", "Must be positive")

    task_uuid: uuid.UUID | None = None
    if task_id and str(task_id).strip():
        task_uuid = _parse_uuid(task_id, "task_id")

    async with async_session_factory() as session:
        try:
            movement, new_qty = await warehouse_operations.record_movement(
                session,
                item_id=iid,
                movement_type=movement_type.strip(),
                quantity=qty,
                user_id=actor,
                task_id=task_uuid,
                reason=reason,
                destination=None,
            )
        except ValueError as exc:
            raise ValidationError("movement_type", str(exc)) from exc
        await session.commit()

    data = WarehouseMovementResponse.model_validate(movement).model_dump(mode="json")
    data["new_quantity"] = float(new_qty)
    data["recorded_at"] = movement.created_at.isoformat() if movement.created_at else None
    return data
