"""Unit tests for workflow gate validation (required fields / roles / checklists).

Covers ``WorkflowEngine`` helpers used before ``execute_transition`` — no DB required.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.template import WorkflowTransition
from app.services.workflow_engine import WorkflowEngine


@pytest.mark.asyncio
async def test_required_fields_missing_in_custom_fields() -> None:
    """Transition requiring a custom field fails when value is absent."""
    transition = WorkflowTransition.model_validate(
        {
            "from": "new",
            "to": "in_progress",
            "required_fields": ["site_address"],
        }
    )
    task = SimpleNamespace(custom_fields={}, title="T", description=None)
    errors = await WorkflowEngine._check_required_fields(task, transition)
    assert errors
    assert any("site_address" in e for e in errors)


@pytest.mark.asyncio
async def test_required_fields_satisfied_from_custom_fields() -> None:
    """Filled custom_fields satisfy required_fields."""
    transition = WorkflowTransition.model_validate(
        {
            "from": "new",
            "to": "in_progress",
            "required_fields": ["site_address"],
        }
    )
    task = SimpleNamespace(custom_fields={"site_address": "Moscow"}, title="T", description=None)
    errors = await WorkflowEngine._check_required_fields(task, transition)
    assert errors == []


def test_required_roles_admin_allowed() -> None:
    """User with a matching role passes role gate."""
    transition = WorkflowTransition.model_validate(
        {
            "from": "new",
            "to": "in_progress",
            "required_roles": ["engineer"],
        }
    )
    user = SimpleNamespace(sub="u1", roles=["engineer"])
    errors = WorkflowEngine._check_required_roles(transition, user)
    assert errors == []


def test_required_roles_denied() -> None:
    """User without any required role gets an error string."""
    transition = WorkflowTransition.model_validate(
        {
            "from": "new",
            "to": "in_progress",
            "required_roles": ["warehouse_manager"],
        }
    )
    user = SimpleNamespace(sub="u1", roles=["engineer"])
    errors = WorkflowEngine._check_required_roles(transition, user)
    assert errors
    assert "role" in errors[0].lower()


@pytest.mark.asyncio
async def test_required_checklist_missing_on_task() -> None:
    """When no matching checklist rows exist, validation reports missing gate."""
    transition = WorkflowTransition.model_validate(
        {
            "from": "new",
            "to": "in_progress",
            "required_checklists": ["Safety briefing"],
        }
    )
    task = SimpleNamespace(id=uuid.uuid4())

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    errors = await WorkflowEngine._check_required_checklists(task, transition, session)
    assert errors
    assert any("Safety briefing" in e or "not found" in e for e in errors)


@pytest.mark.asyncio
async def test_required_checklist_incomplete() -> None:
    """Existing checklist with is_completed False blocks transition."""
    transition = WorkflowTransition.model_validate(
        {
            "from": "new",
            "to": "in_progress",
            "required_checklists": ["Safety briefing"],
        }
    )
    task = SimpleNamespace(id=uuid.uuid4())
    cl = SimpleNamespace(title="Safety briefing", gate_transition=None, is_completed=False)

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [cl]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    session = AsyncMock()
    session.execute = AsyncMock(return_value=mock_result)

    errors = await WorkflowEngine._check_required_checklists(task, transition, session)
    assert errors
    assert any("not fully completed" in e for e in errors)
