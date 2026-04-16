"""Pure date logic for rolling task due dates (no database imports)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def compute_next_day_same_local_time(
    due_utc: datetime,
    *,
    tz_name: str,
    reference_now_utc: datetime,
) -> datetime:
    """Return ``due_date`` moved to tomorrow in ``tz_name`` at the same local clock time.

    Args:
        due_utc: Current due instant (timezone-aware, typically UTC).
        tz_name: IANA timezone used for calendar-day boundaries (e.g. ``Europe/Moscow``).
        reference_now_utc: "Now" for deciding what "today" is (injection for tests).

    Returns:
        New due instant in UTC.

    Raises:
        ValueError: If ``due_utc`` is naive, ``tz_name`` is invalid, or due is not before today in ``tz_name``.
    """
    if due_utc.tzinfo is None:
        raise ValueError("due_utc must be timezone-aware")
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone: {tz_name!r}") from exc

    today_local = reference_now_utc.astimezone(tz).date()
    due_local = due_utc.astimezone(tz)
    if due_local.date() >= today_local:
        raise ValueError("due date is not before today in the rollover timezone")

    tomorrow = today_local + timedelta(days=1)
    new_local = datetime(
        tomorrow.year,
        tomorrow.month,
        tomorrow.day,
        due_local.hour,
        due_local.minute,
        due_local.second,
        due_local.microsecond,
        tzinfo=tz,
    )
    return new_local.astimezone(timezone.utc)
