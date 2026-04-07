"""Tests for deploy log SHA markers."""

from app.services.deploy_log_utils import parse_shas_from_deploy_log


def test_parse_shas_from_log() -> None:
    log = """DEPLOY_PREV_SHA=abc123
DEPLOY_NEW_SHA=def456
done
"""
    prev, new = parse_shas_from_deploy_log(log)
    assert prev == "abc123"
    assert new == "def456"


def test_parse_shas_empty() -> None:
    assert parse_shas_from_deploy_log("") == (None, None)
