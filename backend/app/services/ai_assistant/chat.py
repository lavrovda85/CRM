"""OpenAI chat loop with tool execution for the AI assistant."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings
from app.services.openai_client import create_async_openai_client
from app.core.exceptions import AiAssistantUnavailableError
from app.core.security import CurrentUser
from app.prompts.ai_assistant_system import SYSTEM_PROMPT
from app.services.ai_assistant.openai_schema import openai_tools_schema
from app.services.ai_assistant.replies import format_tool_failure_reply
from app.services.ai_assistant.session_memory import build_session_context_message, extract_context_patch_from_tool
from app.services.ai_assistant.tender_import import (
    reply_after_auto_tender_import,
    reply_when_tender_import_not_executed,
    resolve_tender_search_row_for_hints,
    resolve_tender_search_url_for_import,
    user_wants_tender_import_crm,
)
from app.services.ai_assistant.tender_search_ux import (
    collect_exclude_urls_from_session,
    should_force_tender_web_search,
    user_wants_more_tender_results,
)
from app.services.ai_assistant.time_context import build_server_time_system_message
from app.services.ai_assistant.tool_invocation import invoke_crm_tool, serialize_tool_result
from app.services.ai_assistant.tool_registry import get_tool_registry


@dataclass(frozen=True)
class AiChatTurnResult:
    """Completed assistant turn: user-visible reply plus session context updates.

    Атрибуты:
        reply: Финальный текст ассистента.
        context_patch: Слияние в пер-сессионный контекст (last_task_id, last_task_title, …).
    """

    reply: str
    context_patch: dict[str, Any]


async def run_ai_chat(
    *,
    user: CurrentUser,
    user_message: str,
    prior_messages: list[dict[str, str]] | None,
    session_context: dict[str, Any] | None = None,
    settings: Settings | None = None,
    multimodal_user_content: list[dict[str, Any]] | None = None,
) -> AiChatTurnResult:
    """Run one user turn: OpenAI chat with tool loop; return reply and context patch.

    Аргументы:
        user: Текущий пользователь JWT.
        user_message: Новое сообщение пользователя (краткая строка для логов при вложениях).
        prior_messages: История ``{role, content}`` (user/assistant) с сервера.
        session_context: Сохранённые факты (last_task_id и т.д.) для system-дополнения.
        multimodal_user_content: Опционально — части сообщения (текст + image_url) для вложений.

    Возвращает:
        ``AiChatTurnResult`` с текстом и патчем контекста из успешных tool-calls.
    """
    cfg = settings or get_settings()
    if not (cfg.openai_api_key or "").strip():
        raise AiAssistantUnavailableError("OPENAI_API_KEY is not set")

    text = (user_message or "").strip()
    if multimodal_user_content is None:
        if not text:
            raise ValueError("message must not be empty")
        if len(text) > 12000:
            raise ValueError("message too long")
        last_user_payload: str | list[dict[str, Any]] = text
    else:
        if not multimodal_user_content:
            raise ValueError("multimodal content must not be empty")
        last_user_payload = multimodal_user_content
        total_txt = 0
        for part in multimodal_user_content:
            if isinstance(part, dict) and part.get("type") == "text":
                total_txt += len(str(part.get("text") or ""))
        if total_txt > 120_000:
            raise ValueError("attached content too large")

    registry = get_tool_registry()
    client = create_async_openai_client(cfg)
    tools = openai_tools_schema(registry)

    context_patch: dict[str, Any] = {}
    tool_failure_payload: dict[str, Any] | None = None

    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.append(
        {"role": "system", "content": build_server_time_system_message(cfg.ai_assistant_timezone)},
    )
    scm = build_session_context_message(session_context)
    if scm:
        messages.append({"role": "system", "content": scm})
    if prior_messages:
        for m in prior_messages[-40:]:
            role = m.get("role", "")
            content = (m.get("content") or "").strip()
            if role not in ("user", "assistant") or not content:
                continue
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": last_user_payload})

    max_rounds = cfg.ai_assistant_max_tool_rounds
    tender_import_confirmed = False
    # If the model calls another tool first, then answers without tools, we still inject
    # ``search_tenders_on_web`` once per user turn (when ``should_force_tender_web_search``).
    tender_web_search_invoked_this_turn = False
    for round_idx in range(max_rounds):
        tool_failure_payload = None
        response = await client.chat.completions.create(
            model=cfg.openai_model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.25,
        )
        choice = response.choices[0].message
        tool_calls = choice.tool_calls
        if not tool_calls:
            if (
                not tender_web_search_invoked_this_turn
                and should_force_tender_web_search(text)
                and not tender_import_confirmed
            ):
                forced_args: dict[str, Any] = {
                    "query": text[:1200],
                    "prefer_zakupki_gov": True,
                }
                out_forced = await invoke_crm_tool(
                    "search_tenders_on_web",
                    forced_args,
                    user,
                )
                if isinstance(out_forced, dict) and out_forced.get("ok") is False:
                    reply = format_tool_failure_reply(text, out_forced)
                    return AiChatTurnResult(reply=reply, context_patch=context_patch)
                for k, v in extract_context_patch_from_tool(
                    "search_tenders_on_web",
                    out_forced,
                ).items():
                    if v is not None:
                        context_patch[k] = v
                forced_tool_args = json.dumps(
                    {
                        "tool_name": "search_tenders_on_web",
                        "arguments": forced_args,
                    },
                    ensure_ascii=False,
                )
                fake_tc_id = "call_forced_tender_search"
                messages.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": fake_tc_id,
                                "type": "function",
                                "function": {
                                    "name": "invoke_crm_tool",
                                    "arguments": forced_tool_args,
                                },
                            }
                        ],
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": fake_tc_id,
                        "content": serialize_tool_result(out_forced),
                    },
                )
                context_patch["tender_search_reset_seen"] = True
                tender_web_search_invoked_this_turn = True
                continue

            reply = (choice.content or "").strip() or "(empty reply)"
            if user_wants_tender_import_crm(text) and not tender_import_confirmed:
                fb_url = resolve_tender_search_url_for_import(session_context, text)
                if fb_url:
                    import_args: dict[str, Any] = {"url": fb_url}
                    hint_row = resolve_tender_search_row_for_hints(session_context, text, fb_url)
                    if hint_row:
                        summ = str(hint_row.get("summary") or hint_row.get("snippet") or "").strip()
                        if summ:
                            import_args["enriched_summary"] = summ[:8000]
                        sdu = hint_row.get("submission_deadline_utc")
                        if sdu is not None and str(sdu).strip():
                            import_args["enriched_submission_deadline_utc"] = str(sdu).strip()
                    auto_out = await invoke_crm_tool(
                        "import_tender_from_url",
                        import_args,
                        user,
                    )
                    if isinstance(auto_out, dict) and auto_out.get("ok") is False:
                        reply = format_tool_failure_reply(text, auto_out)
                    elif isinstance(auto_out, dict) and auto_out.get("id"):
                        tender_import_confirmed = True
                        for k, v in extract_context_patch_from_tool("import_tender_from_url", auto_out).items():
                            if v is not None:
                                context_patch[k] = v
                        reply = reply_after_auto_tender_import(text, auto_out)
                    else:
                        reply = reply_when_tender_import_not_executed()
                else:
                    reply = reply_when_tender_import_not_executed()
            return AiChatTurnResult(reply=reply, context_patch=context_patch)

        asst_msg: dict[str, Any] = {"role": "assistant", "content": choice.content}
        if tool_calls:
            asst_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments or "{}",
                    },
                }
                for tc in tool_calls
            ]
        messages.append(asst_msg)

        for tc in tool_calls:
            if tc.function.name != "invoke_crm_tool":
                result = {"ok": False, "message": f"Unexpected function {tc.function.name}"}
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": serialize_tool_result(result),
                    }
                )
                continue
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                payload = {"ok": False, "code": "INVALID_JSON", "message": "Bad function arguments"}
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": serialize_tool_result(payload)}
                )
                continue

            tname = args.get("tool_name")
            targs = args.get("arguments") if isinstance(args.get("arguments"), dict) else {}
            if not isinstance(tname, str):
                out: Any = {"ok": False, "message": "tool_name must be a string"}
            else:
                if tname == "search_tenders_on_web" and session_context:
                    targs = dict(targs or {})
                    if user_wants_more_tender_results(text):
                        ex = collect_exclude_urls_from_session(session_context)
                        if ex:
                            cur = targs.get("exclude_urls")
                            if isinstance(cur, list) and cur:
                                merged_ex = list(
                                    dict.fromkeys(
                                        [str(u).strip() for u in cur if u]
                                        + [str(u).strip() for u in ex if u]
                                    )
                                )[:400]
                                targs["exclude_urls"] = merged_ex
                            elif not targs.get("exclude_urls"):
                                targs["exclude_urls"] = ex
                if tname in ("import_tender_from_url", "fetch_tender_from_url") and session_context:
                    tu = str((targs or {}).get("url") or "").strip()
                    if not tu:
                        fb = resolve_tender_search_url_for_import(session_context, text)
                        if fb:
                            targs = dict(targs or {})
                            targs["url"] = fb
                            tu = fb
                    if tname == "import_tender_from_url" and tu:
                        hint_row = resolve_tender_search_row_for_hints(session_context, text, tu)
                        if hint_row:
                            targs = dict(targs or {})
                            if not str(targs.get("enriched_summary") or "").strip():
                                summ = str(
                                    hint_row.get("summary") or hint_row.get("snippet") or ""
                                ).strip()
                                if summ:
                                    targs["enriched_summary"] = summ[:8000]
                            if not str(targs.get("enriched_submission_deadline_utc") or "").strip():
                                sdu = hint_row.get("submission_deadline_utc")
                                if sdu is not None and str(sdu).strip():
                                    targs["enriched_submission_deadline_utc"] = str(sdu).strip()
                out = await invoke_crm_tool(tname, targs, user)
                if tname == "search_tenders_on_web":
                    tender_web_search_invoked_this_turn = True
                if (
                    tname == "import_tender_from_url"
                    and isinstance(out, dict)
                    and out.get("id")
                    and out.get("ok") is not False
                ):
                    tender_import_confirmed = True
                for k, v in extract_context_patch_from_tool(tname, out).items():
                    if v is not None:
                        context_patch[k] = v
                if tname == "search_tenders_on_web" and isinstance(out, list):
                    if not user_wants_more_tender_results(text):
                        context_patch["tender_search_reset_seen"] = True

            if tool_failure_payload is None and isinstance(out, dict) and out.get("ok") is False:
                tool_failure_payload = out
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": serialize_tool_result(out),
                }
            )

        if tool_failure_payload is not None:
            reply = format_tool_failure_reply(text or user_message, tool_failure_payload)
            return AiChatTurnResult(reply=reply, context_patch=context_patch)

    return AiChatTurnResult(
        reply="Tool loop limit reached; please narrow your request.",
        context_patch=context_patch,
    )
