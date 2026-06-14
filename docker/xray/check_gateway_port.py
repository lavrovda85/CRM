#!/usr/bin/env python3
"""Preflight checks before starting the TCP gateway relay."""

from __future__ import annotations

import os
import socket
import sys


def main() -> int:
    raw = (os.environ.get("XRAY_GATEWAY_LISTEN_PORT") or "443").strip()
    try:
        port = int(raw)
    except ValueError:
        print(f"Invalid XRAY_GATEWAY_LISTEN_PORT={raw!r}", file=sys.stderr)
        return 1

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        probe.bind(("0.0.0.0", port))
    except OSError as exc:
        print(
            f"Port {port} is already in use ({exc}). "
            "Stop the conflicting process/container or set XRAY_GATEWAY_LISTEN_PORT "
            "(for example 8443) in .env.",
            file=sys.stderr,
        )
        print(
            "On the server: sudo ss -tlnp | grep ':443'  "
            "and docker compose down xray-openai xray-gateway",
            file=sys.stderr,
        )
        return 1
    finally:
        probe.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
