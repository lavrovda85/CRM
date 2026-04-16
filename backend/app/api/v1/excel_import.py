"""Unified Excel import API (clients + warehouse)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.company_context import ActiveCompanyContext, get_active_company
from app.core.dependencies import get_db
from app.core.security import CurrentUser, get_current_user
from app.schemas.excel_import import ExcelUnifiedImportResponse
from app.services.excel_unified_import import import_excel_workbook

router = APIRouter(prefix="/import")


@router.post("/excel", response_model=ExcelUnifiedImportResponse)
async def post_import_excel(
    file: UploadFile = File(...),
    use_ai_mapping: bool = Form(
        default=False,
        description="Reserved: future AI-assisted column mapping for exotic layouts.",
    ),
    db: AsyncSession = Depends(get_db),
    ctx: ActiveCompanyContext = Depends(get_active_company),
    _user: CurrentUser = Depends(get_current_user),
) -> ExcelUnifiedImportResponse:
    """Import clients and/or warehouse items from a multi-sheet XLSX workbook.

    Sheets are classified heuristically: Russian «база клиентов» layouts map to clients;
    sheets with SKU/quantity headers map to warehouse. Same file can mix both.
    """
    raw = await file.read()
    if not raw:
        return ExcelUnifiedImportResponse(errors=["Empty file"])
    return await import_excel_workbook(
        db,
        company_id=ctx.company_id,
        raw_bytes=raw,
        use_ai_hint=use_ai_mapping,
    )
