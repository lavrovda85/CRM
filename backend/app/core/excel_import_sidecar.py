"""Bind user-uploaded XLSX bytes to ``import_excel_workbook_base64`` tool calls.

The assistant receives spreadsheet *text* in the chat payload (possibly truncated for
token limits). The model cannot reconstruct valid workbook base64 from that text.
When the same HTTP request included ``.xlsx`` uploads, we inject ``file_base64`` here.
"""

from __future__ import annotations

import base64
from typing import Any


def merge_uploaded_xlsx_into_import_arguments(
    tool_name: str,
    arguments: dict[str, Any] | None,
    uploads_by_filename: dict[str, bytes] | None,
) -> dict[str, Any]:
    """If this is an Excel import tool call and uploads exist, set ``file_base64`` from bytes.

    Matching order: exact filename, case-insensitive filename, single-upload fallback,
    then basename / suffix heuristics.

    Args:
        tool_name: MCP tool name from ``invoke_crm_tool``.
        arguments: Raw ``arguments`` object from the model (may be empty).
        uploads_by_filename: Original filename -> full ``.xlsx`` file bytes from multipart.

    Returns:
        A shallow-copied arguments dict (possibly unchanged).
    """
    if tool_name != "import_excel_workbook_base64" or not uploads_by_filename:
        return dict(arguments or {})
    out = dict(arguments or {})
    fn = str(out.get("filename") or "").strip()
    raw = _resolve_upload_bytes(fn, uploads_by_filename)
    if raw is not None:
        out["file_base64"] = base64.standard_b64encode(raw).decode("ascii")
    return out


def _resolve_upload_bytes(filename: str, uploads: dict[str, bytes]) -> bytes | None:
    if not uploads:
        return None
    if len(uploads) == 1:
        return next(iter(uploads.values()))
    fn = (filename or "").strip()
    if fn and fn in uploads:
        return uploads[fn]
    lower = {k.lower(): v for k, v in uploads.items()}
    if fn and fn.lower() in lower:
        return lower[fn.lower()]
    want = fn.lower()
    if not want:
        return None
    for name, data in uploads.items():
        base = name.rsplit("/", 1)[-1].lower()
        if base == want or base.endswith(want) or want.endswith(base):
            return data
    return None
