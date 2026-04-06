"""Execute one MCP tool under the current HTTP user's actor context."""

from __future__ import annotations

import json
import logging
from contextvars import Token
from typing import Any

from app.core.exceptions import HVACBaseError
from app.core.security import CurrentUser
from app.core.database import async_session_factory
from app.mcp.actor_context import (
    reset_resolved_users_id,
    reset_tool_actor,
    set_resolved_users_id,
    set_tool_actor,
)
from app.services.user_identity import resolve_users_table_id
from app.services.ai_assistant.constants import DESTRUCTIVE_TOOLS
from app.services.ai_assistant.tool_arguments import normalize_tool_arguments, prepare_kwargs
from app.services.ai_assistant.tool_registry import get_tool_registry

logger = logging.getLogger(__name__)


def serialize_tool_result(payload: Any) -> str:
    def _default(o: object) -> str:
        return str(o)

    try:
        return json.dumps(payload, default=_default, ensure_ascii=False)
    except TypeError:
        return json.dumps({"repr": repr(payload)}, ensure_ascii=False)


def _error_payload(exc: HVACBaseError) -> dict[str, Any]:
    return {
        "ok": False,
        "code": exc.code,
        "message": exc.message,
        "details": exc.details,
    }


async def invoke_crm_tool(
    tool_name: str,
    arguments: dict[str, Any],
    user: CurrentUser,
) -> Any:
    """Execute one MCP tool as the given user.

    Возвращает:
        Сериализуемый результат инструмента или dict с полем ``ok: False``.
    """
    registry = get_tool_registry()
    fn = registry.get(tool_name)
    if fn is None:
        return {"ok": False, "code": "UNKNOWN_TOOL", "message": f"Unknown tool: {tool_name}"}

    normalized = normalize_tool_arguments(tool_name, arguments or {})
    confirm = normalized.pop("__confirm", None)
    if tool_name in DESTRUCTIVE_TOOLS and str(confirm or "").strip().lower() not in ("yes", "true", "1"):
        return {
            "ok": False,
            "code": "CONFIRMATION_REQUIRED",
            "message": "Destructive action requires confirmation",
            "details": {
                "tool": tool_name,
                "how_to_confirm": "Ask the user to confirm, then re-run the same tool call with arguments.__confirm = 'yes'.",
            },
        }
    kwargs = prepare_kwargs(fn, normalized)
    token_actor = set_tool_actor(user)
    token_resolved: Token | None = None
    try:
        async with async_session_factory() as db:
            internal_uid = await resolve_users_table_id(db, user)
        token_resolved = set_resolved_users_id(internal_uid)
        return await fn(**kwargs)
    except HVACBaseError as exc:
        return _error_payload(exc)
    except TypeError as exc:
        logger.info("AI tool bad arguments", extra={"tool": tool_name, "error": str(exc)})
        return {"ok": False, "code": "BAD_ARGUMENTS", "message": str(exc)}
    except Exception as exc:  # noqa: BLE001 — surfaced to model as structured error
        logger.exception("AI tool execution failed", extra={"tool": tool_name})
        return {"ok": False, "code": "TOOL_EXECUTION_ERROR", "message": str(exc)}
    finally:
        if token_resolved is not None:
            reset_resolved_users_id(token_resolved)
        reset_tool_actor(token_actor)
