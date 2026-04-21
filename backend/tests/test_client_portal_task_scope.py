"""Unit tests for client-only task visibility scope (Keycloak ``client`` role)."""

from app.core.permissions import is_client_portal_only_task_scope
from app.core.security import CurrentUser


def test_client_only_user_gets_strict_scope() -> None:
    u = CurrentUser(sub="x", roles=["client"])
    assert is_client_portal_only_task_scope(u) is True


def test_staff_roles_disable_strict_scope() -> None:
    u = CurrentUser(sub="x", roles=["client", "engineer"])
    assert is_client_portal_only_task_scope(u) is False


def test_admin_without_client_not_strict() -> None:
    u = CurrentUser(sub="x", roles=["admin"])
    assert is_client_portal_only_task_scope(u) is False


def test_empty_roles_not_strict() -> None:
    u = CurrentUser(sub="x", roles=[])
    assert is_client_portal_only_task_scope(u) is False
