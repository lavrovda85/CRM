"""OpenAI Chat Completions tool schema for ``invoke_crm_tool``."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any


def openai_tools_schema(registry: dict[str, Callable[..., Awaitable[Any]]]) -> list[dict[str, Any]]:
    names = sorted(registry.keys())
    return [
        {
            "type": "function",
            "function": {
                "name": "invoke_crm_tool",
                "description": (
                    "Execute one backend CRM tool. Pass ONLY valid keyword args for that tool inside "
                    "`arguments`. For `create_task` you MUST always include a non-empty `title` string "
                    "(task headline). For template-based tasks, call `list_templates` first to obtain "
                    "`template_id` (UUID), then `create_task` with both `title` and `template_id`. "
                    "For many rows from a table or list, use `bulk_create_tasks` with `items` (array of "
                    "objects with `title`, optional `due_date`, `assignee_query` / `assigned_to`, and optional "
                    "`co_assignee_ids` / `observer_ids`."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tool_name": {
                            "type": "string",
                            "enum": names,
                            "description": "Registered MCP tool function name (snake_case).",
                        },
                        "arguments": {
                            "type": "object",
                            "description": (
                                "Flat keyword arguments for the tool, e.g. search_tasks: {q, limit?}; "
                                "search_tenders_on_web: MUST include `query` (search string, e.g. region + topic) "
                                "or synonym `q` / `keywords`; optional prefer_zakupki_gov (bool), max_results (int), "
                                "enrich (bool, default true — returns `summary` per row); "
                                "only_open_deadlines (bool, default true — drop expired submission deadlines vs server UTC); "
                                "exclude_urls (string[], optional — skip notices already shown; injected on «ещё/следующие»). "
                                "import_tender_from_url / fetch_tender_from_url: {url} (or link/href); "
                                "optional enriched_summary, enriched_submission_deadline_utc from last search row. "
                                "create_task: {title, template_id?, ...}; bulk_create_tasks: {items: [...], "
                                "template_id?, client_id?} (per-row fields may include `assigned_to`, "
                                "`co_assignee_ids`, and `observer_ids`); delete_task: {task_id} (UUID from search_tasks)."
                            ),
                        },
                    },
                    "required": ["tool_name", "arguments"],
                },
            },
        }
    ]
