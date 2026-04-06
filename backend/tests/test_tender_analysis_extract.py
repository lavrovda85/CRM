"""Tests for archive-aware document text expansion for tender analysis."""

from __future__ import annotations

import io
import zipfile

import openpyxl

from app.services.tender.tender_analysis_extract import expand_document_for_analysis


def _xlsx_bytes_with_sheet(title: str, cell_a1: str) -> bytes:
    buf = io.BytesIO()
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = title
    ws["A1"] = cell_a1
    wb.save(buf)
    return buf.getvalue()


def test_expand_zip_with_inner_xlsx_extracts_text() -> None:
    xlsx = _xlsx_bytes_with_sheet("Ведомость", "Кирпич М100")
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("docs/estimate.xlsx", xlsx)
    data = zbuf.getvalue()

    text, stats = expand_document_for_analysis("tender_docs.zip", "application/zip", data)

    assert stats["from_archive"] is True
    assert stats["inner_files"] >= 1
    assert "Кирпич" in text
    assert "Ведомость" in text or "estimate" in text.lower()


def test_expand_plain_pdf_not_marked_as_archive() -> None:
    # Minimal valid empty PDF structure is complex; use tiny xlsx as "leaf" path instead.
    xlsx = _xlsx_bytes_with_sheet("S", "x")
    text, stats = expand_document_for_analysis("a.xlsx", "application/vnd...", xlsx)
    assert stats["from_archive"] is False
    assert "x" in text
