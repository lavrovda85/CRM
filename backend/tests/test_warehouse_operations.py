"""Unit checks for warehouse movement type constants."""

from __future__ import annotations

from app.services.warehouse_operations import ALLOWED_MOVEMENT_TYPES, INTAKE_TYPES


def test_intake_types_subset() -> None:
    """Intake and return increase stock."""
    assert INTAKE_TYPES <= ALLOWED_MOVEMENT_TYPES
    assert "consumption" in ALLOWED_MOVEMENT_TYPES
    assert "transfer" in ALLOWED_MOVEMENT_TYPES
