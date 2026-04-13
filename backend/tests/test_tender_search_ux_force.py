"""Tests for AI assistant tender web-search heuristics.

Loads ``tender_search_ux`` by file path to avoid importing ``app.services.ai_assistant`` package
(which pulls Settings/DB at import time).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "_tender_search_ux_under_test",
    _ROOT / "app/services/ai_assistant/tender_search_ux.py",
)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
should_force_tender_web_search = _mod.should_force_tender_web_search


def test_force_search_public_tender_query_ru() -> None:
    assert should_force_tender_web_search(
        "посмотри актуальные тендеры по вентиляции в красноярском крае",
    )


def test_force_search_topic_without_aktualnye() -> None:
    assert should_force_tender_web_search("тендеры по вентиляции в красноярске")


def test_no_force_crm_list() -> None:
    assert not should_force_tender_web_search("покажи наши тендеры в CRM")


def test_no_force_url_paste() -> None:
    assert not should_force_tender_web_search(
        "добавь тендер https://zakupki.gov.ru/epz/order/notice/zk20/view/common-info.html?regNumber=123",
    )
