"""Unit tests for template service helpers (no database)."""

from __future__ import annotations

from types import SimpleNamespace

from app.services.template_service import TemplateService


def test_get_initial_status_prefers_initial_state_key() -> None:
    """Workflow may set ``initial_state`` distinct from ``states[0]``."""
    tpl = SimpleNamespace(
        workflow_definition={
            "states": ["draft", "new", "done"],
            "initial_state": "new",
        }
    )
    assert TemplateService._get_initial_status(tpl) == "new"


def test_json_schema_required_keys_mixed_list() -> None:
    """``required_fields`` JSON may be strings or dicts with ``key``."""
    tpl = SimpleNamespace(
        required_fields=[
            "site_address",
            {"key": "phone", "required": True},
            {"key": "optional_x", "required": False},
        ]
    )
    keys = TemplateService._json_schema_required_keys(tpl)
    assert keys == ["site_address", "phone"]
