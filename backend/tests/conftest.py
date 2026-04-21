"""Pytest configuration: minimal env so ``app`` modules can be imported."""

from __future__ import annotations

import os

# ``Settings`` requires ``database_url``; unit tests do not connect unless marked.
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/hvac_crm",
    ),
)
# Avoid empty-string JSON parse failures when .env has blank complex fields.
for _k in ("DEV_ADMIN_EMAILS", "DEV_ADMIN_USER_IDS", "TASK_FULL_ACCESS_ACCOUNTS"):
    if not (os.environ.get(_k) or "").strip():
        os.environ[_k] = "[]"
