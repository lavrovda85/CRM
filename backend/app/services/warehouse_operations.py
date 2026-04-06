"""Warehouse inventory operations shared by REST API and MCP.

Centralizes movement recording and reservations so MCP tools
match ``/api/v1/warehouse`` behaviour.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, WarehouseInsufficientStockError
from app.models import WarehouseItem, WarehouseMovement, WarehouseReservation

CONSUMPTION_TYPES = frozenset({"consumption", "write_off", "transfer"})
INTAKE_TYPES = frozenset({"intake", "return"})
ALLOWED_MOVEMENT_TYPES = CONSUMPTION_TYPES | INTAKE_TYPES


async def record_movement(
    session: AsyncSession,
    *,
    item_id: uuid.UUID,
    movement_type: str,
    quantity: Decimal,
    user_id: uuid.UUID,
    task_id: uuid.UUID | None = None,
    reason: str | None = None,
    destination: str | None = None,
) -> tuple[WarehouseMovement, Decimal]:
    """Persist a movement and update item quantity.

    Args:
        session: DB session (caller commits).
        item_id: Warehouse item UUID.
        movement_type: One of intake, return, consumption, write_off, transfer.
        quantity: Positive quantity for the movement.
        user_id: Acting user (audit).
        task_id: Optional linked task.
        reason: Optional comment.
        destination: Optional destination for transfers.

    Returns:
        Tuple of (created movement ORM row, new on-hand quantity after update).

    Raises:
        NotFoundError: Item not found.
        WarehouseInsufficientStockError: Consumption exceeds available.
        ValueError: Unknown movement_type.
    """
    if movement_type not in ALLOWED_MOVEMENT_TYPES:
        raise ValueError(
            f"Invalid movement_type {movement_type!r}; allowed: {sorted(ALLOWED_MOVEMENT_TYPES)}"
        )

    item_result = await session.execute(select(WarehouseItem).where(WarehouseItem.id == item_id))
    item = item_result.scalar_one_or_none()
    if not item:
        raise NotFoundError("WarehouseItem", str(item_id))

    if movement_type in CONSUMPTION_TYPES:
        available = item.quantity - item.reserved_quantity
        if quantity > available:
            raise WarehouseInsufficientStockError(
                item_id=str(item_id),
                requested=float(quantity),
                available=float(available),
            )
        new_quantity = item.quantity - quantity
    elif movement_type in INTAKE_TYPES:
        new_quantity = item.quantity + quantity
    else:
        new_quantity = item.quantity

    await session.execute(
        update(WarehouseItem).where(WarehouseItem.id == item_id).values(quantity=new_quantity)
    )

    movement = WarehouseMovement(
        item_id=item_id,
        task_id=task_id,
        user_id=user_id,
        movement_type=movement_type,
        quantity=quantity,
        unit_price=item.price,
        reason=reason,
        destination=destination,
    )
    session.add(movement)
    await session.flush()
    await session.refresh(movement)
    return movement, new_quantity


async def create_reservation(
    session: AsyncSession,
    *,
    item_id: uuid.UUID,
    task_id: uuid.UUID,
    quantity: Decimal,
) -> WarehouseReservation:
    """Reserve quantity for a task; updates ``reserved_quantity`` on the item.

    Raises:
        NotFoundError: Item not found.
        WarehouseInsufficientStockError: Not enough free quantity.
    """
    item_result = await session.execute(select(WarehouseItem).where(WarehouseItem.id == item_id))
    item = item_result.scalar_one_or_none()
    if not item:
        raise NotFoundError("WarehouseItem", str(item_id))

    available = item.quantity - item.reserved_quantity
    if quantity > available:
        raise WarehouseInsufficientStockError(
            item_id=str(item_id),
            requested=float(quantity),
            available=float(available),
        )

    await session.execute(
        update(WarehouseItem)
        .where(WarehouseItem.id == item_id)
        .values(reserved_quantity=item.reserved_quantity + quantity)
    )

    reservation = WarehouseReservation(
        item_id=item_id,
        task_id=task_id,
        quantity=quantity,
        status="reserved",
    )
    session.add(reservation)
    await session.flush()
    await session.refresh(reservation)
    return reservation
