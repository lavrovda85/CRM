"""Time-limited signed tokens for browser-safe file URLs (no MinIO presign to the client).

Tokens are used as ``?token=`` on ``GET /api/v1/documents/{id}/file`` and chat attachment
streams so ``<img src>`` works without sending ``Authorization`` headers.
"""

from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import quote

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


def content_disposition_header(filename: str, mime_type: str) -> str:
    """Build ``Content-Disposition`` (inline for images, attachment otherwise) with UTF-8 filename."""
    kind = "inline" if (mime_type or "").lower().startswith("image/") else "attachment"
    encoded = quote(filename, safe="")
    return f"{kind}; filename*=UTF-8''{encoded}"


def _serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key, salt="crm-minio-file-proxy-v1")


def encode_document_file_token(
    secret_key: str,
    *,
    document_id: uuid.UUID,
    company_id: uuid.UUID,
    user_sub: str,
) -> str:
    """Build a token granting read access to one document within a company."""
    payload: dict[str, Any] = {
        "k": "doc",
        "d": str(document_id),
        "c": str(company_id),
        "u": (user_sub or "").strip(),
    }
    return _serializer(secret_key).dumps(payload)


def decode_document_file_token(secret_key: str, token: str, *, max_age: int = 3600) -> dict[str, Any] | None:
    """Validate token and return payload, or None if invalid or expired."""
    try:
        data = _serializer(secret_key).loads(token, max_age=max_age)
        if not isinstance(data, dict) or data.get("k") != "doc":
            return None
        return data
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None


def encode_chat_attachment_token(secret_key: str, *, attachment_id: uuid.UUID, user_sub: str) -> str:
    """Build a token for downloading one chat attachment."""
    payload: dict[str, Any] = {
        "k": "chat",
        "a": str(attachment_id),
        "u": (user_sub or "").strip(),
    }
    return _serializer(secret_key).dumps(payload)


def decode_chat_attachment_token(secret_key: str, token: str, *, max_age: int = 3600) -> dict[str, Any] | None:
    try:
        data = _serializer(secret_key).loads(token, max_age=max_age)
        if not isinstance(data, dict) or data.get("k") != "chat":
            return None
        return data
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None
