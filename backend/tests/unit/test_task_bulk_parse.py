"""Unit tests for task bulk helpers (due date parsing)."""

from __future__ import annotations

import pytest

from app.mcp.tools import task_tools as tt


def test_parse_due_date_optional_none() -> None:
    assert tt._parse_due_date_optional(None) is None
    assert tt._parse_due_date_optional("  ") is None


def test_parse_due_date_optional_iso() -> None:
    dt = tt._parse_due_date_optional("2026-03-30T15:00:00+00:00")
    assert dt is not None
    assert dt.year == 2026 and dt.month == 3 and dt.day == 30


def test_parse_due_date_optional_russian_datetime() -> None:
    dt = tt._parse_due_date_optional("30.03.2026 15:00:00")
    assert dt is not None
    assert dt.tzinfo == tt._MOSCOW_TZ
    assert dt.hour == 15


def test_parse_due_date_optional_russian_date_only() -> None:
    dt = tt._parse_due_date_optional("30.03.2026")
    assert dt is not None
    assert dt.tzinfo == tt._MOSCOW_TZ


def test_parse_due_date_optional_invalid() -> None:
    from app.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        tt._parse_due_date_optional("not-a-date")


def test_placeholder_assignee_labels() -> None:
    assert tt._is_placeholder_assignee_label("Рабочая группа") is True
    assert tt._is_placeholder_assignee_label("  рабочая   группа  ") is True
    assert tt._is_placeholder_assignee_label("Рабочая группа 2") is True
    assert tt._is_placeholder_assignee_label("—") is True
    assert tt._is_placeholder_assignee_label("") is True
    assert tt._is_placeholder_assignee_label(None) is False


def test_placeholder_assignee_not_real_names() -> None:
    assert tt._is_placeholder_assignee_label("Иванов П.П.") is False
    assert tt._is_placeholder_assignee_label("a1b2c3d4-e5f6-7890-abcd-ef1234567890") is False
