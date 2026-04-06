"""Tests for tabular bill-of-works heuristic."""

from __future__ import annotations

from app.services.tender.tender_analysis_bill_heuristic import (
    extract_bill_of_works_heuristic,
    merge_bill_rows_llm_and_heuristic,
)


def test_heuristic_extracts_tab_separated_rows() -> None:
    text = """## Лист1
№\tНаименование\tЕд. изм.\tКоличество
1\tУкладка кирпича\tм3\t12.5
2\tШтукатурка по сетке\tм2\t40
"""
    rows, note = extract_bill_of_works_heuristic(text)
    assert len(rows) >= 2
    assert any("кирпич" in (r.get("name") or "").lower() for r in rows)
    assert "heuristic" in note


def test_merge_prefers_heuristic_when_llm_empty() -> None:
    h = [{"position": "1", "name": "A", "unit": "м2", "quantity": "1", "remarks": ""}]
    merged = merge_bill_rows_llm_and_heuristic([], h)
    assert merged == h


def test_metadata_row_filtered() -> None:
    text = (
        "х\tСоставлен(а) в текущем уровне цен\t01.10.2025\t01.10.2025\n"
        "1\tУкладка кирпича\tм3\t12.5\t100\t1250\n"
    )
    rows, _ = extract_bill_of_works_heuristic(text)
    assert len(rows) == 1
    assert "кирпич" in (rows[0].get("name") or "").lower()


def test_wide_row_drops_numeric_remarks() -> None:
    text = "1\tКод\tРазборка покрытий пола\tм2\t88.5\t1200.50\t106244.25\n"
    rows, _ = extract_bill_of_works_heuristic(text)
    assert rows
    assert not (rows[0].get("remarks") or "").strip()


def test_merge_keeps_llm_when_substantial() -> None:
    llm = [
        {"name": "A", "unit": "м", "quantity": "1"},
        {"name": "B", "unit": "м", "quantity": "2"},
    ]
    h = [{"position": "", "name": "X", "unit": "шт", "quantity": "3", "remarks": ""}]
    merged = merge_bill_rows_llm_and_heuristic(llm, h)
    assert len(merged) == 2
