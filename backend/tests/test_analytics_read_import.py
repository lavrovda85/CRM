"""Sanity import for shared analytics query module."""

from __future__ import annotations

from app.services import analytics_read


def test_aggregate_dashboard_is_callable() -> None:
    """Module exposes coroutine functions used by REST and MCP."""
    assert callable(analytics_read.aggregate_dashboard)
    assert callable(analytics_read.aggregate_tender_analytics)
