"""Schemas for unified Excel import (clients + warehouse)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SheetImportSummary(BaseModel):
    """Per-sheet import summary."""

    sheet_name: str
    kind: str = Field(description="clients | warehouse | skipped")
    rows_processed: int = 0
    message: str | None = None


class ExcelUnifiedImportResponse(BaseModel):
    """Result of POST /import/excel."""

    clients_created: int = 0
    clients_skipped: int = 0
    warehouse_created: int = 0
    warehouse_updated: int = 0
    warehouse_skipped: int = 0
    sheets: list[SheetImportSummary] = Field(default_factory=list)
    ai_mapping_used: bool = False
    errors: list[str] = Field(default_factory=list)
