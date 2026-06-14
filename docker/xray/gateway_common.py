#!/usr/bin/env python3
"""Shared helpers for optional Xray TCP gateway relay."""

from __future__ import annotations

import importlib.util
import os
import sys
from dataclasses import replace
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


def load_vless_uri_module():
    spec = importlib.util.spec_from_file_location("vless_uri", _vless_uri_module_path())
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load vless_uri.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_vu = load_vless_uri_module()
VlessUriError = _vu.VlessUriError
VlessRealityParams = _vu.VlessRealityParams
parse_vless_reality_uri = _vu.parse_vless_reality_uri

GATEWAY_INBOUND_TAG = "gateway-relay"
GATEWAY_OUTBOUND_TAG = "gateway-vless-out"
GATEWAY_ENV_PATH = Path(os.environ.get("XRAY_GATEWAY_ENV_PATH", "/tmp/xray-gateway.env"))


def env_truthy(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def gateway_only() -> bool:
    return env_truthy("XRAY_GATEWAY_ONLY")


def gateway_enabled() -> bool:
    return env_truthy("XRAY_GATEWAY_ENABLED") or gateway_only()


def resolve_gateway_uri() -> str:
    return (os.environ.get("XRAY_GATEWAY_VLESS_URI") or os.environ.get("OPENAI_VLESS_URI") or "").strip()


def gateway_relay_mode() -> str:
    mode = (os.environ.get("XRAY_GATEWAY_RELAY") or "socat").strip().lower()
    if mode in {"socat", "xray-bridge", "xray-dokodemo"}:
        return mode
    print(f"Unknown XRAY_GATEWAY_RELAY={mode!r}, using socat.", file=sys.stderr)
    return "socat"


def gateway_listen_port(default_port: int) -> int:
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


def resolve_downstream(gateway_uri: str) -> VlessRealityParams:
    downstream = parse_vless_reality_uri(gateway_uri)
    override = (os.environ.get("XRAY_GATEWAY_DOWNSTREAM_ADDRESS") or "").strip()
    if override:
        return replace(downstream, address=override)
    return downstream


def write_gateway_env(downstream: VlessRealityParams, listen_port: int, relay_mode: str) -> None:
    lines = [
        f"XRAY_GATEWAY_RELAY={relay_mode}",
        f"XRAY_GATEWAY_LISTEN_PORT={listen_port}",
        f"XRAY_GATEWAY_DOWNSTREAM_ADDRESS={downstream.address}",
        f"XRAY_GATEWAY_DOWNSTREAM_PORT={downstream.port}",
    ]
    GATEWAY_ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
