"""Unpack archives (ZIP, 7Z, RAR) and extract leaf text for tender AI analysis.

Estimates and local estimate sheets (сметы) are often shipped inside archives; this module
recursively expands supported archives with depth/member/size limits to mitigate zip-slip
and zip-bomb patterns.
"""

from __future__ import annotations

import io
import logging
import zipfile
from typing import Any

import openpyxl
from docx import Document as DocxDocument
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader

logger = logging.getLogger(__name__)

MAX_ARCHIVE_DEPTH = 3
MAX_ARCHIVE_MEMBERS = 200
MAX_MEMBER_UNCOMPRESSED = 96 * 1024 * 1024


def _safe_member_name(name: str) -> bool:
    """Reject path traversal and absolute paths inside archives."""
    n = name.replace("\\", "/").strip()
    if not n or n.endswith("/"):
        return False
    parts = [p for p in n.split("/") if p]
    for p in parts:
        if p == ".." or p.startswith("/"):
            return False
    return True


def _is_archive_filename(filename: str) -> bool:
    low = (filename or "").lower()
    return low.endswith((".zip", ".7z", ".rar"))


def _docx_text_with_tables(doc: DocxDocument) -> str:
    """Paragraphs and table rows in document order (ведомости are often in Word tables)."""
    lines: list[str] = []
    for el in doc.element.body:
        if el.tag == qn("w:p"):
            p = Paragraph(el, doc)
            if p.text.strip():
                lines.append(p.text)
        elif el.tag == qn("w:tbl"):
            tbl = Table(el, doc)
            for row in tbl.rows:
                cells = [c.text.strip() for c in row.cells]
                if any(cells):
                    lines.append("\t".join(cells))
    return "\n".join(lines)


def _extract_leaf_text(filename: str, mime_type: str | None, data: bytes) -> str:
    """Plain text from PDF, DOCX, or XLSX/XLS only (single file)."""
    low = (filename or "").lower()
    mt = (mime_type or "").lower()
    if not data:
        return ""
    try:
        if low.endswith(".pdf") or "pdf" in mt:
            reader = PdfReader(io.BytesIO(data))
            parts: list[str] = []
            for page in reader.pages[:200]:
                t = page.extract_text() or ""
                if t.strip():
                    parts.append(t)
            return "\n".join(parts)

        if low.endswith(".docx") or "wordprocessingml" in mt or "officedocument.wordprocessingml" in mt:
            d = DocxDocument(io.BytesIO(data))
            return _docx_text_with_tables(d)

        if low.endswith(".xls") and not low.endswith(".xlsx"):
            try:
                import xlrd
            except ImportError:
                logger.info("xlrd not installed; legacy .xls skipped")
                return ""
            book = xlrd.open_workbook(file_contents=data)
            lines: list[str] = []
            for sheet in book.sheets()[:5]:
                lines.append(f"## {sheet.name}")
                for row_idx in range(min(sheet.nrows, 800)):
                    row = sheet.row_values(row_idx)
                    cells = [str(c).strip() if c != "" else "" for c in row]
                    if any(x.strip() for x in cells):
                        lines.append("\t".join(cells))
            return "\n".join(lines)

        if low.endswith(".xlsx") or "spreadsheetml" in mt:
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            lines = []
            for sheet in wb.worksheets[:5]:
                lines.append(f"## {sheet.title}")
                for row in sheet.iter_rows(max_row=800, values_only=True):
                    cells = [str(c) if c is not None else "" for c in row]
                    if any(x.strip() for x in cells):
                        lines.append("\t".join(cells))
            return "\n".join(lines)
    except Exception as exc:
        logger.info("leaf extract failed for %s: %s", filename, exc)
        return ""
    return ""


def _unpack_zip_bytes(
    data: bytes,
    parent_label: str,
    depth: int,
    stats: dict[str, Any],
) -> str:
    out: list[str] = []
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        logger.info("bad zip %s: %s", parent_label, exc)
        return ""

    members_seen = 0
    for info in zf.infolist():
        if members_seen >= MAX_ARCHIVE_MEMBERS:
            out.append(f"[… пропуск: лимит {MAX_ARCHIVE_MEMBERS} вложений в архиве …]")
            break
        if info.is_dir():
            continue
        name = info.filename
        if not _safe_member_name(name):
            continue
        if info.file_size > MAX_MEMBER_UNCOMPRESSED:
            continue
        try:
            raw = zf.read(name)
        except Exception as exc:
            logger.info("zip read %s/%s: %s", parent_label, name, exc)
            continue
        members_seen += 1
        stats["archive_members_seen"] = stats.get("archive_members_seen", 0) + 1
        rel = f"{parent_label}/{name}"
        low = name.lower()
        if low.endswith(".zip") and depth < MAX_ARCHIVE_DEPTH:
            inner = _unpack_zip_bytes(raw, rel, depth + 1, stats)
            if inner.strip():
                out.append(f"### Вложенный архив: {rel}\n{inner}")
        elif low.endswith(".7z") and depth < MAX_ARCHIVE_DEPTH:
            inner = _unpack_7z_bytes(raw, rel, depth + 1, stats)
            if inner.strip():
                out.append(f"### Вложенный архив: {rel}\n{inner}")
        elif low.endswith(".rar") and depth < MAX_ARCHIVE_DEPTH:
            inner = _unpack_rar_bytes(raw, rel, depth + 1, stats)
            if inner.strip():
                out.append(f"### Вложенный архив: {rel}\n{inner}")
        else:
            leaf = _extract_leaf_text(name, None, raw)
            if leaf.strip():
                stats["inner_files"] = stats.get("inner_files", 0) + 1
                out.append(f"### {rel}\n{leaf}")

    return "\n\n".join(out)


def _unpack_7z_bytes(
    data: bytes,
    parent_label: str,
    depth: int,
    stats: dict[str, Any],
) -> str:
    try:
        import py7zr
    except ImportError:
        logger.warning("py7zr not installed; 7z extraction skipped")
        stats["py7zr_missing"] = True
        return ""

    out: list[str] = []
    try:
        with py7zr.SevenZipFile(io.BytesIO(data), mode="r") as archive:
            names = archive.getnames()
            for name in names:
                if stats.get("archive_members_seen", 0) >= MAX_ARCHIVE_MEMBERS:
                    out.append(f"[… пропуск: лимит {MAX_ARCHIVE_MEMBERS} вложений …]")
                    break
                if name.endswith("/"):
                    continue
                if not _safe_member_name(name):
                    continue
                chunk = archive.read([name])
                if not chunk:
                    continue
                bio = chunk.get(name)
                if bio is None:
                    continue
                raw = bio.read() if hasattr(bio, "read") else bytes(bio)
                if len(raw) > MAX_MEMBER_UNCOMPRESSED:
                    continue
                stats["archive_members_seen"] = stats.get("archive_members_seen", 0) + 1
                rel = f"{parent_label}/{name}"
                low = name.lower()
                if low.endswith(".zip") and depth < MAX_ARCHIVE_DEPTH:
                    inner = _unpack_zip_bytes(raw, rel, depth + 1, stats)
                    if inner.strip():
                        out.append(f"### Вложенный архив: {rel}\n{inner}")
                elif low.endswith(".7z") and depth < MAX_ARCHIVE_DEPTH:
                    inner = _unpack_7z_bytes(raw, rel, depth + 1, stats)
                    if inner.strip():
                        out.append(f"### Вложенный архив: {rel}\n{inner}")
                elif low.endswith(".rar") and depth < MAX_ARCHIVE_DEPTH:
                    inner = _unpack_rar_bytes(raw, rel, depth + 1, stats)
                    if inner.strip():
                        out.append(f"### Вложенный архив: {rel}\n{inner}")
                else:
                    leaf = _extract_leaf_text(name, None, raw)
                    if leaf.strip():
                        stats["inner_files"] = stats.get("inner_files", 0) + 1
                        out.append(f"### {rel}\n{leaf}")
    except Exception as exc:
        logger.info("7z unpack failed %s: %s", parent_label, exc)
        return ""

    return "\n\n".join(out)


def _unpack_rar_bytes(
    data: bytes,
    parent_label: str,
    depth: int,
    stats: dict[str, Any],
) -> str:
    try:
        import rarfile
        import shutil

        for cmd in ("unrar", "unrar-free"):
            if shutil.which(cmd):
                rarfile.UNRAR_TOOL = cmd
                break
    except ImportError:
        return ""

    out: list[str] = []
    try:
        rf = rarfile.RarFile(io.BytesIO(data))
        for info in rf.infolist():
            if info.isdir():
                continue
            if stats.get("archive_members_seen", 0) >= MAX_ARCHIVE_MEMBERS:
                out.append(f"[… пропуск: лимит {MAX_ARCHIVE_MEMBERS} вложений …]")
                break
            name = info.filename
            if not _safe_member_name(name):
                continue
            if info.file_size > MAX_MEMBER_UNCOMPRESSED:
                continue
            raw = rf.read(name)
            stats["archive_members_seen"] = stats.get("archive_members_seen", 0) + 1
            rel = f"{parent_label}/{name}"
            low = name.lower()
            if low.endswith(".zip") and depth < MAX_ARCHIVE_DEPTH:
                inner = _unpack_zip_bytes(raw, rel, depth + 1, stats)
                if inner.strip():
                    out.append(f"### Вложенный архив: {rel}\n{inner}")
            elif low.endswith(".7z") and depth < MAX_ARCHIVE_DEPTH:
                inner = _unpack_7z_bytes(raw, rel, depth + 1, stats)
                if inner.strip():
                    out.append(f"### Вложенный архив: {rel}\n{inner}")
            elif low.endswith(".rar") and depth < MAX_ARCHIVE_DEPTH:
                inner = _unpack_rar_bytes(raw, rel, depth + 1, stats)
                if inner.strip():
                    out.append(f"### Вложенный архив: {rel}\n{inner}")
            else:
                leaf = _extract_leaf_text(name, None, raw)
                if leaf.strip():
                    stats["inner_files"] = stats.get("inner_files", 0) + 1
                    out.append(f"### {rel}\n{leaf}")
    except rarfile.RarCannotExec as exc:
        logger.info("rar unpack skipped (no unrar): %s", exc)
        stats["rar_tool_missing"] = True
        return ""
    except Exception as exc:
        logger.info("rar unpack failed %s: %s", parent_label, exc)
        return ""

    return "\n\n".join(out)


def expand_document_for_analysis(
    filename: str,
    mime_type: str | None,
    data: bytes,
) -> tuple[str, dict[str, Any]]:
    """Return combined text and stats. Archives are unpacked; leaves use PDF/DOCX/XLSX only.

    Returns:
        Tuple of (text, stats) where stats may include ``from_archive``, ``inner_files``,
        ``archive_members_seen``.
    """
    stats: dict[str, Any] = {"from_archive": False, "inner_files": 0, "archive_members_seen": 0}
    if not data:
        return "", stats

    if _is_archive_filename(filename):
        stats["from_archive"] = True
        low = (filename or "").lower()
        label = filename or "archive"
        if low.endswith(".zip"):
            text = _unpack_zip_bytes(data, label, 0, stats)
        elif low.endswith(".7z"):
            text = _unpack_7z_bytes(data, label, 0, stats)
        elif low.endswith(".rar"):
            text = _unpack_rar_bytes(data, label, 0, stats)
        else:
            text = ""
        if text.strip():
            return text, stats
        return "", stats

    return _extract_leaf_text(filename, mime_type, data), stats
