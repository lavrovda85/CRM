"""Normalize zakupki.gov.ru notice URLs to the main «common-info» card (better HTML for parsing).

Avoids print-form / document-only URLs when ``regNumber`` is present.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

_REG_NUMBER_RE = re.compile(r"regNumber[=:](\d{10,30})", re.I)
_REG_DIGITS_ONLY = re.compile(r"\D")
_NOTICE_SEGMENT_RE = re.compile(r"/epz/order/notice/([^/]+)/", re.I)


def canonical_zakupki_notice_url(url: str) -> str:
    """Return ``common-info.html`` URL for the same notice when possible.

    Args:
        url: Any zakupki.gov.ru notice link (search, printForm, common-info, etc.).

    Returns:
        Canonical https URL or the original string if it cannot be rewritten safely.
    """
    s = (url or "").strip()
    if not s:
        return s
    try:
        p = urlparse(s)
    except Exception:
        return s
    host = (p.netloc or "").lower()
    if "zakupki.gov.ru" not in host:
        return s
    qs = parse_qs(p.query, keep_blank_values=True)
    reg = (qs.get("regNumber") or [None])[0]
    if not reg:
        return s
    path = p.path or ""
    m = re.search(r"/epz/order/notice/([^/]+)/", path)
    segment = m.group(1) if m else "ea20"
    new_path = f"/epz/order/notice/{segment}/view/common-info.html"
    return urlunparse(("https", "zakupki.gov.ru", new_path, "", urlencode({"regNumber": reg}), ""))


def reg_number_from_zakupki_url(url: str) -> str | None:
    """Return ``regNumber`` query value for a zakupki.gov.ru URL, or None."""
    s = (url or "").strip()
    if not s or "zakupki.gov.ru" not in s.lower():
        return None
    try:
        qs = parse_qs(urlparse(s).query, keep_blank_values=True)
        r = (qs.get("regNumber") or [None])[0]
        return r.strip() if r else None
    except Exception:
        return None


def zakupki_reg_numbers_equivalent(a: str | None, b: str | None) -> bool:
    """Compare registry numbers allowing formatting differences (spaces, prefixes)."""
    if not a or not b:
        return False
    da = _REG_DIGITS_ONLY.sub("", a)
    db = _REG_DIGITS_ONLY.sub("", b)
    return bool(da) and da == db


def extract_reg_number_from_zakupki_html(html: str) -> str | None:
    """Best-effort ``regNumber`` from notice HTML (links, forms, JS) when the request URL omits it.

    Args:
        html: Raw HTML of a zakupki.gov.ru page.

    Returns:
        Registry number string or None.
    """
    if not (html and html.strip()):
        return None
    m = _REG_NUMBER_RE.search(html)
    return m.group(1) if m else None


def extract_notice_segment_from_zakupki_html(html: str) -> str | None:
    """Return notice path segment (e.g. ea20, zk504) from HTML or None."""
    if not (html and html.strip()):
        return None
    m = _NOTICE_SEGMENT_RE.search(html)
    return m.group(1) if m else None


def zakupki_common_info_url(reg_number: str, segment: str = "ea20") -> str:
    """Build https common-info URL for a registry number."""
    reg = (reg_number or "").strip()
    seg = (segment or "ea20").strip() or "ea20"
    path = f"/epz/order/notice/{seg}/view/common-info.html"
    return urlunparse(("https", "zakupki.gov.ru", path, "", urlencode({"regNumber": reg}), ""))


def derive_zakupki_documents_url(notice_url: str) -> str | None:
    """Build ``documents.html`` URL for the same notice as ``common-info`` (documentation package)."""
    s = (notice_url or "").strip()
    if not s:
        return None
    try:
        p = urlparse(s)
    except Exception:
        return None
    if "zakupki.gov.ru" not in (p.netloc or "").lower():
        return None
    qs = parse_qs(p.query, keep_blank_values=True)
    reg = (qs.get("regNumber") or [None])[0]
    if not reg:
        return None
    path = p.path or ""
    m = re.search(r"/epz/order/notice/([^/]+)/", path)
    segment = m.group(1) if m else "ea20"
    new_path = f"/epz/order/notice/{segment}/view/documents.html"
    return urlunparse(("https", "zakupki.gov.ru", new_path, "", urlencode({"regNumber": reg}), ""))
