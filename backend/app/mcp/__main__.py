"""Allow running MCP server as ``python -m app.mcp``.

Делегирует запуск функции main() из server модуля.
"""

from app.mcp.server import main

main()
