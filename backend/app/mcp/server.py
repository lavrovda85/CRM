"""MCP server entry point for HVAC CRM/ERP platform.

Инициализирует FastMCP сервер и регистрирует все инструменты
из app.mcp.tools.* для управления платформой через AI-агентов.
Запуск: python -m app.mcp.server
"""

import logging

from fastmcp import FastMCP

from app.core.config import get_settings

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "HVAC CRM/ERP",
    description="MCP server for HVAC CRM/ERP platform management by AI agents",
)

import app.mcp.tools.task_tools  # noqa: E402, F401
import app.mcp.tools.template_tools  # noqa: E402, F401
import app.mcp.tools.crm_tools  # noqa: E402, F401
import app.mcp.tools.tender_tools  # noqa: E402, F401
import app.mcp.tools.warehouse_tools  # noqa: E402, F401
import app.mcp.tools.analytics_tools  # noqa: E402, F401


def main() -> None:
    """Launch MCP server with streamable HTTP transport.

    Запускает MCP сервер на хосте и порте, указанных
    в переменных окружения MCP_HOST и MCP_PORT.
    """
    settings = get_settings()
    logger.info(
        "Starting MCP server on %s:%s", settings.mcp_host, settings.mcp_port
    )
    mcp.run(
        transport="streamable-http",
        host=settings.mcp_host,
        port=settings.mcp_port,
    )


if __name__ == "__main__":
    main()
