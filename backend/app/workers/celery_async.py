"""Shared asyncio event loop for Celery worker processes.

asyncpg connections created under one event loop cannot be reused after that loop
is closed. Calling ``asyncio.run()`` in each task creates a **new** loop every
time while SQLAlchemy's global async ``engine`` keeps pooled connections tied to
the previous loop, which causes:

- ``RuntimeError: ... attached to a different loop`` on the next task run
- ``RuntimeError: Event loop is closed`` during pool connection teardown

A single worker-process loop (same pattern as ``scheduled_tasks``) keeps the
engine, pool, and asyncpg state consistent across periodic and ad-hoc tasks.

Attributes:
    None
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TypeVar

T = TypeVar("T")

_worker_loop: asyncio.AbstractEventLoop | None = None


def get_celery_worker_event_loop() -> asyncio.AbstractEventLoop:
    """Return one event loop per Celery worker OS process (recreated if closed).

    Returns:
        The worker-local event loop used for all async DB work in this process.
    """
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)
    return _worker_loop


def run_coroutine(coro: Awaitable[T]) -> T:
    """Run an awaitable on the worker-local loop via ``run_until_complete``.

    Args:
        coro: Coroutine to execute (e.g. ``main()``).

    Returns:
        The coroutine's result.
    """
    loop = get_celery_worker_event_loop()
    return loop.run_until_complete(coro)
