"""Normalize and filter LLM tool arguments before MCP invocation."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any


def normalize_tool_arguments(tool_name: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Map common LLM mistakes to real MCP parameter names before filtering by signature.

    Модели часто передают ``name``/``subject`` вместо обязательного ``title`` у ``create_task``;
    без этого ключи отбрасываются ``prepare_kwargs`` и заголовок остаётся пустым.
    """
    args = dict(raw or {})
    if tool_name == "bulk_create_tasks":
        if "items" not in args and isinstance(args.get("tasks"), list):
            args["items"] = args["tasks"]
        return args
    if tool_name == "search_tenders_on_web":
        q = args.get("query")
        if q is None or not str(q).strip():
            for key in ("q", "keywords", "search_query", "text", "search", "prompt", "subject"):
                val = args.get(key)
                if val is not None and str(val).strip():
                    args["query"] = str(val).strip()
                    break
        elif isinstance(q, str):
            args["query"] = q.strip()
        return args
    if tool_name in ("import_tender_from_url", "fetch_tender_from_url"):
        u = args.get("url")
        if u is None or not str(u).strip():
            for key in ("link", "href", "tender_url", "page_url", "source_url"):
                val = args.get(key)
                if val is not None and str(val).strip():
                    args["url"] = str(val).strip()
                    break
        return args
    if tool_name != "create_task":
        return args
    t = args.get("title")
    if t is not None and str(t).strip():
        args["title"] = str(t).strip()
        return args
    for key in ("name", "task_title", "task_name", "subject", "heading", "label"):
        val = args.get(key)
        if val is not None and str(val).strip():
            args["title"] = str(val).strip()
            break
    return args


def prepare_kwargs(fn: Callable[..., Awaitable[Any]], raw: dict[str, Any]) -> dict[str, Any]:
    """Drop unknown keys unless the callable accepts **kwargs."""
    sig = inspect.signature(fn)
    params = sig.parameters.values()
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params):
        return dict(raw)
    names = {p.name for p in params if p.kind not in (inspect.Parameter.VAR_POSITIONAL,)}
    return {k: v for k, v in raw.items() if k in names}
