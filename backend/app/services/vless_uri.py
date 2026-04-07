"""Parse VLESS sharing links (Reality) for Xray outbound configuration.

Used by tests and documented for the docker/xray sidecar (copies this file at build time).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse


class VlessUriError(ValueError):
    """Invalid or unsupported VLESS URI."""


@dataclass(frozen=True)
class VlessRealityParams:
    """Fields required for Xray VLESS + REALITY outbound."""

    uuid: str
    address: str
    port: int
    flow: str
    sni: str
    public_key: str
    short_id: str
    spider_x: str
    fingerprint: str


def parse_vless_reality_uri(uri: str) -> VlessRealityParams:
    """Parse a ``vless://`` URI with Reality (tcp, security=reality, pbk, sni, sid, spx, flow).

    Args:
        uri: Full sharing link (may include fragment #name).

    Returns:
        Structured parameters for Xray JSON.

    Raises:
        VlessUriError: If scheme or required query keys are missing.
    """
    raw = (uri or "").strip()
    if not raw.startswith("vless://"):
        raise VlessUriError("URI must start with vless://")

    parsed = urlparse(raw)
    if not parsed.hostname:
        raise VlessUriError("Missing host in VLESS URI")

    uuid = (parsed.username or "").strip()
    if not uuid or not re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        uuid,
        re.I,
    ):
        raise VlessUriError("Invalid or missing UUID in VLESS URI")

    port = parsed.port or 443
    q = parse_qs(parsed.query)
    def _one(key: str, default: str = "") -> str:
        vals = q.get(key, [])
        return unquote(vals[0]).strip() if vals else default

    security = _one("security", "none")
    if security != "reality":
        raise VlessUriError("Only security=reality is supported for OpenAI Xray outbound")

    pbk = _one("pbk")
    sni = _one("sni")
    sid = _one("sid")
    if not pbk or not sni or not sid:
        raise VlessUriError("Missing pbk, sni, or sid for Reality")

    spx = _one("spx", "/")
    fp = _one("fp", "chrome")
    flow = _one("flow", "")
    if not flow:
        raise VlessUriError("Missing flow (e.g. xtls-rprx-vision)")

    return VlessRealityParams(
        uuid=uuid.lower(),
        address=parsed.hostname.strip(),
        port=int(port),
        flow=flow,
        sni=sni,
        public_key=pbk,
        short_id=sid,
        spider_x=spx or "/",
        fingerprint=fp or "chrome",
    )
