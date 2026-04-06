"""OpenAI chat with MCP-equivalent tool execution for SPEC CRM.

Dispatches ``invoke_crm_tool`` function calls to the same async functions
registered under ``@mcp.tool()``, binding the authenticated HTTP user via
``app.mcp.actor_context``.

Implementation is split under ``app.services.ai_assistant``; this module
re-exports the public API and test hooks with legacy names.
"""

from __future__ import annotations

from app.prompts.ai_assistant_system import SYSTEM_PROMPT
from app.services.ai_assistant.chat import AiChatTurnResult, run_ai_chat
from app.services.ai_assistant.session_memory import build_session_context_message, extract_context_patch_from_tool
from app.services.ai_assistant.tender_import import user_wants_tender_import_crm
from app.services.ai_assistant.time_context import build_server_time_system_message
from app.services.ai_assistant.tool_arguments import normalize_tool_arguments, prepare_kwargs
from app.services.ai_assistant.tool_invocation import invoke_crm_tool
from app.services.ai_assistant.tool_registry import get_tool_registry, unwrap_tool_callable

_normalize_tool_arguments = normalize_tool_arguments
_prepare_kwargs = prepare_kwargs
_unwrap_tool_callable = unwrap_tool_callable
_user_wants_tender_import_crm = user_wants_tender_import_crm

__all__ = (
    "SYSTEM_PROMPT",
    "AiChatTurnResult",
    "build_server_time_system_message",
    "build_session_context_message",
    "extract_context_patch_from_tool",
    "get_tool_registry",
    "invoke_crm_tool",
    "run_ai_chat",
    "_normalize_tool_arguments",
    "_prepare_kwargs",
    "_unwrap_tool_callable",
    "_user_wants_tender_import_crm",
)
