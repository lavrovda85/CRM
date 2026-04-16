"""Warehouse XLSX row import (shared by /warehouse/items/import and unified Excel import)."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WarehouseItem
from app.schemas.warehouse import WarehouseItemsImportResponse


async def import_warehouse_rows(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    rows: list[tuple[object, ...]],
) -> WarehouseItemsImportResponse:
    """Import warehouse items from sheet rows (first row = headers)."""
    if not rows:
        return WarehouseItemsImportResponse(
            created_count=0,
            updated_count=0,
            skipped_count=0,
            error_count=1,
            errors=["Empty sheet"],
        )

    header_row = rows[0]
    headers_norm = [(str(h).strip().lower() if h is not None else "") for h in header_row]

    aliases_to_field: dict[str, str] = {
        "название": "name",
        "наименование": "name",
        "name": "name",
        "артикул": "sku",
        "артикул (sku)": "sku",
        "sku": "sku",
        "код": "sku",
        "категория": "category",
        "category": "category",
        "ед. изм.": "unit",
        "ед. изм": "unit",
        "ед. изм. ": "unit",
        "unit": "unit",
        "единица": "unit",
        "количество": "quantity",
        "quantity": "quantity",
        "кол-во": "quantity",
        "мин. остаток": "min_quantity",
        "min остаток": "min_quantity",
        "minquantity": "min_quantity",
        "min_quantity": "min_quantity",
        "цена за ед.": "price",
        "цена за ед": "price",
        "цена": "price",
        "price": "price",
        "место хранения": "location",
        "location": "location",
        "склад": "location",
        "описание": "description",
        "description": "description",
    }

    def _norm_col(v: str) -> str:
        return v.replace("\u00a0", " ").strip().lower()

    col_to_field: dict[int, str] = {}
    for idx, h in enumerate(headers_norm):
        nh = _norm_col(h)
        if nh in aliases_to_field:
            col_to_field[idx] = aliases_to_field[nh]

    def _to_decimal(v: object) -> Decimal | None:
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        try:
            s = str(v).strip().replace(",", ".")
            if s == "":
                return None
            return Decimal(s)
        except Exception:
            return None

    created_count = 0
    updated_count = 0
    skipped_count = 0
    errors: list[str] = []

    sku_col_indexes = [idx for idx, f in col_to_field.items() if f == "sku"]
    sku_idx = sku_col_indexes[0] if sku_col_indexes else None
    existing_by_sku: dict[str, WarehouseItem] = {}
    if sku_idx is not None:
        skus_in_sheet: set[str] = set()
        for r in rows[1:]:
            if sku_idx >= len(r):
                continue
            raw_sku = r[sku_idx]
            if raw_sku is None:
                continue
            s = str(raw_sku).strip()
            if s:
                skus_in_sheet.add(s)
        if skus_in_sheet:
            result = await db.execute(
                select(WarehouseItem).where(
                    WarehouseItem.company_id == company_id,
                    WarehouseItem.sku.in_(list(skus_in_sheet)),
                )
            )
            for it in result.scalars().all():
                existing_by_sku[it.sku] = it

    for row_idx, r in enumerate(rows[1:], start=2):
        try:
            if not isinstance(r, tuple):
                continue

            sku_value = None
            if sku_idx is not None and sku_idx < len(r):
                if r[sku_idx] is not None:
                    sku_value = str(r[sku_idx]).strip()

            if not sku_value:
                skipped_count += 1
                continue

            def _get(field: str) -> object:
                for c_idx, f in col_to_field.items():
                    if f == field and c_idx < len(r):
                        return r[c_idx]
                return None

            name_val = _get("name")
            category_val = _get("category") or "materials"
            unit_val = _get("unit") or "pcs"

            qty = _to_decimal(_get("quantity")) or Decimal("0")
            min_qty = _to_decimal(_get("min_quantity")) or Decimal("0")
            price = _to_decimal(_get("price")) or Decimal("0")

            desc = _get("description")
            location = _get("location")

            name_str = str(name_val).strip() if name_val is not None else ""
            if not name_str:
                skipped_count += 1
                continue

            existing = existing_by_sku.get(sku_value)
            if existing:
                await db.execute(
                    update(WarehouseItem)
                    .where(WarehouseItem.id == existing.id)
                    .values(
                        name=name_str,
                        category=str(category_val).strip() or "materials",
                        unit=str(unit_val).strip() or "pcs",
                        quantity=qty,
                        min_quantity=min_qty,
                        price=price,
                        description=str(desc).strip() if desc not in (None, "") else None,
                        location=str(location).strip() if location not in (None, "") else None,
                    )
                )
                updated_count += 1
            else:
                item = WarehouseItem(
                    company_id=company_id,
                    name=name_str,
                    sku=sku_value,
                    category=str(category_val).strip() or "materials",
                    unit=str(unit_val).strip() or "pcs",
                    quantity=qty,
                    min_quantity=min_qty,
                    price=price,
                    description=str(desc).strip() if desc not in (None, "") else None,
                    location=str(location).strip() if location not in (None, "") else None,
                )
                db.add(item)
                await db.flush()
                created_count += 1

        except Exception as exc:
            errors.append(f"Row {row_idx}: {exc}")
            skipped_count += 1

    error_count = len(errors)
    return WarehouseItemsImportResponse(
        created_count=created_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
        error_count=error_count,
        errors=errors[:20],
    )
