"""Unit tests for workflow JSON schema (Pydantic) used by WorkflowEngine."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.template import WorkflowDefinition


def test_minimal_linear_workflow_parses() -> None:
    """Valid workflow_definition as stored on TaskTemplate."""
    raw = {
        "states": ["new", "in_progress", "completed"],
        "initial_state": "new",
        "transitions": [
            {"from": "new", "to": "in_progress"},
            {"from": "in_progress", "to": "completed"},
        ],
    }
    wf = WorkflowDefinition.model_validate(raw)
    assert wf.states == ["new", "in_progress", "completed"]
    assert wf.transitions[0].from_state == "new"
    assert wf.transitions[0].to == "in_progress"


def test_invalid_transition_rejected() -> None:
    """Missing required keys must fail validation."""
    with pytest.raises(ValidationError):
        WorkflowDefinition.model_validate({"states": [], "transitions": [{"to": "x"}]})
