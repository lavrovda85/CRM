"""RBAC permissions matrix and helper dependencies.

Матрица прав доступа по ролям и ресурсам.
Предоставляет готовые Depends-совместимые функции
для защиты эндпоинтов.
"""

from app.core.security import require_any_role, require_role

ADMIN_ONLY = require_role("admin")

MANAGE_USERS = require_role("admin")

MANAGE_TASKS = require_any_role("admin", "manager")

READ_TASKS = require_any_role("admin", "manager", "engineer", "warehouse_manager", "accountant")

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
