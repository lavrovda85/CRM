"""Optional integration with Russian state construction pricing systems (ФГИС ЦС).

The official portal `https://fgiscs.minstroyrf.ru/` (ФГИС ЦС, Минстрой) publishes
construction resource pricing and related data for regulated procurement. There is
**no stable, fully documented public REST API** published for arbitrary third-party
smeta engines to query live unit rates the way desktop tools (e.g. GrandSmeta) do;
access is typically via the web UI, authorised participants, or separate integration
programmes.

This module therefore:

- Optionally **GET** a JSON document from ``FGIS_CS_CONTEXT_JSON_URL`` (your mirror of
  indices / notes) and pass it into the smeta calculator prompt.
- Optionally **GET** ``FGIS_CS_API_BASE_URL`` + ``FGIS_CS_API_PATH`` with bearer token
  ``FGIS_CS_API_TOKEN`` when your organisation exposes an internal gateway.

If nothing is configured, the calculator runs with an explicit disclaimer that
numeric results are **indicative** and must be validated against official
methodology and current collections (ФССЦ / РИМ / regional catalogues).

See also: `https://fgiscs.minstroyrf.ru/` — ФГИС ЦС.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def fetch_fgis_external_context() -> tuple[str, dict[str, Any]]:
    """Return (text_for_llm, diagnostics) from optional configured sources.

    ``diagnostics`` may include keys: ``context_json_url_ok``, ``api_ok``, ``errors``.
    """
    settings = get_settings()
    diag: dict[str, Any] = {"errors": []}
    chunks: list[str] = []

    url = (settings.fgis_cs_context_json_url or "").strip()
    if url:
        try:
            async with httpx.AsyncClient(timeout=settings.fgis_cs_http_timeout_seconds) as client:
                r = await client.get(url)
                r.raise_for_status()
                body = r.text
                chunks.append("--- Внешний JSON-контекст (FGIS_CS_CONTEXT_JSON_URL) ---\n" + body[:40000])
                diag["context_json_url_ok"] = True
        except Exception as exc:
            logger.info("FGIS_CS_CONTEXT_JSON_URL fetch failed: %s", exc)
            diag["errors"].append(f"context_json:{exc!s}")

    base = (settings.fgis_cs_api_base_url or "").strip().rstrip("/")
    path = (settings.fgis_cs_api_path or "").strip()
    if base and path:
        token = (settings.fgis_cs_api_token or "").strip()
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            async with httpx.AsyncClient(timeout=settings.fgis_cs_http_timeout_seconds) as client:
                r = await client.get(f"{base}{path}", headers=headers)
                r.raise_for_status()
                chunks.append("--- Ответ API (FGIS_CS_API_BASE_URL + PATH) ---\n" + r.text[:40000])
                diag["api_ok"] = True
        except Exception as exc:
            logger.info("FGIS_CS API fetch failed: %s", exc)
            diag["errors"].append(f"api:{exc!s}")

    return "\n\n".join(chunks), diag
