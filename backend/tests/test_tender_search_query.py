"""Tender search query normalization and exclusion heuristics."""

from app.services.tender.tender_search_query import (
    normalize_eis_search_query,
    should_drop_for_exclusion_tokens,
    should_drop_for_sro_exclusion,
)


def test_normalize_strips_bez_sro() -> None:
    q, ex = normalize_eis_search_query("строительство без СРО Красноярский край")
    assert "сро" not in q.lower()
    assert "сро" in ex
    assert "строительство" in q.lower()
    assert "красноярск" in q.lower()


def test_normalize_typo_po_po() -> None:
    q, _ = normalize_eis_search_query("по по строительству")
    assert "по по" not in q.lower()


def test_sro_mandatory_dropped() -> None:
    text = "Участник должен иметь членство в СРО. Требуется наличие допуска СРО."
    assert should_drop_for_sro_exclusion(text) is True


def test_sro_not_required_kept() -> None:
    text = "Членство в СРО не требуется. Работы под ключ."
    assert should_drop_for_sro_exclusion(text) is False


def test_exclusion_token_sro_in_prev() -> None:
    prev = {
        "notice_subject": "Ремонт здания",
        "text_excerpt": "Требуется членство в СРО",
    }
    assert should_drop_for_exclusion_tokens(prev, ["сро"]) is True
