"""Tests for XLSX upload bytes merged into import tool arguments."""

from __future__ import annotations

import base64

from app.core.excel_import_sidecar import merge_uploaded_xlsx_into_import_arguments


def test_merge_ignores_non_import_tool() -> None:
    out = merge_uploaded_xlsx_into_import_arguments(
        "list_tasks",
        {"q": "x"},
        {"a.xlsx": b"fake"},
    )
    assert out == {"q": "x"}


def test_single_upload_sets_base64() -> None:
    raw = b"PK\x03\x04hello"
    out = merge_uploaded_xlsx_into_import_arguments(
        "import_excel_workbook_base64",
        {"filename": "clients.xlsx", "__confirm": "yes"},
        {"clients.xlsx": raw},
    )
    assert base64.standard_b64decode(out["file_base64"]) == raw


def test_single_upload_without_filename_uses_only_file() -> None:
    raw = b"PK\x03\x04solo"
    out = merge_uploaded_xlsx_into_import_arguments(
        "import_excel_workbook_base64",
        {"__confirm": "да"},
        {"big.xlsx": raw},
    )
    assert base64.standard_b64decode(out["file_base64"]) == raw


def test_multiple_uploads_match_filename() -> None:
    a, b = b"aaa", b"bbb"
    uploads = {"a.xlsx": a, "b.xlsx": b}
    out = merge_uploaded_xlsx_into_import_arguments(
        "import_excel_workbook_base64",
        {"filename": "b.xlsx", "__confirm": "yes"},
        uploads,
    )
    assert base64.standard_b64decode(out["file_base64"]) == b


def test_multiple_uploads_case_insensitive() -> None:
    raw = b"ZZZ"
    out = merge_uploaded_xlsx_into_import_arguments(
        "import_excel_workbook_base64",
        {"filename": "DATA.XLSX", "__confirm": "yes"},
        {"data.xlsx": raw},
    )
    assert base64.standard_b64decode(out["file_base64"]) == raw


def test_multiple_no_match_leaves_args_without_injection() -> None:
    out = merge_uploaded_xlsx_into_import_arguments(
        "import_excel_workbook_base64",
        {"filename": "missing.xlsx", "file_base64": "abcd", "__confirm": "yes"},
        {"other.xlsx": b"x", "another.xlsx": b"y"},
    )
    assert out["file_base64"] == "abcd"
