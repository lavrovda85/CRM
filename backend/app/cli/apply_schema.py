"""Apply database schema (create_all + patches). Used by deploy scripts after git checkout."""

from __future__ import annotations

import asyncio


def main() -> None:
    """Run ``ensure_application_schema`` synchronously for Docker one-shot containers."""
    from app.core.schema_bootstrap import ensure_application_schema

    asyncio.run(ensure_application_schema())


if __name__ == "__main__":
    main()
