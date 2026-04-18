"""Tests for client extra_data / legal requisites helpers."""

from datetime import datetime, timezone
from unittest.mock import MagicMock
import uuid

from app.schemas.client import ClientCreate, ClientUpdate
from app.services.client_payload import (
    build_client_response,
    extra_data_for_create,
    extra_data_for_update,
    legal_fields_from_extra,
)


def test_extra_data_for_create_merges_legal() -> None:
    body = ClientCreate(
        name="ООО Тест",
        client_type="organization",
        inn="7707083893",
        kpp="770701001",
        extra_data={"import_source": "test"},
    )
    ed = extra_data_for_create(body)
    assert ed["import_source"] == "test"
    assert ed["kpp"] == "770701001"


def test_extra_data_for_update_extra_only() -> None:
    existing = {"a": 1}
    body = ClientUpdate(extra_data={"b": 2})
    merged = extra_data_for_update(existing, body)
    assert merged == {"a": 1, "b": 2}


def test_extra_data_for_update_legal_only() -> None:
    existing = {}
    body = ClientUpdate(kpp="123456789")
    merged = extra_data_for_update(existing, body)
    assert merged == {"kpp": "123456789"}


def test_legal_fields_from_extra() -> None:
    d = legal_fields_from_extra({"kpp": "1", "ogrn": "2", "x": "y"})
    assert d["kpp"] == "1"
    assert d["ogrn"] == "2"


def test_build_client_response_reads_legal_from_extra() -> None:
    c = MagicMock()
    c.id = uuid.uuid4()
    c.name = "X"
    c.client_type = "organization"
    c.address = None
    c.phone = None
    c.email = None
    c.inn = None
    c.coordinates = None
    c.extra_data = {"kpp": "111"}
    c.notes = None
    c.contacts = []
    c.created_at = datetime.now(timezone.utc)
    c.updated_at = datetime.now(timezone.utc)
    r = build_client_response(c)
    assert r.kpp == "111"
