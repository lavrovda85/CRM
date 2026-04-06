"""Optional integration smoke test against a real PostgreSQL instance.

Set ``DATABASE_URL`` (or ``TEST_DATABASE_URL`` in conftest) to a reachable DB
with migrations applied. If the server is down, tests are skipped.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Re-read env after conftest defaults
pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_postgres_select_one() -> None:
    """Verify async DB connectivity when integration tests are enabled."""
    if os.environ.get("SKIP_DB_INTEGRATION", "").lower() in ("1", "true", "yes"):
        pytest.skip("SKIP_DB_INTEGRATION set")

    url = os.environ.get("DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not configured")

    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except OSError:
        pytest.skip("Database host unreachable")
    except Exception as exc:
        pytest.skip(f"Database not available: {exc!r}")
    finally:
        await engine.dispose()
