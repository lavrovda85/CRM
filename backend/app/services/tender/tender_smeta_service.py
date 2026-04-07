"""Background tender smeta (estimate) calculation from bill of works.

Combines optional external pricing context (see ``fgis_cs_client``) with a structured
LLM pass to produce indicative costs, margin band, and suggested bid floor for trades.
Results are stored under ``tender_analysis["smeta_calculation"]`` without overwriting
document-analysis fields under the top-level ``status`` used by ``tender_analysis_service``.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.models.tender import Tender
from app.prompts.tender_smeta_json import TENDER_SMETA_JSON_INSTRUCTION
from app.services.fgis_cs_client import fetch_fgis_external_context
from app.services.openai_client import create_async_openai_client
from app.services.tender.tender_smeta_reconcile import reconcile_smeta_llm_output

logger = logging.getLogger(__name__)

_MAX_ROWS = 80
_MAX_PROMPT_CHARS = 48_000


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _merge_smeta(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = dict(base) if base else {}
    sm = dict(out.get("smeta_calculation") or {})
    sm.update(patch)
    out["smeta_calculation"] = sm
    return out


async def _call_openai_smeta(
    tender_title: str,
    bill_rows: list[dict[str, Any]],
    external_context: str,
) -> dict[str, Any]:
    settings = get_settings()
    key = (settings.openai_api_key or "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    client = create_async_openai_client(settings)
    bill_blob = json.dumps(bill_rows, ensure_ascii=False, indent=2)[:_MAX_PROMPT_CHARS]
    user_blob = (
        f"Тендер: {tender_title}\n\n"
        f"Ведомость работ (до {_MAX_ROWS} строк):\n{bill_blob}\n\n"
        f"Внешний контекст цен/индексов (может быть пуст):\n{external_context or '(пусто)'}\n"
    )
    resp = await client.chat.completions.create(
        model=settings.openai_model,
        temperature=0.15,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": TENDER_SMETA_JSON_INSTRUCTION},
            {"role": "user", "content": user_blob[:_MAX_PROMPT_CHARS]},
        ],
        timeout=120.0,
    )
    raw = (resp.choices[0].message.content or "").strip()
    return json.loads(raw)


async def enqueue_smeta_pending(session: AsyncSession, tender_id: uuid.UUID) -> None:
    """Mark smeta job as queued before Celery picks it up."""
    t = await session.get(Tender, tender_id)
    if not t:
        return
    cur = dict(t.tender_analysis) if t.tender_analysis else {}
    sm = dict(cur.get("smeta_calculation") or {})
    sm.update(
        {
            "status": "pending",
            "stage_label": "queued",
            "updated_at": _now_iso(),
        }
    )
    cur["smeta_calculation"] = sm
    t.tender_analysis = cur
    await session.flush()


async def run_tender_smeta_job(tender_id: uuid.UUID) -> None:
    """Load bill of works, optional FGIS context, run LLM, persist ``smeta_calculation``."""
    async with async_session_factory() as session:
        result = await session.execute(select(Tender).where(Tender.id == tender_id))
        tender = result.scalar_one_or_none()
        if not tender:
            logger.warning("tender_smeta: tender %s not found", tender_id)
            return

        base = dict(tender.tender_analysis) if tender.tender_analysis else {}
        tender.tender_analysis = _merge_smeta(
            base,
            {
                "status": "running",
                "stage_label": "computing",
                "updated_at": _now_iso(),
            },
        )
        await session.commit()

        result = await session.execute(select(Tender).where(Tender.id == tender_id))
        tender = result.scalar_one_or_none()
        if not tender:
            return

        ta = dict(tender.tender_analysis) if tender.tender_analysis else {}
        rows = ta.get("bill_of_works") or []
        if not isinstance(rows, list) or not rows:
            tender.tender_analysis = _merge_smeta(
                ta,
                {
                    "status": "completed",
                    "stage_label": "no_bill",
                    "error": "no_bill_of_works",
                    "disclaimer_ru": "Нет ведомости работ — заполните или дождитесь анализа документов.",
                    "updated_at": _now_iso(),
                    "completed_at": _now_iso(),
                },
            )
            await session.commit()
            return

        slim: list[dict[str, Any]] = []
        for r in rows[:_MAX_ROWS]:
            if not isinstance(r, dict):
                continue
            slim.append(
                {
                    "position": r.get("position"),
                    "name": r.get("name"),
                    "unit": r.get("unit"),
                    "quantity": r.get("quantity"),
                    "remarks": r.get("remarks"),
                }
            )

        ext_text, diag = await fetch_fgis_external_context()

        try:
            parsed = await _call_openai_smeta(tender.title, slim, ext_text)
        except Exception as exc:
            logger.exception("tender_smeta LLM failed for %s", tender_id)
            tender2 = await session.get(Tender, tender_id)
            if tender2:
                ta2 = dict(tender2.tender_analysis) if tender2.tender_analysis else {}
                tender2.tender_analysis = _merge_smeta(
                    ta2,
                    {
                        "status": "failed",
                        "stage_label": "error",
                        "error": str(exc)[:2000],
                        "fgis_diagnostics": diag,
                        "updated_at": _now_iso(),
                    },
                )
                await session.commit()
            return

        tender3 = await session.get(Tender, tender_id)
        if tender3:
            ta3 = dict(tender3.tender_analysis) if tender3.tender_analysis else {}
            out = dict(parsed) if isinstance(parsed, dict) else {}
            out = reconcile_smeta_llm_output(out)
            out["status"] = "completed"
            out["stage_label"] = "done"
            out["fgis_diagnostics"] = diag
            out["updated_at"] = _now_iso()
            out["completed_at"] = _now_iso()
            tender3.tender_analysis = _merge_smeta(ta3, out)
            await session.commit()
