#!/usr/bin/env python3
"""Write /etc/xray/config.json: optional VLESS gateway + OpenAI HTTP proxy."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from gateway_common import (
    GATEWAY_INBOUND_TAG,
    GATEWAY_OUTBOUND_TAG,
    VlessUriError,
    gateway_enabled,
    gateway_listen_port,
    gateway_relay_mode,
    resolve_downstream,
    resolve_gateway_uri,
    write_gateway_env,
)

OUT_PATH = Path(os.environ.get("XRAY_CONFIG_PATH", "/etc/xray/config.json"))


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


def _vless_outbound(tag: str, downstream) -> dict:
    return {
        "tag": tag,
        "protocol": "vless",
        "settings": {
            "vnext": [
                {
                    "address": downstream.address,
                    "port": downstream.port,
                    "users": [
                        {
                            "id": downstream.uuid,
                            "encryption": "none",
                            "flow": downstream.flow,
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
                "fingerprint": downstream.fingerprint,
                "serverName": downstream.sni,
                "publicKey": downstream.public_key,
                "shortId": downstream.short_id,
                "spiderX": downstream.spider_x,
            },
        },
    }


def _full_config(uri: str) -> dict:
    downstream = resolve_downstream(uri)
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
            _vless_outbound("vless-out", downstream),
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


def _gateway_dokodemo_inbound(downstream, listen_port: int) -> dict:
    return {
        "tag": GATEWAY_INBOUND_TAG,
        "listen": "0.0.0.0",
        "port": listen_port,
        "protocol": "dokodemo-door",
        "settings": {
            "address": downstream.address,
            "port": downstream.port,
            "network": "tcp",
        },
        "sniffing": {"enabled": False},
    }


def _gateway_bridge_inbound(downstream, listen_port: int, private_key: str) -> dict:
    return {
        "tag": GATEWAY_INBOUND_TAG,
        "listen": "0.0.0.0",
        "port": listen_port,
        "protocol": "vless",
        "settings": {
            "clients": [
                {
                    "id": downstream.uuid,
                    "flow": downstream.flow,
                }
            ],
            "decryption": "none",
        },
        "streamSettings": {
            "network": "tcp",
            "security": "reality",
            "realitySettings": {
                "show": False,
                "dest": f"{downstream.sni}:443",
                "xver": 0,
                "serverNames": [downstream.sni],
                "privateKey": private_key,
                "shortIds": [downstream.short_id],
            },
        },
        "sniffing": {"enabled": False},
    }


def _append_gateway(cfg: dict, gateway_uri: str) -> str | None:
    relay_mode = gateway_relay_mode()
    try:
        downstream = resolve_downstream(gateway_uri)
    except VlessUriError as exc:
        return str(exc)

    listen_port = gateway_listen_port(downstream.port)
    write_gateway_env(downstream, listen_port, relay_mode)

    if relay_mode == "socat":
        print(
            "Gateway socat relay enabled: "
            f"0.0.0.0:{listen_port} -> {downstream.address}:{downstream.port} "
            "(raw TCP; users change only IP in their VLESS link).",
            file=sys.stderr,
        )
        return None

    if relay_mode == "xray-bridge":
        private_key = (os.environ.get("XRAY_GATEWAY_REALITY_PRIVATE_KEY") or "").strip()
        if not private_key:
            return "XRAY_GATEWAY_REALITY_PRIVATE_KEY is required for xray-bridge mode"
        cfg.setdefault("inbounds", []).insert(
            0,
            _gateway_bridge_inbound(downstream, listen_port, private_key),
        )
        outbound = _vless_outbound(GATEWAY_OUTBOUND_TAG, downstream)
        outbounds = cfg.setdefault("outbounds", [])
        if not any(item.get("tag") == GATEWAY_OUTBOUND_TAG for item in outbounds):
            outbounds.insert(0, outbound)
        routing = cfg.setdefault("routing", {"domainStrategy": "AsIs", "rules": []})
        routing.setdefault("rules", []).insert(
            0,
            {
                "type": "field",
                "inboundTag": [GATEWAY_INBOUND_TAG],
                "outboundTag": GATEWAY_OUTBOUND_TAG,
            },
        )
        print(
            "Gateway xray-bridge enabled: "
            f"0.0.0.0:{listen_port} -> {downstream.address}:{downstream.port}.",
            file=sys.stderr,
        )
        return None

    cfg.setdefault("inbounds", []).insert(
        0,
        _gateway_dokodemo_inbound(downstream, listen_port),
    )
    routing = cfg.setdefault("routing", {"domainStrategy": "AsIs", "rules": []})
    routing.setdefault("rules", []).insert(
        0,
        {
            "type": "field",
            "inboundTag": [GATEWAY_INBOUND_TAG],
            "outboundTag": "direct",
        },
    )
    print(
        "Gateway dokodemo-door relay enabled: "
        f"0.0.0.0:{listen_port} -> {downstream.address}:{downstream.port}.",
        file=sys.stderr,
    )
    return None


def main() -> int:
    openai_uri = (os.environ.get("OPENAI_VLESS_URI") or "").strip()
    gateway_uri = resolve_gateway_uri() if gateway_enabled() else ""

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

    if gateway_enabled():
        if not gateway_uri:
            print(
                "XRAY_GATEWAY_ENABLED but no XRAY_GATEWAY_VLESS_URI or OPENAI_VLESS_URI for downstream target.",
                file=sys.stderr,
            )
            return 1
        gateway_error = _append_gateway(cfg, gateway_uri)
        if gateway_error:
            print(f"Invalid gateway settings: {gateway_error}", file=sys.stderr)
            return 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
