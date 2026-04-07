#!/usr/bin/env python3
"""Minimal HTTP API for deploy-agent: /health, /deploy, /branches, /project-logs."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

LOCK = threading.Lock()


def _compose_cmd() -> list[str]:
    """Build docker-compose argv (v1) matching deploy.sh."""
    args: list[str] = ["docker-compose"]
    if os.environ.get("COMPOSE_PROJECT_NAME"):
        args.extend(["-p", os.environ["COMPOSE_PROJECT_NAME"]])
    args.extend(["-f", os.environ.get("DEPLOY_COMPOSE_FILE_MAIN", "docker-compose.yml")])
    extra = os.environ.get("DEPLOY_COMPOSE_FILE_EXTRA")
    if extra:
        args.extend(["-f", extra])
    return args


class Handler(BaseHTTPRequestHandler):
    """JSON handlers for deploy operations."""

    def log_message(self, *_args: object) -> None:
        return

    def _send(self, code: int, body: dict) -> None:
        raw = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/health":
            self._send(200, {"ok": True})
            return

        if path == "/branches":
            repo = os.environ.get("DEPLOY_REPO_PATH", "/deploy/repo")
            try:
                subprocess.run(
                    ["git", "-C", repo, "fetch", "origin"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                p = subprocess.run(
                    ["git", "-C", repo, "branch", "-r"],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                names: list[str] = []
                for line in (p.stdout or "").splitlines():
                    line = line.strip()
                    if not line or "->" in line:
                        continue
                    if line.startswith("origin/"):
                        b = line.replace("origin/", "", 1).strip()
                        if b != "HEAD":
                            names.append(b)
                self._send(200, {"branches": sorted(set(names))})
            except subprocess.SubprocessError as exc:
                self._send(500, {"error": str(exc), "branches": []})
            return

        if path == "/project-logs":
            qs = parse_qs(parsed.query or "")
            raw_tail = (qs.get("tail") or ["400"])[0]
            try:
                tail_n = max(50, min(int(raw_tail), 5000))
            except ValueError:
                tail_n = 400
            repo = os.environ.get("DEPLOY_REPO_PATH", "/deploy/repo")
            cmd = _compose_cmd() + [
                "logs",
                f"--tail={tail_n}",
                "backend",
                "celery-worker",
                "nginx",
            ]
            try:
                p = subprocess.run(
                    cmd,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=repo,
                    env=os.environ.copy(),
                )
                out = (p.stdout or "") + (p.stderr or "")
                self._send(200, {"lines": out[-800_000:]})
            except subprocess.SubprocessError as exc:
                self._send(500, {"lines": "", "error": str(exc)})
            return

        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/deploy":
            self._send(404, {"error": "not found"})
            return

        if not LOCK.acquire(blocking=False):
            self._send(409, {"error": "deploy already running", "exit_code": 1, "log": ""})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                data = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self._send(400, {"error": "invalid json", "exit_code": 1, "log": ""})
                return

            branch = str(data.get("branch") or "").strip()
            if not branch:
                self._send(400, {"error": "branch required", "exit_code": 1, "log": ""})
                return

            p = subprocess.run(
                ["/bin/bash", "/deploy.sh", branch],
                capture_output=True,
                text=True,
                timeout=3600,
                env=os.environ.copy(),
            )
            log = (p.stdout or "") + (p.stderr or "")
            code = 0 if p.returncode == 0 else int(p.returncode)
            self._send(200, {"exit_code": code, "log": log[-900_000:]})
        finally:
            LOCK.release()


def main() -> None:
    host = os.environ.get("DEPLOY_AGENT_BIND", "0.0.0.0")
    port = int(os.environ.get("DEPLOY_AGENT_PORT", "9090"))
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"deploy-agent listening on {host}:{port}", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
