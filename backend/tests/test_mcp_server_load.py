"""Ensure MCP server module and tool packages load (regression guard)."""

from __future__ import annotations

import pytest


def test_mcp_server_and_tool_modules_import() -> None:
    """Importing the server registers tools from all tool modules."""
    pytest.importorskip("fastmcp", reason="fastmcp is required for MCP server")
    from app.mcp import server as mcp_server

    assert mcp_server.mcp is not None
    assert mcp_server.mcp.name
