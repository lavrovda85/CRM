"""Unit tests for tender pipeline transition rules."""

from __future__ import annotations

import pytest

from app.services.tender import tender_pipeline


@pytest.mark.parametrize(
    ("from_s", "to_s", "allowed"),
    [
        ("search", "participation", True),
        ("search", "won", False),
        ("participation", "won", True),
        ("participation", "lost", True),
        ("won", "execution", True),
        ("execution", "completed", True),
        ("completed", "search", False),
    ],
)
def test_is_transition_allowed(from_s: str, to_s: str, allowed: bool) -> None:
    """Known edges of the tender status graph."""
    assert tender_pipeline.is_transition_allowed(from_s, to_s) is allowed


def test_same_status_not_allowed() -> None:
    """No-op transitions are rejected."""
    assert tender_pipeline.is_transition_allowed("search", "search") is False
    assert tender_pipeline.transition_denial_reason("search", "search") == "Status unchanged"


def test_unknown_from_status() -> None:
    """Unknown current status yields denial reason."""
    reason = tender_pipeline.transition_denial_reason("bogus", "search")
    assert reason is not None
    assert "Unknown current status" in reason
