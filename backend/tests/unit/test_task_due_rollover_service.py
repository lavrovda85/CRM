"""Unit tests for task due-date rollover (calendar day in a fixed IANA zone)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.task_due_rollover_logic import compute_next_day_same_local_time


def test_compute_next_day_same_local_time_moscow() -> None:
    """Overdue MSK due becomes tomorrow at same local time."""
    # 2026-04-14 12:00 UTC == 15:00 MSK -> calendar "today" is 2026-04-14 in Moscow.
    ref = datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc)
    # 2026-04-13 15:30 UTC == 18:30 MSK on 2026-04-13 -> strictly before today MSK.
    due = datetime(2026, 4, 13, 15, 30, tzinfo=timezone.utc)
    new_due = compute_next_day_same_local_time(
        due,
        tz_name="Europe/Moscow",
        reference_now_utc=ref,
    )
    # Next local day is 2026-04-15 at 18:30 MSK == 2026-04-15 15:30 UTC (MSK = UTC+3).
    assert new_due == datetime(2026, 4, 15, 15, 30, tzinfo=timezone.utc)


def test_compute_next_day_raises_if_not_overdue() -> None:
    """Same calendar day as today in zone must not roll."""
    ref = datetime(2026, 4, 14, 10, 0, tzinfo=timezone.utc)
    due = datetime(2026, 4, 14, 20, 0, tzinfo=timezone.utc)  # still 2026-04-14 in Moscow
    with pytest.raises(ValueError, match="not before today"):
        compute_next_day_same_local_time(
            due,
            tz_name="Europe/Moscow",
            reference_now_utc=ref,
        )


def test_compute_next_day_rejects_naive() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        compute_next_day_same_local_time(
            datetime(2026, 1, 1, 12, 0),
            tz_name="Europe/Moscow",
            reference_now_utc=datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc),
        )
