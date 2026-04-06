"""Background tender document analysis: risks, profitability, bill of works (ведомость).

Aggregates text from tender-linked documents in MinIO, then calls OpenAI for structured output.
Stored in ``Tender.tender_analysis`` (JSONB).
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.models.document import Document
from app.models.tender import Tender
from app.prompts.tender_analysis_json import TENDER_ANALYSIS_JSON_INSTRUCTION
from app.services.document_service import DocumentService
from .tender_analysis_bill_heuristic import (
    extract_bill_of_works_heuristic,
    merge_bill_rows_llm_and_heuristic,
)
from .tender_analysis_extract import expand_document_for_analysis

logger = logging.getLogger(__name__)

_MAX_TEXT = 120_000
# Avoid one huge PDF consuming the whole budget so later files (with ГОСТ / гарантия) never reach the model.
_MAX_TEXT_PER_DOCUMENT = 28_000
# Below this, LLM tends to paraphrase field rubrics instead of analyzing real content.
_MIN_CHARS_FOR_LLM = 800


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _merge_analysis(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base) if base else {}
    out.update(patch)
    return out


def _extraction_skip_note(filename: str, meta: dict[str, Any] | None = None) -> str:
    """Machine-readable reason when no text was extracted (for ``extraction_report``)."""
    meta = meta or {}
    low = (filename or "").lower()
    if low.endswith((".zip", ".rar", ".7z")):
        if meta.get("rar_tool_missing"):
            return "archive_rar_tool_missing"
        if meta.get("py7zr_missing"):
            return "archive_7z_tool_missing"
        if meta.get("from_archive"):
            ms = int(meta.get("archive_members_seen") or 0)
            inner = int(meta.get("inner_files") or 0)
            if ms == 0:
                return "archive_empty_or_unreadable"
            if inner == 0:
                return "archive_no_supported_text"
        return "archive_not_unpacked"
    if low.endswith(".doc") and not low.endswith(".docx"):
        return "legacy_doc_not_supported_use_docx"
    if low.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".tif", ".tiff")):
        return "image_no_ocr"
    if low.endswith((".html", ".htm")):
        return "html_not_extracted"
    return "no_text_layer_or_empty_extract"


def _assemble_capped_document_text(chunks: list[str], *, max_total: int, max_per_doc: int) -> str:
    """Join per-file chunks so each file contributes up to ``max_per_doc`` chars before global ``max_total``."""
    parts: list[str] = []
    used = 0
    for ch in chunks:
        if used >= max_total:
            break
        room = max_total - used
        cap = min(max_per_doc, room)
        if len(ch) <= cap:
            parts.append(ch)
            used += len(ch)
        else:
            parts.append(
                ch[:cap]
                + "\n\n[… фрагмент обрезан по лимиту на один файл; остальные файлы ниже тоже участвуют в анализе …]"
            )
            used += cap
    return "\n\n".join(parts)


async def _call_openai(combined_text: str, tender_title: str) -> dict[str, Any]:
    settings = get_settings()
    key = (settings.openai_api_key or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    client = AsyncOpenAI(api_key=key)
    user_blob = (
        f"Название тендера: {tender_title}\n\n"
        "Ниже — извлечённый текст из прикреплённых файлов (каждый файл может быть сокращён по объёму; "
        "несколько файлов объединены). Внимательно просмотри все блоки «### Файл: …» и таблицы с табуляцией. "
        "Ведомости и сметы часто идут таблицами (строки с несколькими колонками через таб) — перенеси их в bill_of_works. "
        "Если в тексте есть ГОСТ, гарантия, сроки, штрафы — обязательно отрази это.\n\n"
        f"--- Всего символов: {len(combined_text.strip())} ---\n\n{combined_text}"
    )
    resp = await client.chat.completions.create(
        model=settings.openai_model,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": TENDER_ANALYSIS_JSON_INSTRUCTION},
            {"role": "user", "content": user_blob[:_MAX_TEXT]},
        ],
        timeout=120.0,
    )
    raw = (resp.choices[0].message.content or "").strip()
    return json.loads(raw)


async def run_tender_analysis_job(tender_id: uuid.UUID) -> None:
    """Load tender documents, extract text, run LLM analysis, persist ``tender_analysis``."""
    async with async_session_factory() as session:
        result = await session.execute(select(Tender).where(Tender.id == tender_id))
        tender = result.scalar_one_or_none()
        if not tender:
            logger.warning("tender_analysis: tender %s not found", tender_id)
            return

        base: dict[str, Any] = dict(tender.tender_analysis) if tender.tender_analysis else {}
        tender.tender_analysis = _merge_analysis(
            base,
            {
                "status": "running",
                "stage": 1,
                "stage_label": "collecting_text",
                "updated_at": _now_iso(),
            },
        )
        await session.commit()

        result = await session.execute(
            select(Tender)
            .options(selectinload(Tender.documents))
            .where(Tender.id == tender_id)
        )
        tender = result.scalar_one_or_none()
        if not tender:
            return
        def _doc_bill_priority(doc: Document) -> int:
            low = (doc.filename or "").lower()
            keys = (
                "ведомость",
                "ведом",
                "объём",
                "объем",
                "смет",
                "локальн",
                "кс-2",
                "кс2",
                "м-29",
                "м29",
                "позиц",
                "объем работ",
                "объём работ",
            )
            return 0 if any(k in low for k in keys) else 1

        docs_sorted = sorted(tender.documents, key=lambda d: (_doc_bill_priority(d), d.created_at))
        svc = DocumentService()
        chunks: list[str] = []
        doc_ids: list[str] = []
        extraction_report: list[dict[str, Any]] = []
        for doc in docs_sorted:
            row: dict[str, Any] = {
                "document_id": str(doc.id),
                "filename": doc.filename,
                "mime_type": doc.mime_type,
                "chars_extracted": 0,
                "included_in_llm_input": False,
                "skip_note": None,
                "from_archive": None,
                "archive_inner_files": None,
                "archive_members_seen": None,
            }
            try:
                raw = svc.get_object_bytes(doc.storage_path)
            except Exception as exc:
                logger.warning("skip doc %s: %s", doc.id, exc)
                row["skip_note"] = f"storage_read_error:{type(exc).__name__}"
                extraction_report.append(row)
                continue
            text, xmeta = expand_document_for_analysis(doc.filename, doc.mime_type, raw)
            stripped = text.strip()
            row["chars_extracted"] = len(stripped)
            if xmeta.get("from_archive"):
                row["from_archive"] = True
                row["archive_inner_files"] = xmeta.get("inner_files")
                row["archive_members_seen"] = xmeta.get("archive_members_seen")
            if not stripped:
                row["skip_note"] = _extraction_skip_note(doc.filename, xmeta)
                extraction_report.append(row)
                continue
            row["included_in_llm_input"] = True
            extraction_report.append(row)
            chunks.append(f"### Файл: {doc.filename}\n{text}")
            doc_ids.append(str(doc.id))

        combined = _assemble_capped_document_text(
            chunks,
            max_total=_MAX_TEXT,
            max_per_doc=_MAX_TEXT_PER_DOCUMENT,
        )
        combined_stripped = combined.strip()

        tender2 = await session.get(Tender, tender_id)
        if not tender2:
            return
        tender2.tender_analysis = _merge_analysis(
            dict(tender2.tender_analysis),
            {
                "stage": 2,
                "stage_label": "llm_analysis",
                "source_document_ids": doc_ids,
                "documents_total": len(docs_sorted),
                "documents_with_extracted_text": len(chunks),
                "document_extraction_report": extraction_report,
                "text_chars_used": len(combined_stripped),
                "max_text_per_document": _MAX_TEXT_PER_DOCUMENT,
                "updated_at": _now_iso(),
            },
        )
        await session.commit()

        if not combined_stripped:
            tender3 = await session.get(Tender, tender_id)
            if tender3:
                tender3.tender_analysis = _merge_analysis(
                    dict(tender3.tender_analysis),
                    {
                        "status": "completed",
                        "stage": 3,
                        "stage_label": "done_no_text",
                        "analysis_note": "no_extractable_text",
                        "pitfalls_and_risks": "_Нет извлекаемого текста из прикреплённых файлов (PDF, DOCX, XLSX; ZIP/7Z/RAR распаковываются, внутри — те же форматы)._",
                        "profitability_assessment": "_Недостаточно данных для оценки._",
                        "participation_recommendation": "caution",
                        "bill_of_works": [],
                        "bill_of_works_notes": "Ведомость не извлечена: нет текстового содержимого (в т.ч. из архивов — только поддерживаемые вложения).",
                        "bill_of_works_confidence": "low",
                        "completed_at": _now_iso(),
                        "updated_at": _now_iso(),
                    },
                )
                await session.commit()
            return

        if len(combined_stripped) < _MIN_CHARS_FOR_LLM:
            tender_low = await session.get(Tender, tender_id)
            if tender_low:
                n = len(combined_stripped)
                tender_low.tender_analysis = _merge_analysis(
                    dict(tender_low.tender_analysis),
                    {
                        "status": "completed",
                        "stage": 3,
                        "stage_label": "done_insufficient_text",
                        "analysis_note": "text_below_minimum_for_llm",
                        "pitfalls_and_risks": (
                            f"_Из документов извлечено только **{n}** значимых символов "
                            f"(порог для автоматического разбора — {_MIN_CHARS_FOR_LLM}). "
                            "Загрузите полный комплект PDF/DOCX/XLSX с текстовым слоем или проверьте, что файлы не только сканы без OCR._"
                        ),
                        "profitability_assessment": (
                            "_Недостаточно текста для оценки рентабельности. "
                            "После загрузки читаемых документов нажмите «Повторить анализ»._"
                        ),
                        "participation_recommendation": "caution",
                        "bill_of_works": [],
                        "bill_of_works_notes": f"Недостаточно табличных/текстовых данных для ведомости ({n} символов извлечено).",
                        "bill_of_works_confidence": "low",
                        "completed_at": _now_iso(),
                        "updated_at": _now_iso(),
                    },
                )
                await session.commit()
            return

        try:
            parsed = await _call_openai(combined, tender.title)
        except Exception as exc:
            logger.exception("tender_analysis LLM failed for %s", tender_id)
            tender_e = await session.get(Tender, tender_id)
            if tender_e:
                tender_e.tender_analysis = _merge_analysis(
                    dict(tender_e.tender_analysis),
                    {
                        "status": "failed",
                        "stage": 3,
                        "stage_label": "error",
                        "error": str(exc)[:2000],
                        "updated_at": _now_iso(),
                    },
                )
                await session.commit()
            return

        def _get(key: str, default: Any = "") -> Any:
            v = parsed.get(key, default)
            return v if v is not None else default

        raw_bill = _get("bill_of_works", [])
        raw_bill_list: list[Any] = raw_bill if isinstance(raw_bill, list) else []

        heur_rows, heur_meta = extract_bill_of_works_heuristic(combined_stripped)
        merged_bill = merge_bill_rows_llm_and_heuristic(raw_bill_list, heur_rows)

        bill_notes = str(_get("bill_of_works_notes", ""))
        bill_confidence = str(_get("bill_of_works_confidence", "medium"))
        if merged_bill is heur_rows and heur_rows:
            extra = f"Позиции извлечены из табличных строк в тексте ({heur_meta})."
            bill_notes = f"{bill_notes} {extra}".strip() if bill_notes else extra
            bill_confidence = "medium" if len(heur_rows) >= 5 else "low"

        out = {
            "status": "completed",
            "stage": 3,
            "stage_label": "done",
            "pitfalls_and_risks": str(_get("pitfalls_and_risks", "")),
            "profitability_assessment": str(_get("profitability_assessment", "")),
            "participation_recommendation": str(_get("participation_recommendation", "caution")),
            "bill_of_works": merged_bill,
            "bill_of_works_notes": bill_notes,
            "bill_of_works_confidence": bill_confidence,
            "completed_at": _now_iso(),
            "updated_at": _now_iso(),
        }

        tender_f = await session.get(Tender, tender_id)
        if tender_f:
            tender_f.tender_analysis = _merge_analysis(dict(tender_f.tender_analysis), out)
            await session.commit()


async def enqueue_analysis_reset_pending(session: AsyncSession, tender_id: uuid.UUID) -> None:
    """Set analysis to pending before queueing a background job."""
    t = await session.get(Tender, tender_id)
    if not t:
        return
    cur = dict(t.tender_analysis) if t.tender_analysis else {}
    cur.update(
        {
            "status": "pending",
            "stage": 0,
            "stage_label": "queued",
            "updated_at": _now_iso(),
        }
    )
    t.tender_analysis = cur
    await session.flush()
