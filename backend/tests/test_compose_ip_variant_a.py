"""Guardrails for LAN deploy: Next.js on host 9000 + empty NEXT_PUBLIC_API_URL (same-origin /api/v1)."""

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_compose_uses_frontend_host_port_env() -> None:
    """Base compose maps host port via FRONTEND_HOST_PORT (variant A uses 9000 in env.template.ip)."""
    text = (_repo_root() / "docker-compose.yml").read_text(encoding="utf-8")
    assert "FRONTEND_HOST_PORT" in text, "docker-compose.yml should use FRONTEND_HOST_PORT for frontend publish port"


def test_env_template_ip_sets_frontend_host_port_9000() -> None:
    """LAN template pins Next.js to port 9000 for same-origin /api/v1."""
    text = (_repo_root() / "deploy" / "server" / "env.template.ip").read_text(encoding="utf-8")
    assert "FRONTEND_HOST_PORT=9000" in text.replace(" ", "")


def test_env_template_documents_empty_next_public_api_url() -> None:
    """Template must keep NEXT_PUBLIC_API_URL empty for variant A."""
    text = (_repo_root() / "deploy" / "server" / "env.template.ip").read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n")
    assert "NEXT_PUBLIC_API_URL=\n" in normalized, "NEXT_PUBLIC_API_URL must be empty (no value after =)"


def test_keycloak_realm_allows_localhost_9000_redirect() -> None:
    """hvac-frontend client must allow OAuth redirect to UI on port 9000."""
    text = (_repo_root() / "docker" / "keycloak" / "hvac-realm.json").read_text(encoding="utf-8")
    assert "http://localhost:9000/*" in text
    assert "http://127.0.0.1:9000/*" in text
