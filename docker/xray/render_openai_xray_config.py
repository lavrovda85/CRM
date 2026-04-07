#!/usr/bin/env python3
"""Write /etc/xray/config.json: HTTP inbound + OpenAI -> VLESS Reality, else direct."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

_dir = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("vless_uri", _dir / "vless_uri.py")
if _spec is None or _spec.loader is None:
    raise RuntimeError("Cannot load vless_uri.py")
_vu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_vu)
VlessUriError = _vu.VlessUriError
parse_vless_reality_uri = _vu.parse_vless_reality_uri


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


def main() -> int:
    uri = (os.environ.get("OPENAI_VLESS_URI") or "").strip()
    if not uri:
        cfg = _direct_only_config()
        print("OPENAI_VLESS_URI unset: xray HTTP inbound -> direct only (set OPENAI_HTTP_PROXY only if needed).", file=sys.stderr)
    else:
        try:
            cfg = _full_config(uri)
        except VlessUriError as e:
            print(f"Invalid OPENAI_VLESS_URI: {e}", file=sys.stderr)
            return 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_PATH}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
