"""Tests for task global visibility: by JWT account identity, not realm role."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.permissions import (
    user_identity_matches_task_full_access,
    user_sees_all_company_tasks,
)
from app.core.security import CurrentUser


def _settings_mock(
    *,
    task_accounts: list[str] | None = None,
    dev_emails: list[str] | None = None,
    dev_ids: list[str] | None = None,
    debug: bool = False,
) -> MagicMock:
    m = MagicMock()
    m.task_full_access_accounts = list(task_accounts or [])
    m.dev_admin_emails = list(dev_emails or [])
    m.dev_admin_user_ids = list(dev_ids or [])
    m.debug = debug
    return m


def test_identity_match_email_case_insensitive() -> None:
    u = CurrentUser(sub="any", email="Boss@EXAMPLE.com", roles=["engineer"])
    allow = frozenset({"boss@example.com"})
    assert user_identity_matches_task_full_access(u, allow) is True


def test_identity_match_preferred_username() -> None:
    u = CurrentUser(
        sub="uuid-here",
        email="",
        preferred_username="ivanov",
        roles=["engineer"],
    )
    allow = frozenset({"ivanov"})
    assert user_identity_matches_task_full_access(u, allow) is True


def test_identity_match_sub() -> None:
    u = CurrentUser(sub="11111111-1111-1111-1111-111111111111", email="", roles=["engineer"])
    allow = frozenset({"11111111-1111-1111-1111-111111111111"})
    assert user_identity_matches_task_full_access(u, allow) is True


def test_admin_realm_role_does_not_imply_full_access_without_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.core.permissions.get_settings",
        lambda: _settings_mock(),
    )
    u = CurrentUser(sub="s", email="nobody@x.test", roles=["admin"])
    assert user_sees_all_company_tasks(u) is False


def test_full_access_when_task_accounts_lists_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.core.permissions.get_settings",
        lambda: _settings_mock(task_accounts=["auditor@corp.test"]),
    )
    u = CurrentUser(sub="kc-sub", email="auditor@corp.test", roles=["engineer"])
    assert user_sees_all_company_tasks(u) is True


def test_full_access_via_dev_admin_email(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.core.permissions.get_settings",
        lambda: _settings_mock(dev_emails=["lead@corp.test"]),
    )
    u = CurrentUser(sub="x", email="lead@corp.test", roles=["manager"])
    assert user_sees_all_company_tasks(u) is True
