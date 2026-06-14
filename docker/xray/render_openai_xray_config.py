#!/usr/bin/env python3
"""Write /etc/xray/config.json: optional VLESS TCP relay gateway + OpenAI HTTP proxy."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

_dir = Path(__file__).resolve().parent


def _vless_uri_module_path() -> Path:
    for candidate in (
        _dir / "vless_uri.py",
        _dir.parents[1] / "backend" / "app" / "services" / "vless_uri.py",
    ):
        if candidate.is_file():
            return candidate
    raise RuntimeError("Cannot find vless_uri.py")


_spec = importlib.util.spec_from_file_location("vless_uri", _vless_uri_module_path())
if _spec is None or _spec.loader is None:
    raise RuntimeError("Cannot load vless_uri.py")
_vu = importlib.util.module_from_spec(_spec)
# Required before exec_module so dataclasses can resolve cls.__module__ (Python 3.12+).
sys.modules[_spec.name] = _vu
_spec.loader.exec_module(_vu)
VlessUriError = _vu.VlessUriError
parse_vless_reality_uri = _vu.parse_vless_reality_uri


OUT_PATH = Path(os.environ.get("XRAY_CONFIG_PATH", "/etc/xray/config.json"))
GATEWAY_INBOUND_TAG = "gateway-relay"


def _env_truthy(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _gateway_listen_port(default_port: int) -> int:
    raw = (os.environ.get("XRAY_GATEWAY_LISTEN_PORT") or "").strip()
    if not raw:
        return default_port
    try:
        port = int(raw)
    except ValueError:
        print(f"Invalid XRAY_GATEWAY_LISTEN_PORT={raw!r}, using {default_port}.", file=sys.stderr)
        return default_port
    if port < 1 or port > 65535:
        print(f"XRAY_GATEWAY_LISTEN_PORT out of range ({port}), using {default_port}.", file=sys.stderr)
        return default_port
    return port


def _gateway_relay_inbound(downstream_address: str, downstream_port: int, listen_port: int) -> dict:
    """Transparent TCP relay: clients keep the same VLESS URI, only the host IP changes."""
    return {
        "tag": GATEWAY_INBOUND_TAG,
        "listen": "0.0.0.0",
        "port": listen_port,
        "protocol": "dokodemo-door",
        "settings": {
            "address": downstream_address,
            "port": downstream_port,
            "network": "tcp",
        },
        "sniffing": {"enabled": False},
    }


def _gateway_routing_rule() -> dict:
    return {
        "type": "field",
        "inboundTag": [GATEWAY_INBOUND_TAG],
        "outboundTag": "direct",
    }


def _resolve_gateway_uri() -> str:
    return (os.environ.get("XRAY_GATEWAY_VLESS_URI") or os.environ.get("OPENAI_VLESS_URI") or "").strip()


def _direct_only_config() -> dict:
    """HTTP proxy that forwards everything without upstream (no VLESS)."""
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "tag": "http-in",
                "listen": "0.0.0.0",
                "port": 10808,
                "protocol": "http",
                "sniffing": {
                    "enabled": True,
                    "destOverride": ["http", "tls", "quic"],
                },
            }
        ],
        "outbounds": [
            {"tag": "direct", "protocol": "freedom", "settings": {}},
        ],
        "routing": {
            "domainStrategy": "AsIs",
            "rules": [
                {
                    "type": "field",
                    "network": "tcp,udp",
                    "outboundTag": "direct",
                }
            ],
        },
    }


def _full_config(uri: str) -> dict:
    p = parse_vless_reality_uri(uri)
    vless_out = {
        "tag": "vless-out",
        "protocol": "vless",
        "settings": {
            "vnext": [
                {
                    "address": p.address,
                    "port": p.port,
                    "users": [
                        {
                            "id": p.uuid,
                            "encryption": "none",
                            "flow": p.flow,
                        }
                    ],
                }
            ]
        },
        "streamSettings": {
            "network": "tcp",
            "security": "reality",
            "realitySettings": {
                "show": False,
                "fingerprint": p.fingerprint,
                "serverName": p.sni,
                "publicKey": p.public_key,
                "shortId": p.short_id,
                "spiderX": p.spider_x,
            },
        },
    }
    return {
        "log": {"loglevel": "warning"},
        "inbounds": [
            {
                "tag": "http-in",
                "listen": "0.0.0.0",
                "port": 10808,
                "protocol": "http",
                "sniffing": {
                    "enabled": True,
                    "destOverride": ["http", "tls", "quic"],
                },
            }
        ],
        "outbounds": [
            vless_out,
            {"tag": "direct", "protocol": "freedom", "settings": {}},
        ],
        "routing": {
            "domainStrategy": "AsIs",
            "rules": [
                {
                    "type": "field",
                    "domain": [
                        "geosite:openai",
                        "domain:api.openai.com",
                        "domain:openai.com",
                        "suffix:openai.com",
                        "domain:chat.openai.com",
                        "domain:platform.openai.com",
                        "domain:cdn.openai.com",
                        "domain:auth.openai.com",
                    ],
                    "outboundTag": "vless-out",
                },
                {
                    "type": "field",
                    "network": "tcp,udp",
                    "outboundTag": "direct",
                },
            ],
        },
    }


def _append_gateway(cfg: dict, gateway_uri: str) -> dict | None:
    """Add dokodemo-door relay inbound; returns error message or None on success."""
    try:
        downstream = parse_vless_reality_uri(gateway_uri)
    except VlessUriError as exc:
        return str(exc)

    listen_port = _gateway_listen_port(downstream.port)
    cfg.setdefault("inbounds", []).insert(0, _gateway_relay_inbound(
        downstream.address,
        downstream.port,
        listen_port,
    ))
    routing = cfg.setdefault("routing", {"domainStrategy": "AsIs", "rules": []})
    routing.setdefault("rules", []).insert(0, _gateway_routing_rule())
    print(
        "Gateway relay enabled: "
        f"0.0.0.0:{listen_port} -> {downstream.address}:{downstream.port} "
        "(users change only IP in their VLESS link).",
        file=sys.stderr,
    )
    return None


def main() -> int:
    openai_uri = (os.environ.get("OPENAI_VLESS_URI") or "").strip()
    gateway_enabled = _env_truthy("XRAY_GATEWAY_ENABLED")
    gateway_uri = _resolve_gateway_uri() if gateway_enabled else ""

    if not openai_uri:
        cfg = _direct_only_config()
        print(
            "OPENAI_VLESS_URI unset: xray HTTP inbound -> direct only (set OPENAI_HTTP_PROXY only if needed).",
            file=sys.stderr,
        )
    else:
        try:
            cfg = _full_config(openai_uri)
        except VlessUriError as exc:
            print(f"Invalid OPENAI_VLESS_URI: {exc}", file=sys.stderr)
            return 1

    if gateway_enabled:
        if not gateway_uri:
            print(
                "XRAY_GATEWAY_ENABLED but no XRAY_GATEWAY_VLESS_URI or OPENAI_VLESS_URI for downstream target.",
                file=sys.stderr,
            )
            return 1
        gateway_error = _append_gateway(cfg, gateway_uri)
        if gateway_error:
            print(f"Invalid gateway VLESS URI: {gateway_error}", file=sys.stderr)
            return 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
