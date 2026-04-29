"""MCP tools: unified Excel import for clients and warehouse (AI assistant)."""

from __future__ import annotations

import base64
import binascii
from pathlib import Path

from app.core.database import async_session_factory
from app.core.destructive_confirm import is_destructive_action_confirmed
from app.core.exceptions import ValidationError
from app.mcp.actor_context import resolve_mcp_actor_users_table_id
from app.mcp.server import mcp
from app.services import company_service
from app.services.excel_unified_import import import_excel_workbook

_MAX_BYTES = 6 * 1024 * 1024


@mcp.tool()
async def import_excel_workbook_base64(
    file_base64: str | None = None,
    filename: str = "upload.xlsx",
    file_path: str | None = None,
    use_ai_mapping: bool = False,
    __confirm: str | None = None,
) -> dict:
    """Import clients and/or warehouse items from an XLSX file (base64-encoded).

    Typical «База клиентов» sheets (Russian headers: наименование, контакты, оборудование)
    create Client rows. Sheets with SKU/артикул + количество update WarehouseItem stock.

    Args:
        file_base64: XLSX file content encoded as base64 (max ~6 MB).
        filename: Original name (for logs only).
        file_path: Optional absolute/relative path to local .xlsx file (fallback when attachment was not uploaded).
        use_ai_mapping: Reserved for future AI column mapping.
        __confirm: Explicit confirmation (e.g. \"yes\", \"подтверждаю\", \"да\") for bulk import safety.

    Returns:
        Counts per domain and per-sheet summary; lists errors (truncated).
    """
    _ = filename
    if not is_destructive_action_confirmed(__confirm):
        return {
            "ok": False,
            "code": "CONFIRM_REQUIRED",
            "message": "Bulk import requires explicit __confirm (e.g. 'yes' or 'подтверждаю').",
        }

    raw = (file_base64 or "").strip()
    data: bytes | None = None
    if raw:
        try:
            data = base64.b64decode(raw, validate=True)
        except binascii.Error as exc:
            raise ValidationError("file_base64", "Invalid base64") from exc
    else:
        fp = (file_path or "").strip()
        if fp:
            try:
                p = Path(fp).expanduser()
                data = p.read_bytes()
                if not filename or filename == "upload.xlsx":
                    filename = p.name
            except OSError as exc:
                raise ValidationError("file_path", f"Cannot read file: {exc}") from exc
        else:
            return {
                "ok": False,
                "code": "FILE_CONTENT_REQUIRED",
                "message": (
                    "Missing Excel file content. Attach an .xlsx file, or pass file_path "
                    "(e.g. C:\\projects\\SPECSTROY\\Клиенты__ВСЕ.xlsx), and call again."
                ),
            }

    if data is None:
        raise ValidationError("file_base64", "Unable to resolve file content")

    if len(data) > _MAX_BYTES:
        raise ValidationError("file", f"File too large (max {_MAX_BYTES} bytes)")

    if len(data) < 64:
        raise ValidationError("file", "File too small to be a valid XLSX")

    async with async_session_factory() as session:
        uid = await resolve_mcp_actor_users_table_id(session)
        company_id = await company_service.get_default_or_first_company_id(session, uid)

        result = await import_excel_workbook(
            session,
            company_id=company_id,
            raw_bytes=data,
            use_ai_hint=bool(use_ai_mapping),
        )
        await session.commit()

    return {
        "ok": True,
        **result.model_dump(mode="json"),
    }
