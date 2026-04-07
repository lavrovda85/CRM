"""Factory for ``AsyncOpenAI`` with optional HTTP proxy (Xray sidecar for OpenAI-only routing)."""

from __future__ import annotations

import httpx
from openai import AsyncOpenAI

from app.core.config import Settings


def create_async_openai_client(settings: Settings) -> AsyncOpenAI:
    """Build ``AsyncOpenAI``; uses ``OPENAI_HTTP_PROXY`` when set (e.g. ``http://xray-openai:10808``).

    Only code paths that talk to OpenAI should use this factory so other HTTP traffic stays direct.

    Args:
        settings: Application settings (API key + optional proxy URL).

    Returns:
        Configured async OpenAI client.
    """
    api_key = (settings.openai_api_key or "").strip()
    proxy = (settings.openai_http_proxy or "").strip()
    if not proxy:
        return AsyncOpenAI(api_key=api_key)
    http_client = httpx.AsyncClient(
        proxy=proxy,
        timeout=httpx.Timeout(120.0, connect=45.0),
        limits=httpx.Limits(max_connections=32, max_keepalive_connections=16),
    )
    return AsyncOpenAI(api_key=api_key, http_client=http_client)
