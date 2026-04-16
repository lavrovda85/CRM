"""Tests for signed file-proxy tokens."""

from __future__ import annotations

import uuid

from app.core.file_proxy_token import (
    content_disposition_header,
    decode_chat_attachment_token,
    decode_document_file_token,
    encode_chat_attachment_token,
    encode_document_file_token,
)


def test_document_token_roundtrip() -> None:
    secret = "test-secret-key-min-32-chars-long!!"
    cid = uuid.uuid4()
    did = uuid.uuid4()
    raw = encode_document_file_token(secret, document_id=did, company_id=cid, user_sub="sub-1")
    data = decode_document_file_token(secret, raw, max_age=3600)
    assert data is not None
    assert data["d"] == str(did)
    assert data["c"] == str(cid)
    assert data["u"] == "sub-1"


def test_chat_token_roundtrip() -> None:
    secret = "test-secret-key-min-32-chars-long!!"
    aid = uuid.uuid4()
    raw = encode_chat_attachment_token(secret, attachment_id=aid, user_sub="u2")
    data = decode_chat_attachment_token(secret, raw, max_age=3600)
    assert data is not None
    assert data["a"] == str(aid)


def test_content_disposition_image() -> None:
    h = content_disposition_header("фото.png", "image/png")
    assert h.startswith("inline")
    assert "UTF-8" in h


def test_content_disposition_doc() -> None:
    h = content_disposition_header("file.doc", "application/msword")
    assert h.startswith("attachment")
