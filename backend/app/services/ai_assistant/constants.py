"""Configuration for AI assistant tool discovery and safety gates."""

from __future__ import annotations

MCP_TOOL_MODULES: tuple[str, ...] = (
    "app.mcp.tools.task_tools",
    "app.mcp.tools.template_tools",
    "app.mcp.tools.crm_tools",
    "app.mcp.tools.tender_tools",
    "app.mcp.tools.warehouse_tools",
    "app.mcp.tools.excel_import_tools",
    "app.mcp.tools.analytics_tools",
    "app.mcp.tools.chat_tools",
    "app.mcp.tools.board_tools",
    "app.mcp.tools.user_tools",
)

DESTRUCTIVE_TOOLS = frozenset(
    {
        "delete_task",
        "bulk_delete_tasks",
        "delete_document",
        "delete_tender",
        "delete_board",
        "import_excel_workbook_base64",
    }
)
