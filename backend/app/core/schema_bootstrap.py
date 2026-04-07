"""Idempotent PostgreSQL schema creation and patches.

Mirrors the historical dev-only path that ran under ``BACKEND_DEBUG`` so production
can apply the same steps once via ``SCHEMA_BOOTSTRAP_ON_STARTUP`` without opening CORS.
"""

from __future__ import annotations

import app.models  # noqa: F401 — register models on Base.metadata
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def ensure_application_schema() -> None:
    """Run ``create_all`` and additive SQL (safe to re-run)."""
    from app.core.database import engine

    async with engine.begin() as conn:
        await _apply_schema_patches(conn)


async def _apply_schema_patches(conn: AsyncConnection) -> None:
    from app.core.database import Base

    # Serialize create_all when multiple uvicorn workers start together (same DB).
    await conn.execute(text("SELECT pg_advisory_xact_lock(872364531)"))
    await conn.run_sync(Base.metadata.create_all)
    # create_all does not alter existing tables; keep additive DDL in sync with dev.
    await conn.execute(text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS tender_id uuid NULL"))
    await conn.execute(text("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS tender_link varchar(1000) NULL"))
    await conn.execute(text("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS customer_id uuid NULL"))
    await conn.execute(text("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS guarantee_amount numeric(15,2) NULL"))
    await conn.execute(text("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS max_price numeric(15,2) NULL"))
    await conn.execute(text("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS min_price numeric(15,2) NULL"))
    await conn.execute(text("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS trade_start_at timestamptz NULL"))
    await conn.execute(text("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS trade_end_at timestamptz NULL"))
    await conn.execute(
        text(
            "ALTER TABLE tenders ADD COLUMN IF NOT EXISTS tender_analysis jsonb "
            "NOT NULL DEFAULT '{}'::jsonb"
        )
    )
    await conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS deleted_at timestamptz NULL"))
    await conn.execute(
        text(
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS deleted_by uuid NULL "
            "REFERENCES users(id)"
        )
    )
    await conn.execute(
        text(
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS requested_by uuid NULL "
            "REFERENCES users(id)"
        )
    )
    await conn.execute(
        text(
            "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS visibility varchar(32) "
            "NOT NULL DEFAULT 'company'"
        )
    )
    await conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS task_co_assignees ("
            "task_id uuid NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,"
            "user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,"
            "PRIMARY KEY (task_id, user_id))"
        )
    )
    await conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS task_observers ("
            "task_id uuid NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,"
            "user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,"
            "PRIMARY KEY (task_id, user_id))"
        )
    )
    await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url varchar(1000) NULL"))
    _dc = "00000000-0000-4000-8000-000000000001"
    await conn.execute(
        text(
            f"INSERT INTO companies (id, name, slug, is_active, settings, created_at, updated_at) "
            f"VALUES ('{_dc}'::uuid, 'Default organization', 'default', true, '{{}}'::jsonb, now(), now()) "
            f"ON CONFLICT (id) DO NOTHING"
        )
    )
    _tenant_tables = (
        "tasks",
        "clients",
        "deal_stages",
        "deals",
        "tenders",
        "boards",
        "task_templates",
        "documents",
        "warehouse_items",
        "warehouse_movements",
        "warehouse_reservations",
        "equipment",
        "equipment_usage",
        "depreciation_records",
        "reference_items",
        "notifications",
        "time_entries",
    )
    await conn.execute(text('ALTER TABLE "references" ADD COLUMN IF NOT EXISTS company_id uuid'))
    await conn.execute(text('ALTER TABLE "chat_rooms" ADD COLUMN IF NOT EXISTS company_id uuid'))
    for tbl in _tenant_tables:
        await conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS company_id uuid"))
    for tbl in (*_tenant_tables, "references", "chat_rooms"):
        qt = '"references"' if tbl == "references" else tbl
        await conn.execute(text(f"UPDATE {qt} SET company_id = '{_dc}'::uuid WHERE company_id IS NULL"))
    for tbl in (*_tenant_tables, "references", "chat_rooms"):
        qt = '"references"' if tbl == "references" else tbl
        await conn.execute(text(f"ALTER TABLE {qt} ALTER COLUMN company_id SET NOT NULL"))
    await conn.execute(
        text(
            "INSERT INTO user_company_memberships "
            "(id, user_id, company_id, role, is_default, created_at, updated_at) "
            f"SELECT gen_random_uuid(), u.id, '{_dc}'::uuid, NULL, true, now(), now() "
            "FROM users u WHERE NOT EXISTS ("
            "SELECT 1 FROM user_company_memberships m WHERE m.user_id = u.id"
            ")"
        )
    )
    await conn.execute(text("ALTER TABLE warehouse_items DROP CONSTRAINT IF EXISTS warehouse_items_sku_key"))
    await conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_warehouse_items_company_sku "
            "ON warehouse_items (company_id, sku)"
        )
    )
    await conn.execute(text("ALTER TABLE equipment DROP CONSTRAINT IF EXISTS equipment_serial_number_key"))
    await conn.execute(
        text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_equipment_company_serial "
            "ON equipment (company_id, serial_number)"
        )
    )
    await conn.execute(text('ALTER TABLE "references" DROP CONSTRAINT IF EXISTS references_code_key'))
    await conn.execute(
        text(
            'CREATE UNIQUE INDEX IF NOT EXISTS uq_references_company_code '
            'ON "references" (company_id, code)'
        )
    )
    await conn.execute(text('ALTER TABLE "chat_rooms" DROP CONSTRAINT IF EXISTS chat_rooms_code_key'))
    await conn.execute(
        text(
            'CREATE UNIQUE INDEX IF NOT EXISTS uq_chat_rooms_company_code '
            'ON "chat_rooms" (company_id, code)'
        )
    )
