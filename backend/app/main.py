"""FastAPI application entry point.

Создаёт и настраивает экземпляр FastAPI с middleware,
роутерами и обработчиками исключений.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

try:
    import structlog
except ModuleNotFoundError:  # pragma: no cover
    structlog = None  # type: ignore[assignment]

import logging


class _LoggerCompat:
    """Compatibility wrapper for environments without `structlog`.

    This keeps the app functional when `structlog` isn't available locally
    (e.g. lint-only environments), while ignoring extra keyword fields.
    """

    def __init__(self, base_logger: logging.Logger) -> None:
        self._base_logger = base_logger

    def info(self, msg: str, **_: object) -> None:
        self._base_logger.info(msg)

    def warning(self, msg: str, **_: object) -> None:
        self._base_logger.warning(msg)

    def error(self, msg: str, **_: object) -> None:
        self._base_logger.error(msg)
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.core.config import get_settings
from app.core.exceptions import HVACBaseError

logger = structlog.get_logger() if structlog is not None else _LoggerCompat(logging.getLogger(__name__))


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle handler.

    Выполняет инициализацию при старте и очистку при остановке.
    В debug-режиме автоматически создаёт таблицы если они не существуют.
    """
    settings = get_settings()
    logger.info("Starting SPEC CRM Platform", version=settings.app_version)

    if settings.debug:
        from app.core.database import Base, engine
        import app.models  # noqa: F401
        from sqlalchemy import text

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # In debug mode we rely on `create_all`, which does NOT alter existing tables.
            # Since we iteratively extend models, ensure critical missing columns exist.
            # This keeps the app running without requiring Alembic migrations during dev.
            await conn.execute(
                text("ALTER TABLE documents ADD COLUMN IF NOT EXISTS tender_id uuid NULL")
            )
            await conn.execute(
                text("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS tender_link varchar(1000) NULL")
            )
            await conn.execute(
                text("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS customer_id uuid NULL")
            )
            await conn.execute(
                text("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS guarantee_amount numeric(15,2) NULL")
            )
            await conn.execute(
                text("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS max_price numeric(15,2) NULL")
            )
            await conn.execute(
                text("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS min_price numeric(15,2) NULL")
            )
            await conn.execute(
                text("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS trade_start_at timestamptz NULL")
            )
            await conn.execute(
                text("ALTER TABLE tenders ADD COLUMN IF NOT EXISTS trade_end_at timestamptz NULL")
            )
            await conn.execute(
                text(
                    "ALTER TABLE tenders ADD COLUMN IF NOT EXISTS tender_analysis jsonb "
                    "NOT NULL DEFAULT '{}'::jsonb"
                )
            )
            await conn.execute(
                text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS deleted_at timestamptz NULL")
            )
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
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url varchar(1000) NULL")
            )
            # Multi-tenancy: ensure default company, backfill company_id, constraints (idempotent).
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
            await conn.execute(
                text('ALTER TABLE "references" ADD COLUMN IF NOT EXISTS company_id uuid')
            )
            await conn.execute(
                text('ALTER TABLE "chat_rooms" ADD COLUMN IF NOT EXISTS company_id uuid')
            )
            for tbl in _tenant_tables:
                await conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS company_id uuid"))
            for tbl in (*_tenant_tables, "references", "chat_rooms"):
                qt = '"references"' if tbl == "references" else tbl
                await conn.execute(
                    text(f"UPDATE {qt} SET company_id = '{_dc}'::uuid WHERE company_id IS NULL")
                )
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
            await conn.execute(
                text("ALTER TABLE equipment DROP CONSTRAINT IF EXISTS equipment_serial_number_key")
            )
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
        logger.info("Debug mode: database schema ensured")

    try:
        from app.core.database import async_session_factory
        from app.services import company_service

        async with async_session_factory() as db:
            await company_service.bootstrap_testing_tenant(db)
            await db.commit()
    except Exception as exc:
        logger.warning("bootstrap_testing_tenant failed: %s", exc)

    yield
    logger.info("Shutting down SPEC CRM Platform")


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Возвращает:
        Настроенный экземпляр FastAPI.
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        default_response_class=ORJSONResponse,
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    cors_origins: list[str] | str = settings.cors_origins
    if settings.debug:
        cors_origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=not settings.debug,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(HVACBaseError)
    async def hvac_exception_handler(request: Request, exc: HVACBaseError) -> ORJSONResponse:
        logger.warning(
            "Domain error",
            code=exc.code,
            message=exc.message,
            details=exc.details,
            path=str(request.url),
        )
        return ORJSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> ORJSONResponse:
        """Return rich debug info for unexpected exceptions.

        In production this returns a minimal error to avoid leaking internals.
        """
        logger.error(
            "Unhandled exception",
            error=str(exc),
            path=str(request.url),
        )

        if settings.debug:
            import traceback

            return ORJSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "Unhandled exception",
                        "details": {
                            "exception_type": exc.__class__.__name__,
                            "traceback": traceback.format_exc(),
                        },
                    }
                },
            )

        return ORJSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_SERVER_ERROR", "message": "Internal Server Error"}},
        )

    from app.api.v1 import (
        admin_settings,
        ai_assistant,
        analytics,
        auth,
        boards,
        clients,
        companies,
        deals,
        depreciation,
        documents,
        chat,
        notifications,
        references,
        tasks,
        templates,
        tenders,
        time_tracking,
        users,
        warehouse,
    )

    api_prefix = "/api/v1"
    app.include_router(auth.router, prefix=api_prefix, tags=["Auth"])
    app.include_router(companies.router, prefix=api_prefix)
    app.include_router(users.router, prefix=api_prefix, tags=["Users"])
    app.include_router(tasks.router, prefix=api_prefix, tags=["Tasks"])
    app.include_router(templates.router, prefix=api_prefix, tags=["Templates"])
    app.include_router(boards.router, prefix=api_prefix, tags=["Boards"])
    app.include_router(clients.router, prefix=api_prefix, tags=["Clients"])
    app.include_router(deals.router, prefix=api_prefix, tags=["Deals"])
    app.include_router(tenders.router, prefix=api_prefix, tags=["Tenders"])
    app.include_router(time_tracking.router, prefix=api_prefix, tags=["Time Tracking"])
    app.include_router(warehouse.router, prefix=api_prefix, tags=["Warehouse"])
    app.include_router(depreciation.router, prefix=api_prefix, tags=["Depreciation"])
    app.include_router(documents.router, prefix=api_prefix, tags=["Documents"])
    app.include_router(chat.router, prefix=api_prefix, tags=["Chat"])
    app.include_router(notifications.router, prefix=api_prefix, tags=["Notifications"])
    app.include_router(references.router, prefix=api_prefix, tags=["References"])
    app.include_router(analytics.router, prefix=api_prefix, tags=["Analytics"])
    app.include_router(ai_assistant.router, prefix=api_prefix, tags=["AI Assistant"])
    app.include_router(admin_settings.router, prefix=api_prefix, tags=["Admin Settings"])

    @app.get("/health", tags=["System"])
    async def health_check() -> dict:
        return {"status": "healthy", "version": settings.app_version}

    return app


app = create_app()
