"""RBAC permissions matrix and helper dependencies.

Матрица прав доступа по ролям и ресурсам.
Предоставляет готовые Depends-совместимые функции
для защиты эндпоинтов.
"""

from __future__ import annotations

from app.core.config import Settings, get_settings
from app.core.security import DEV_USER_ID, CurrentUser, require_any_role, require_role


def _task_full_access_allowlist(settings: Settings) -> frozenset[str]:
    """Normalized identities (email, username, sub) allowed to bypass participant task filter."""
    parts: list[str] = []
    parts.extend(str(x) for x in settings.task_full_access_accounts)
    parts.extend(str(x) for x in settings.dev_admin_emails)
    parts.extend(str(x) for x in settings.dev_admin_user_ids)
    out: set[str] = set()
    for raw in parts:
        s = raw.strip().lower()
        if s:
            out.add(s)
    if settings.debug:
        out.update(
            {
                "dev@hvac-crm.local",
                str(DEV_USER_ID).lower(),
            }
        )
    return frozenset(out)


def user_identity_matches_task_full_access(user: CurrentUser, allow: frozenset[str]) -> bool:
    """Return True if any JWT identity field matches an entry in ``allow`` (lowercase)."""
    if not allow:
        return False
    candidates = [
        (user.email or "").strip().lower(),
        (user.preferred_username or "").strip().lower(),
        (user.sub or "").strip().lower(),
    ]
    return any(c and c in allow for c in candidates)


def user_sees_all_company_tasks(user: CurrentUser) -> bool:
    """Return True if the user may list/read any task in the company (by account, not role).

    Uses ``TASK_FULL_ACCESS_ACCOUNTS``, ``DEV_ADMIN_EMAILS``, ``DEV_ADMIN_USER_IDS``,
    and in ``debug`` the built-in dev email/sub — matched against JWT ``email``,
    ``preferred_username``, or ``sub``.

    Args:
        user: Authenticated user from the access token.

    Returns:
        Whether per-task participant filtering is skipped for this user.
    """
    settings = get_settings()
    allow = _task_full_access_allowlist(settings)
    return user_identity_matches_task_full_access(user, allow)


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
