"""Tender lifecycle pipeline: allowed status transitions.

Defines the directed graph of valid moves between tender statuses
(search → … → completed, with a lost branch). Used by API and MCP.
"""

from __future__ import annotations

# Ordered stages for UI (main happy path). "lost" is a branch, not in this line.
TENDER_PIPELINE_MAIN: tuple[str, ...] = (
    "search",
    "participation",
    "won",
    "execution",
    "completed",
)

# Adjacency: from_status -> set of allowed to_status values.
ALLOWED_TENDER_TRANSITIONS: dict[str, frozenset[str]] = {
    "search": frozenset({"participation"}),
    "participation": frozenset({"won", "lost", "search"}),
    "won": frozenset({"execution", "participation"}),
    "lost": frozenset({"search"}),
    "execution": frozenset({"completed", "won"}),
    "completed": frozenset(),
}

ALL_KNOWN_STATUSES: frozenset[str] = frozenset(ALLOWED_TENDER_TRANSITIONS.keys())


def allowed_next_statuses(current_status: str) -> list[str]:
    """Return sorted list of statuses reachable in one step from current."""
    allowed = ALLOWED_TENDER_TRANSITIONS.get(current_status)
    if allowed is None:
        return []
    return sorted(allowed)


def is_transition_allowed(from_status: str, to_status: str) -> bool:
    """Whether a single-step transition is permitted."""
    if from_status == to_status:
        return False
    allowed = ALLOWED_TENDER_TRANSITIONS.get(from_status)
    if allowed is None:
        return False
    return to_status in allowed


def transition_denial_reason(from_status: str, to_status: str) -> str | None:
    """Human-readable reason if transition is denied; None if allowed."""
    if from_status == to_status:
        return "Status unchanged"
    if from_status not in ALLOWED_TENDER_TRANSITIONS:
        return f"Unknown current status '{from_status}'"
    if to_status not in ALLOWED_TENDER_TRANSITIONS[from_status]:
        allowed = sorted(ALLOWED_TENDER_TRANSITIONS[from_status])
        if not allowed:
            return f"Terminal status '{from_status}' — no further moves"
        return f"Allowed next: {', '.join(allowed)}"
    return None
