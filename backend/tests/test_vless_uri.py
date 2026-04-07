"""Tests for VLESS Reality URI parsing (OpenAI Xray sidecar)."""

from __future__ import annotations

import pytest

from app.services.vless_uri import VlessUriError, parse_vless_reality_uri


def test_parse_vless_reality_minimal() -> None:
    uri = (
        "vless://403e01e7-e796-4e1b-9acf-2e6603e52d32@example.com:443"
        "?type=tcp&encryption=none&security=reality"
        "&pbk=tvNCbIacIEfGDrg_5D2ujvaPf-WddHjiHRuceMWXNiA"
        "&fp=chrome&sni=www.microsoft.com&sid=ea4bad49d6fa"
        "&spx=%2F&flow=xtls-rprx-vision"
    )
    p = parse_vless_reality_uri(uri)
    assert p.uuid == "403e01e7-e796-4e1b-9acf-2e6603e52d32"
    assert p.address == "example.com"
    assert p.port == 443
    assert p.flow == "xtls-rprx-vision"
    assert p.sni == "www.microsoft.com"
    assert p.public_key == "tvNCbIacIEfGDrg_5D2ujvaPf-WddHjiHRuceMWXNiA"
    assert p.short_id == "ea4bad49d6fa"
    assert p.spider_x == "/"
    assert p.fingerprint == "chrome"


def test_parse_rejects_non_reality() -> None:
    uri = "vless://403e01e7-e796-4e1b-9acf-2e6603e52d32@h:443?security=tls"
    with pytest.raises(VlessUriError, match="reality"):
        parse_vless_reality_uri(uri)


def test_parse_rejects_bad_scheme() -> None:
    with pytest.raises(VlessUriError):
        parse_vless_reality_uri("https://example.com")
