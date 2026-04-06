"""Parse ЕИС «Документация» page and import publicly accessible filestore attachments.

Files are linked as ``/44fz/filestore/public/.../file.html?uid=...`` (or ``223fz``) — these can be
downloaded without a personal cabinet login. Stored in MinIO and linked to the tender for later
AI analysis (summaries, compliance checks).
"""

from __future__ import annotations

import io
import logging
import re
import uuid
from typing import Any

from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.document_service import DocumentService
from .tender_external_service import tender_http_get

logger = logging.getLogger(__name__)

_UID_RE = re.compile(r"[?&]uid=([0-9A-Fa-f]{32})", re.I)


def extract_zakupki_filestore_links(html: str) -> list[dict[str, str]]:
    """Return list of ``{url, title, label, uid}`` for public filestore download links.

    Deduplicates by ``uid`` query parameter when present (ЕИС often repeats the same link).
    """
    if not (html and html.strip()):
        return []
    soup = BeautifulSoup(html, "lxml")
    out: list[dict[str, str]] = []
    seen_uid: set[str] = set()
    seen_url: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = str(a.get("href") or "").strip()
        low = href.lower()
        if "filestore/public" not in low:
            continue
        if "zakupki.gov.ru" not in low and not low.startswith("/"):
            continue
        if "uid=" not in low:
            continue
        if href.startswith("//"):
            href = "https:" + href
        elif href.startswith("/"):
            href = "https://zakupki.gov.ru" + href
        if "zakupki.gov.ru" not in href:
            continue
        href = href.split("#", 1)[0]
        um = _UID_RE.search(href)
        dedupe = um.group(1).upper() if um else href
        if um:
            if dedupe in seen_uid:
                continue
            seen_uid.add(dedupe)
        else:
            if href in seen_url:
                continue
            seen_url.add(href)
        title = (a.get("title") or "").strip() or ""
        label = (a.get_text(" ", strip=True) or title or "document")[:500]
        out.append({"url": href, "title": title, "label": label, "uid": um.group(1).upper() if um else ""})
    return out


def _guess_mime(filename: str, content_type: str | None) -> str:
    low = (filename or "").lower()
    if low.endswith(".pdf"):
        return "application/pdf"
    if low.endswith(".zip"):
        return "application/zip"
    if low.endswith(".docx"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if low.endswith(".doc"):
        return "application/msword"
    if low.endswith(".xlsx"):
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if low.endswith(".xls"):
        return "application/vnd.ms-excel"
    if low.endswith(".rar"):
        return "application/vnd.rar"
    if content_type and "/" in content_type and "octet-stream" not in content_type:
        return content_type.split(";", 1)[0].strip()
    return "application/octet-stream"


async def import_zakupki_public_documents(
    db: AsyncSession,
    *,
    tender_id: uuid.UUID,
    documents_page_url: str,
    user: dict[str, Any],
) -> dict[str, Any]:
    """Download public filestore files and attach to the tender (MinIO + ``documents`` rows).

    Args:
        db: DB session (caller commits).
        tender_id: Created tender id.
        documents_page_url: ``.../view/documents.html?regNumber=...``.
        user: Actor dict with ``id`` (UUID) for ``uploaded_by``.

    Returns:
        Summary dict: ``imported`` (filenames), ``imported_document_ids`` (UUID strings),
        ``skipped``, ``errors``.
    """
    settings = get_settings()
    max_files = settings.tender_zakupki_import_max_files
    max_bytes = settings.tender_zakupki_import_max_bytes_per_file

    imported: list[str] = []
    imported_ids: list[str] = []
    errors: list[str] = []
    try:
        raw, status, _final, ctype = await tender_http_get(documents_page_url)
    except Exception as exc:
        logger.warning("documents page fetch failed: %s", exc)
        return {"imported": [], "imported_document_ids": [], "skipped": 0, "errors": [str(exc)]}

    if status >= 400:
        return {"imported": [], "imported_document_ids": [], "skipped": 0, "errors": [f"HTTP {status}"]}

    html = raw.decode("utf-8", errors="replace")
    links = extract_zakupki_filestore_links(html)
    if not links:
        return {"imported": [], "imported_document_ids": [], "skipped": 0, "errors": []}

    svc = DocumentService()
    skipped = 0
    for item in links[:max_files]:
        url = item["url"]
        try:
            fraw, fst, _fu, fctype = await tender_http_get(url)
        except Exception as exc:
            errors.append(f"{url}: {exc!s}")
            continue
        if fst >= 400:
            skipped += 1
            continue
        if len(fraw) > max_bytes:
            skipped += 1
            errors.append(f"{url}: file too large ({len(fraw)} bytes, max {max_bytes})")
            continue
        if not fraw:
            skipped += 1
            continue
        head = fraw[: min(400, len(fraw))].lower()
        if head.startswith(b"<!doctype") or head.startswith(b"<html"):
            skipped += 1
            continue
        base_name = (item.get("title") or item.get("label") or "file").replace("/", "_")[:180]
        if not any(
            base_name.lower().endswith(x) for x in (".pdf", ".zip", ".doc", ".docx", ".xlsx", ".xls", ".rar")
        ):
            if "pdf" in (fctype or "").lower():
                base_name = base_name + ".pdf"
            elif "zip" in (fctype or "").lower():
                base_name = base_name + ".zip"
            elif "word" in (fctype or "").lower() or "officedocument" in (fctype or "").lower():
                base_name = base_name + ".docx"
            elif "spreadsheet" in (fctype or "").lower() or "excel" in (fctype or "").lower():
                base_name = base_name + ".xlsx"
        mime = _guess_mime(base_name, fctype)
        bio = io.BytesIO(fraw)
        lbl = item.get("label")
        extra = {
            "source": "zakupki_eis",
            "zakupki_file_url": url,
            "zakupki_uid": item.get("uid") or None,
        }
        try:
            doc = await svc.upload_file(
                db,
                bio,
                task_id=None,
                doc_type="tender_notice",
                label=(lbl[:200] if lbl else None),
                user=user,
                filename=base_name,
                mime_type=mime,
                tender_id=tender_id,
                extra_data=extra,
            )
            imported.append(base_name)
            imported_ids.append(str(doc.id))
        except Exception as exc:
            errors.append(f"{base_name}: {exc!s}")
            logger.warning("document upload failed for tender %s: %s", tender_id, exc)

    return {
        "imported": imported,
        "imported_document_ids": imported_ids,
        "skipped": skipped,
        "errors": errors,
    }
