"""RBAC permissions matrix and helper dependencies.

Матрица прав доступа по ролям и ресурсам.
Предоставляет готовые Depends-совместимые функции
для защиты эндпоинтов.
"""

from __future__ import annotations

from app.core.security import CurrentUser, require_any_role, require_role

# Staff roles: full task visibility still follows ``Task.visibility`` (company vs participants).
_STAFF_ROLES_TASK_VISIBILITY: frozenset[str] = frozenset({
    "admin",
    "manager",
    "engineer",
    "warehouse_manager",
    "accountant",
})


def is_client_portal_only_task_scope(user: CurrentUser) -> bool:
    """Return True when the user is an external client for task listing/detail scope.

    If the JWT includes ``client`` and none of the staff roles above, the user only
    sees tasks they created, are assigned to, co-execute, or observe (company-wide
    visibility does not expand their list).

    Args:
        user: Authenticated user from the access token.

    Returns:
        Whether to apply the restricted client task scope.
    """
    roles = frozenset(user.roles or [])
    if "client" not in roles:
        return False
    if roles & _STAFF_ROLES_TASK_VISIBILITY:
        return False
    return True

ADMIN_ONLY = require_role("admin")

MANAGE_USERS = require_role("admin")

MANAGE_TASKS = require_any_role("admin", "manager")

READ_TASKS = require_any_role(
    "admin", "manager", "engineer", "warehouse_manager", "accountant", "client"
)

MANAGE_CLIENTS = require_any_role("admin", "manager")

READ_CLIENTS = require_any_role("admin", "manager", "engineer", "accountant")

MANAGE_TEMPLATES = require_any_role("admin", "manager")

READ_TEMPLATES = require_any_role("admin", "manager", "engineer")

MANAGE_WAREHOUSE = require_any_role("admin", "warehouse_manager")

READ_WAREHOUSE = require_any_role("admin", "manager", "engineer", "warehouse_manager", "accountant")

MANAGE_EQUIPMENT = require_any_role("admin", "warehouse_manager")

VIEW_ANALYTICS = require_any_role("admin", "manager", "accountant")

MANAGE_DEALS = require_any_role("admin", "manager")

MANAGE_TENDERS = require_any_role("admin", "manager")
