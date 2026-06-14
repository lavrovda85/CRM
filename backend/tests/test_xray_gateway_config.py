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


def _render_config(env: dict[str, str], out_path: Path) -> tuple[dict, Path]:
    merged = os.environ.copy()
    merged.update(env)
    merged["XRAY_CONFIG_PATH"] = str(out_path)
    gateway_env = out_path.parent / "gateway.env"
    merged["XRAY_GATEWAY_ENV_PATH"] = str(gateway_env)
    subprocess.run(
        [sys.executable, str(RENDER_SCRIPT)],
        check=True,
        cwd=str(RENDER_SCRIPT.parent),
        env=merged,
        capture_output=True,
        text=True,
    )
    return json.loads(out_path.read_text(encoding="utf-8")), gateway_env


def test_gateway_only_socat_writes_env_without_xray_config(tmp_path: Path) -> None:
    out_path = tmp_path / "config.json"
    gateway_env = tmp_path / "gateway.env"
    merged = os.environ.copy()
    merged.update(
        {
            "XRAY_GATEWAY_ONLY": "true",
            "XRAY_GATEWAY_VLESS_URI": VLESS_URI,
            "XRAY_GATEWAY_LISTEN_PORT": "8443",
            "XRAY_GATEWAY_DOWNSTREAM_ADDRESS": "10.0.0.5",
            "XRAY_CONFIG_PATH": str(out_path),
            "XRAY_GATEWAY_ENV_PATH": str(gateway_env),
        }
    )
    subprocess.run(
        [sys.executable, str(RENDER_SCRIPT)],
        check=True,
        cwd=str(RENDER_SCRIPT.parent),
        env=merged,
        capture_output=True,
        text=True,
    )
    assert not out_path.exists()
    env_text = gateway_env.read_text(encoding="utf-8")
    assert "XRAY_GATEWAY_RELAY=socat" in env_text
    assert "XRAY_GATEWAY_LISTEN_PORT=8443" in env_text
    assert "XRAY_GATEWAY_DOWNSTREAM_ADDRESS=10.0.0.5" in env_text


def test_gateway_socat_combined_with_openai_writes_env_without_xray_inbound(tmp_path: Path) -> None:
    cfg, gateway_env = _render_config(
        {
            "XRAY_GATEWAY_ENABLED": "true",
            "XRAY_GATEWAY_VLESS_URI": VLESS_URI,
            "XRAY_GATEWAY_LISTEN_PORT": "8443",
            "XRAY_GATEWAY_DOWNSTREAM_ADDRESS": "10.0.0.5",
        },
        tmp_path / "config.json",
    )
    env_text = gateway_env.read_text(encoding="utf-8")
    assert "XRAY_GATEWAY_RELAY=socat" in env_text
    assert "XRAY_GATEWAY_LISTEN_PORT=8443" in env_text
    assert "XRAY_GATEWAY_DOWNSTREAM_ADDRESS=10.0.0.5" in env_text
    assert "XRAY_GATEWAY_DOWNSTREAM_PORT=443" in env_text


def test_gateway_dokodemo_inbound(tmp_path: Path) -> None:
    cfg, _ = _render_config(
        {
            "XRAY_GATEWAY_ENABLED": "true",
            "XRAY_GATEWAY_VLESS_URI": VLESS_URI,
            "XRAY_GATEWAY_RELAY": "xray-dokodemo",
        },
        tmp_path / "config.json",
    )
    gateway = cfg["inbounds"][0]
    assert gateway["protocol"] == "dokodemo-door"
    assert gateway["settings"]["address"] == "blocked.example"


def test_gateway_bridge_inbound(tmp_path: Path) -> None:
    cfg, _ = _render_config(
        {
            "XRAY_GATEWAY_ENABLED": "true",
            "XRAY_GATEWAY_VLESS_URI": VLESS_URI,
            "XRAY_GATEWAY_RELAY": "xray-bridge",
            "XRAY_GATEWAY_REALITY_PRIVATE_KEY": "test-private-key",
        },
        tmp_path / "config.json",
    )
    gateway = cfg["inbounds"][0]
    assert gateway["protocol"] == "vless"
    assert cfg["routing"]["rules"][0]["outboundTag"] == "gateway-vless-out"


def test_openai_and_gateway_socat_combined(tmp_path: Path) -> None:
    cfg, _ = _render_config(
        {
            "OPENAI_VLESS_URI": VLESS_URI,
            "XRAY_GATEWAY_ENABLED": "1",
        },
        tmp_path / "config.json",
    )
    tags = {inbound["tag"] for inbound in cfg["inbounds"]}
    assert tags == {"http-in"}
    outbound_tags = {outbound["tag"] for outbound in cfg["outbounds"]}
    assert outbound_tags == {"vless-out", "direct"}
