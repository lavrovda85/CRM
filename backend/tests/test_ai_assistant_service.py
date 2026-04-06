"""Unit tests for AI assistant tool registry and helpers."""

from __future__ import annotations

import inspect

import pytest

from app.services.ai_assistant_service import (
    _normalize_tool_arguments,
    _prepare_kwargs,
    _unwrap_tool_callable,
    _user_wants_tender_import_crm,
    extract_context_patch_from_tool,
    get_tool_registry,
)


def test_tool_registry_contains_expected_tools() -> None:
    """MCP tool names must be discoverable for OpenAI dispatch."""
    pytest.importorskip("fastmcp")
    reg = get_tool_registry()
    for name in ("create_task", "list_tasks", "search_tasks", "list_boards"):
        assert name in reg, f"missing {name}"
        assert inspect.iscoroutinefunction(reg[name])


@pytest.mark.asyncio
async def test_invoke_unknown_tool_returns_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown tool names surface as structured errors (no crash)."""
    from app.core.security import CurrentUser
    from app.services import ai_assistant_service as m

    monkeypatch.setattr(m, "get_tool_registry", lambda: {})

    u = CurrentUser(sub="00000000-0000-0000-0000-000000000099", roles=["admin"], raw_token="")
    out = await m.invoke_crm_tool("not_a_real_tool_ever", {}, u)
    assert isinstance(out, dict)
    assert out.get("code") == "UNKNOWN_TOOL"


def test_normalize_create_task_maps_synonyms_to_title() -> None:
    """LLM often sends name/subject; normalize before kwargs filtering."""
    assert _normalize_tool_arguments("create_task", {"name": "  Замер  "}) == {"name": "  Замер  ", "title": "Замер"}
    assert _normalize_tool_arguments("create_task", {"subject": "A"})["title"] == "A"
    out = _normalize_tool_arguments("create_task", {"title": "  T1 "})
    assert out["title"] == "T1"
    assert _normalize_tool_arguments("list_tasks", {"x": 1}) == {"x": 1}


def test_normalize_search_tenders_on_web_maps_synonyms_to_query() -> None:
    """Models often send q/keywords instead of query."""
    assert _normalize_tool_arguments(
        "search_tenders_on_web",
        {"q": "  кондиционирование Красноярск  "},
    ) == {"q": "  кондиционирование Красноярск  ", "query": "кондиционирование Красноярск"}
    assert _normalize_tool_arguments(
        "search_tenders_on_web",
        {"keywords": "VRF"},
    )["query"] == "VRF"


def test_prepare_kwargs_filters_unknown_keys() -> None:
    """Arguments are filtered to the target signature."""

    async def sample(a: int, b: str = "x") -> None:
        return None

    raw = {"a": 1, "b": "y", "extra": 99}
    assert _prepare_kwargs(sample, raw) == {"a": 1, "b": "y"}


def test_user_wants_tender_import_crm() -> None:
    assert _user_wants_tender_import_crm("добавь его в тендеры")
    assert _user_wants_tender_import_crm("добавить этот тендер в CRM")
    assert not _user_wants_tender_import_crm("как добавить тендер вручную")
    assert not _user_wants_tender_import_crm("расскажи про тендеры")


def test_extract_context_patch_import_tender() -> None:
    p = extract_context_patch_from_tool(
        "import_tender_from_url",
        {"id": "11111111-1111-1111-1111-111111111111", "title": "Test"},
    )
    assert p["last_tender_id"] == "11111111-1111-1111-1111-111111111111"
    assert p["last_tender_title"] == "Test"


def test_parse_tender_list_index_from_message() -> None:
    from app.services.ai_assistant.tender_import import parse_tender_list_index_from_message

    assert parse_tender_list_index_from_message("добавь 4 в тендеры") == 4
    assert parse_tender_list_index_from_message("номер 3 в тендеры") == 3
    assert parse_tender_list_index_from_message("добавь в тендеры") is None


def test_resolve_tender_search_url_by_index() -> None:
    from app.services.ai_assistant.tender_import import resolve_tender_search_url_for_import

    ctx = {
        "last_tender_search_first_url": "https://first.example/a",
        "last_tender_search_urls": ["https://first.example/a", "https://second.example/b"],
        "last_tender_search_results": [
            {"index": 1, "url": "https://first.example/a", "title": "A"},
            {"index": 2, "url": "https://second.example/b", "title": "B"},
            {"index": 3, "url": "https://third.example/c", "title": "C"},
            {"index": 4, "url": "https://fourth.example/d", "title": "D"},
        ],
    }
    assert resolve_tender_search_url_for_import(ctx, "добавь 4 в тендеры") == "https://fourth.example/d"
    assert resolve_tender_search_url_for_import(ctx, "добавь в тендеры") == "https://first.example/a"
    assert resolve_tender_search_url_for_import(ctx, "добавь 99 в тендеры") is None


def test_build_session_context_message_coerces_row_types() -> None:
    """Legacy or malformed JSON must not crash when building the system memory block."""
    from app.services.ai_assistant.session_memory import build_session_context_message

    scm = build_session_context_message(
        {
            "last_tender_search_first_url": "https://example.com/a",
            "last_tender_search_results": [
                {"index": 1, "url": "https://z.test/x", "title": 99999},
            ],
        }
    )
    assert scm is not None
    assert "99999" in scm


def test_extract_context_patch_search_tenders_list() -> None:
    """search_tenders_on_web returns a list — must persist URLs for follow-up import."""
    p = extract_context_patch_from_tool(
        "search_tenders_on_web",
        [
            {"title": "Work A", "url": "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=1"},
            {"title": "Work B", "url": "https://example.com/other"},
        ],
    )
    assert p["last_tender_search_first_url"].startswith("https://zakupki.gov.ru")
    assert len(p["last_tender_search_urls"]) == 2
    assert len(p["last_tender_search_results"]) == 2
    assert p["last_tender_search_results"][0]["index"] == 1


def test_extract_context_patch_search_preserves_enrichment() -> None:
    """Enriched search rows must stay in session for import hints (summary, deadline)."""
    p = extract_context_patch_from_tool(
        "search_tenders_on_web",
        [
            {
                "title": "T",
                "url": "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=1",
                "summary": "НМЦК 1 500 000 ₽. Срок до 15 апреля 2026.",
                "submission_deadline_utc": "2026-04-15T12:00:00+00:00",
                "snippet": "ЕИС",
            },
        ],
    )
    r0 = p["last_tender_search_results"][0]
    assert "НМЦК" in r0["summary"]
    assert r0["submission_deadline_utc"].startswith("2026-04-15")


def test_user_wants_more_tender_results() -> None:
    from app.services.ai_assistant.tender_search_ux import user_wants_more_tender_results

    assert user_wants_more_tender_results("следующие") is True
    assert user_wants_more_tender_results("ещё") is True
    assert user_wants_more_tender_results("покажи ещё варианты") is True
    assert user_wants_more_tender_results("найди вентиляцию") is False


def test_collect_exclude_urls_from_session() -> None:
    from app.services.ai_assistant.tender_search_ux import collect_exclude_urls_from_session

    urls = collect_exclude_urls_from_session(
        {"tender_search_seen_urls": ["https://a", "https://b"]}
    )
    assert urls == ["https://a", "https://b"]


def test_resolve_tender_search_row_for_hints() -> None:
    from app.services.ai_assistant.tender_import import resolve_tender_search_row_for_hints

    u = "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=209150000012600162"
    ctx = {
        "last_tender_search_results": [
            {
                "index": 1,
                "url": u,
                "title": "A",
                "summary": "Full text from enrich",
                "submission_deadline_utc": "2026-04-15T00:00:00+00:00",
            },
            {"index": 2, "url": "https://other", "title": "B"},
        ],
    }
    row = resolve_tender_search_row_for_hints(ctx, "добавь 1 в тендеры", u)
    assert row and row["summary"] == "Full text from enrich"
    row2 = resolve_tender_search_row_for_hints(ctx, "добавь в тендеры", u)
    assert row2 and row2["index"] == 1


def test_unwrap_tool_callable_plain_async() -> None:
    """Unwrap returns plain async functions."""

    async def plain() -> int:
        return 1

    out = _unwrap_tool_callable(plain)
    assert out is plain
