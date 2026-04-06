"""Tests for optional FGIS CS context fetch."""

from __future__ import annotations

import pytest

from app.services.fgis_cs_client import fetch_fgis_external_context


@pytest.mark.asyncio
async def test_fetch_fgis_external_context_empty_without_urls() -> None:
    text, diag = await fetch_fgis_external_context()
    assert text == ""
    assert "errors" in diag
