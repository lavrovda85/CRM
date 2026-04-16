"""Shared rules for confirming destructive MCP / assistant actions."""

from __future__ import annotations

from typing import Any


def is_destructive_action_confirmed(value: Any) -> bool:
    """Return True if ``value`` is an explicit confirmation for a destructive operation.

    Accepts common English tokens and Russian phrases users are prompted with in the UI.

    Args:
        value: Raw ``__confirm`` argument (string, bool, or small int).

    Returns:
        True when the value clearly affirms the action; False otherwise.
    """
    if value is True:
        return True
    if value is False or value is None:
        return False
    if isinstance(value, int) and not isinstance(value, bool):
        return value == 1
    if isinstance(value, float) and value.is_integer():
        return int(value) == 1

    s = str(value).strip().lower()
    s = s.strip("«»\"'")
    s = s.rstrip(".!?")
    if not s:
        return False

    return s in _ACCEPTED_CONFIRM_TOKENS


_ACCEPTED_CONFIRM_TOKENS = frozenset(
    {
        "yes",
        "y",
        "true",
        "1",
        "on",
        "ok",
        "okay",
        "confirm",
        "confirmed",
        "да",
        "подтверждаю",
        "ок",
        "согласен",
        "согласна",
    }
)
