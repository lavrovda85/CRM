"""Integration test hooks: skip entire module when PostgreSQL is unreachable."""

from __future__ import annotations

import asyncio
import os

import pytest
from sqlalchemy import text

# Honour same skip flag as root smoke test
_skip = os.environ.get("SKIP_DB_INTEGRATION", "").lower() in ("1", "true", "yes")


@pytest.fixture(scope="module", autouse=True)
def _require_postgres() -> None:
    """Skip integration tests if DB URL is wrong or server is down."""
    if _skip:
        pytest.skip("SKIP_DB_INTEGRATION is set")

    from app.core.database import engine

    async def _ping() -> None:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    try:
        asyncio.run(_ping())
    except Exception as exc:
        pytest.skip(f"PostgreSQL not available for integration tests: {exc!r}")
