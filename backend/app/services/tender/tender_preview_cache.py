"""In-memory TTL cache of parsed tender previews for CRM import (search → import without re-scraping gaps).

Stores structured notice fields and deadlines keyed by canonical URL. Not a source of truth for audits;
``import_tender_from_url`` always re-fetches, but can merge cached structured data when the page is thin.
"""

from __future__ import annotations

import hashlib
import threading
import time
from typing import Any

_LOCK = threading.Lock()
_STORE: dict[str, tuple[float, dict[str, Any]]] = {}
_TTL_SEC = 86400
_MAX_KEYS = 2000


def _key(url: str) -> str:
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()


def store_tender_preview(canonical_url: str, payload: dict[str, Any]) -> None:
    """Save or replace preview payload for URL (thread-safe, LRU-ish by count)."""
    if not canonical_url.strip():
        return
    k = _key(canonical_url)
    now = time.monotonic()
    with _LOCK:
        if len(_STORE) >= _MAX_KEYS:
            # Drop arbitrary oldest bucket (simple; avoids unbounded growth)
            oldest = min(_STORE.items(), key=lambda x: x[1][0], default=None)
            if oldest:
                del _STORE[oldest[0]]
        _STORE[k] = (now, dict(payload))


def get_tender_preview(canonical_url: str) -> dict[str, Any] | None:
    """Return cached payload if present and not expired."""
    if not canonical_url.strip():
        return None
    k = _key(canonical_url)
    now = time.monotonic()
    with _LOCK:
        row = _STORE.get(k)
        if not row:
            return None
        ts, payload = row
        if now - ts > _TTL_SEC:
            del _STORE[k]
            return None
        return dict(payload)


def touch_tender_preview(canonical_url: str) -> None:
    """Refresh TTL for a key if it exists (optional)."""
    if not canonical_url.strip():
        return
    k = _key(canonical_url)
    now = time.monotonic()
    with _LOCK:
        if k in _STORE:
            _, payload = _STORE[k]
            _STORE[k] = (now, payload)
