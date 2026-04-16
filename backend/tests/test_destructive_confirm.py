"""Tests for destructive-action confirmation parsing."""

from __future__ import annotations

import pytest

from app.core.destructive_confirm import is_destructive_action_confirmed


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, False),
        ("", False),
        ("   ", False),
        ("no", False),
        ("нет", False),
        ("yes", True),
        (" YES ", True),
        ("true", True),
        ("1", True),
        (1, True),
        (1.0, True),
        (True, True),
        (False, False),
        ("подтверждаю", True),
        ("«подтверждаю»", True),
        ("Подтверждаю.", True),
        ("да", True),
        ("ДА!", True),
        ("ok", True),
        ("ок", True),
    ],
)
def test_is_destructive_action_confirmed(value: object, expected: bool) -> None:
    assert is_destructive_action_confirmed(value) is expected
