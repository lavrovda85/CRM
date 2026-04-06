"""Discovery and caching of FastMCP tool callables for OpenAI function calling."""

from __future__ import annotations

import importlib
import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from app.services.ai_assistant.constants import MCP_TOOL_MODULES

_TOOL_REGISTRY: dict[str, Callable[..., Awaitable[Any]]] | None = None


def _ensure_mcp_modules_loaded() -> None:
    for mod in MCP_TOOL_MODULES:
        importlib.import_module(mod)


def unwrap_tool_callable(obj: Any) -> Callable[..., Awaitable[Any]] | None:
    """Resolve FastMCP / decorator wrappers to an async callable."""
    seen: set[int] = set()
    cur: Any = obj
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if inspect.iscoroutinefunction(cur):
            return cur  # type: ignore[return-value]
        nxt = getattr(cur, "fn", None)
        if nxt is None:
            nxt = getattr(cur, "__wrapped__", None)
        cur = nxt
    return None


def _build_tool_registry() -> dict[str, Callable[..., Awaitable[Any]]]:
    registry: dict[str, Callable[..., Awaitable[Any]]] = {}
    _ensure_mcp_modules_loaded()
    for modname in MCP_TOOL_MODULES:
        mod = importlib.import_module(modname)
        for name in dir(mod):
            if name.startswith("_"):
                continue
            raw = getattr(mod, name, None)
            fn = unwrap_tool_callable(raw)
            if fn is None:
                continue
            if getattr(fn, "__module__", None) != mod.__name__:
                continue
            if name in registry:
                raise RuntimeError(f"Duplicate MCP tool name: {name}")
            registry[name] = fn
    return registry


def get_tool_registry() -> dict[str, Callable[..., Awaitable[Any]]]:
    """Return cached mapping of tool name -> unwrapped async function."""
    global _TOOL_REGISTRY
    if _TOOL_REGISTRY is None:
        _TOOL_REGISTRY = _build_tool_registry()
    return _TOOL_REGISTRY
