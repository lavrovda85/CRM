"""Server clock system message for relative date resolution in the AI assistant."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def build_server_time_system_message(tz_name: str) -> str:
    """Build a system message with current UTC and local time for relative date resolution.

    The model uses this to interpret phrases like «сегодня», «завтра», «на следующей неделе»
    against the real server clock (see ``Settings.ai_assistant_timezone``).
    """
    now_utc = datetime.now(timezone.utc)
    name = (tz_name or "").strip() or "UTC"
    try:
        tz = ZoneInfo(name)
        now_local = now_utc.astimezone(tz)
    except Exception:
        name = "UTC"
        now_local = now_utc.astimezone(timezone.utc)
    weekdays_ru = (
        "понедельник",
        "вторник",
        "среда",
        "четверг",
        "пятница",
        "суббота",
        "воскресенье",
    )
    wd_ru = weekdays_ru[now_local.weekday()]
    return (
        "Server clock (authoritative for interpreting relative dates, e.g. «сегодня», «завтра», "
        "«послезавтра», «на этой неделе», «в пятницу»):\n"
        f"- UTC now: {now_utc.isoformat(timespec='seconds')}\n"
        f"- Local ({name}) now: {now_local.isoformat(timespec='seconds')} — {wd_ru}, "
        f"date {now_local.strftime('%Y-%m-%d')}.\n"
        "Use this local calendar for those phrases unless the user specifies another timezone. "
        "Pass `due_date` as ISO 8601 (prefer UTC `Z` or explicit offset)."
    )
