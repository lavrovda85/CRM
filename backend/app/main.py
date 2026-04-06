"""FastAPI application entry point.

Создаёт и настраивает экземпляр FastAPI с middleware,
роутерами и обработчиками исключений.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.core.config import get_settings
from app.core.exceptions import HVACBaseError

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle handler.

    Выполняет инициализацию при старте и очистку при остановке.
    """
    settings = get_settings()
    logger.info("Starting HVAC CRM/ERP Platform", version=settings.app_version)
    yield
    logger.info("Shutting down HVAC CRM/ERP Platform")


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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
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

    from app.api.v1 import (
        analytics,
        boards,
        clients,
        deals,
        depreciation,
        documents,
        references,
        tasks,
        templates,
        tenders,
        time_tracking,
        warehouse,
    )

    api_prefix = "/api/v1"
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
    app.include_router(references.router, prefix=api_prefix, tags=["References"])
    app.include_router(analytics.router, prefix=api_prefix, tags=["Analytics"])

    @app.get("/health", tags=["System"])
    async def health_check() -> dict:
        return {"status": "healthy", "version": settings.app_version}

    return app


app = create_app()
