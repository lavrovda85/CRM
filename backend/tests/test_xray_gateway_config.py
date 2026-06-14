"""Smoke tests for docker/xray gateway relay config generation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RENDER_SCRIPT = REPO_ROOT / "docker" / "xray" / "render_openai_xray_config.py"
VLESS_URI = (
    "vless://403e01e7-e796-4e1b-9acf-2e6603e52d32@blocked.example:443"
    "?type=tcp&encryption=none&security=reality"
    "&pbk=tvNCbIacIEfGDrg_5D2ujvaPf-WddHjiHRuceMWXNiA"
    "&fp=chrome&sni=www.microsoft.com&sid=ea4bad49d6fa"
    "&spx=%2F&flow=xtls-rprx-vision"
)


def _render_config(env: dict[str, str], out_path: Path) -> dict:
    merged = os.environ.copy()
    merged.update(env)
    merged["XRAY_CONFIG_PATH"] = str(out_path)
    subprocess.run(
        [sys.executable, str(RENDER_SCRIPT)],
        check=True,
        cwd=str(RENDER_SCRIPT.parent),
        env=merged,
        capture_output=True,
        text=True,
    )
    return json.loads(out_path.read_text(encoding="utf-8"))


def test_gateway_relay_inbound(tmp_path: Path) -> None:
    cfg = _render_config(
        {
            "XRAY_GATEWAY_ENABLED": "true",
            "XRAY_GATEWAY_VLESS_URI": VLESS_URI,
            "XRAY_GATEWAY_LISTEN_PORT": "8443",
        },
        tmp_path / "config.json",
    )
    gateway = cfg["inbounds"][0]
    assert gateway["protocol"] == "dokodemo-door"
    assert gateway["port"] == 8443
    assert gateway["settings"]["address"] == "blocked.example"
    assert gateway["settings"]["port"] == 443
    assert cfg["routing"]["rules"][0]["inboundTag"] == ["gateway-relay"]


def test_openai_and_gateway_combined(tmp_path: Path) -> None:
    cfg = _render_config(
        {
            "OPENAI_VLESS_URI": VLESS_URI,
            "XRAY_GATEWAY_ENABLED": "1",
        },
        tmp_path / "config.json",
    )
    tags = {inbound["tag"] for inbound in cfg["inbounds"]}
    assert tags == {"gateway-relay", "http-in"}
    outbound_tags = {outbound["tag"] for outbound in cfg["outbounds"]}
    assert outbound_tags == {"vless-out", "direct"}
