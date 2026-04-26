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

    try:
        from app.core.schema_bootstrap import ensure_deploy_jobs_table

        await ensure_deploy_jobs_table()
    except Exception as exc:
        logger.warning("ensure_deploy_jobs_table failed: %s", exc)

    try:
        from app.core.schema_bootstrap import ensure_minimal_equipment_tenant_ddl

        await ensure_minimal_equipment_tenant_ddl()
        logger.info("ensure_minimal_equipment_tenant_ddl completed")
    except Exception as exc:
        logger.error("ensure_minimal_equipment_tenant_ddl failed: %s", exc)

    if settings.debug or settings.schema_bootstrap_on_startup:
        from app.core.schema_bootstrap import ensure_application_schema

        await ensure_application_schema()
        logger.info("Database schema ensured (BACKEND_DEBUG or SCHEMA_BOOTSTRAP_ON_STARTUP)")

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
        admin_deploy,
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
        excel_import,
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
    app.include_router(excel_import.router, prefix=api_prefix, tags=["Import"])
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
    app.include_router(admin_deploy.router, prefix=api_prefix, tags=["Admin Deploy"])

    @app.get("/health", tags=["System"])
    async def health_check() -> dict:
        return {"status": "healthy", "version": settings.app_version}

    return app


app = create_app()
