"""Enrich tender search hits with fetched page text and optional AI summaries.

Adds ``summary`` (short Russian text) to each row so users can pick imports without
opening every link. Fetches up to ``tender_search_enrich_max_pages`` URLs in parallel;
optional OpenAI JSON batch summarization when ``OPENAI_API_KEY`` is set.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from openai import APIError

from app.core.config import Settings, get_settings
from app.services.openai_client import create_async_openai_client
from .tender_external_service import FetchedTenderPage, fetch_tender_page
from .tender_search_query import should_drop_for_exclusion_tokens
from .tender_zakupki_urls import (
    canonical_zakupki_notice_url,
    reg_number_from_zakupki_url,
    zakupki_reg_numbers_equivalent,
)

logger = logging.getLogger(__name__)

_MAX_BLOB_PER_ITEM = 6000
_MAX_OUTPUT_TOKENS = 2500


def _truncate_ru(text: str, max_len: int) -> str:
    """Collapse whitespace and truncate at a word boundary with an ellipsis."""
    t = " ".join((text or "").split())
    if len(t) <= max_len:
        return t
    cut = t[: max_len - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "…"


def _snippet_fallback(it: dict[str, str]) -> str:
    """Build a short line from search title/snippet when no page body is available."""
    title = (it.get("title") or "").strip()
    snippet = (it.get("snippet") or "").strip()
    blob = f"{title} {snippet}".strip()
    return _truncate_ru(blob, 420) or title or snippet or (it.get("url") or "")


def _heuristic_from_row(it: dict[str, str], row: dict[str, Any]) -> str:
    """Build a buyer-facing line from structured notice fields first, then page text."""
    subj = (row.get("notice_subject") or "").strip()
    cust = (row.get("notice_customer") or "").strip()
    nmck = (row.get("notice_nmck") or "").strip()
    dl = row.get("application_deadline_utc")
    parts: list[str] = []
    if subj:
        parts.append(subj)
    elif (row.get("page_title") or "").strip():
        parts.append(str(row.get("page_title")).strip())
    if cust:
        parts.append(f"Заказчик: {cust}")
    if nmck:
        parts.append(f"НМЦК: {nmck}")
    if isinstance(dl, datetime):
        parts.append(f"Подача заявок до (UTC): {dl.strftime('%Y-%m-%d %H:%M')}")
    if len(parts) >= 2:
        return _truncate_ru(" ".join(parts), 720)
    blob = " ".join(
        p
        for p in [
            row.get("description") or "",
            row.get("text_excerpt") or "",
            row.get("page_title") or "",
        ]
        if p
    )
    if blob.strip():
        return _truncate_ru(blob, 520)
    return _snippet_fallback(it)


def _strip_json_fence(content: str) -> str:
    t = (content or "").strip()
    if not t.startswith("```"):
        return t
    lines = t.split("\n")
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


async def _fetch_preview(url: str) -> dict[str, Any]:
    """Download one tender URL and return text fields for summarization."""
    try:
        page: FetchedTenderPage = await fetch_tender_page(url)
        nf = page.notice_fields or {}
        return {
            "url": url,
            "page_title": (page.title or "").strip(),
            "description": (page.description or "").strip(),
            "text_excerpt": (page.text_excerpt or "").strip(),
            "application_deadline_utc": page.application_deadline_utc,
            "notice_subject": (nf.get("subject") or "").strip(),
            "notice_customer": (nf.get("customer") or "").strip(),
            "notice_nmck": (nf.get("nmck") or "").strip(),
            "notice_purchase_id": (nf.get("purchase_id") or "").strip(),
            "notice_placement_date": (nf.get("placement_date") or "").strip(),
            "ok": True,
        }
    except Exception as exc:  # noqa: BLE001 — any fetch/parse failure falls back to snippet
        logger.warning("tender enrich fetch failed for %s: %s", url, exc)
        return {
            "url": url,
            "page_title": "",
            "description": "",
            "text_excerpt": "",
            "application_deadline_utc": None,
            "notice_subject": "",
            "notice_customer": "",
            "notice_nmck": "",
            "notice_purchase_id": "",
            "notice_placement_date": "",
            "ok": False,
            "error": str(exc),
        }


async def _summarize_batch_openai(rows: list[dict[str, Any]], settings: Settings) -> dict[str, str]:
    """Return mapping ``url`` -> Russian summary via one OpenAI chat completion."""
    key = (settings.openai_api_key or "").strip()
    if not key or not rows:
        return {}
    client = create_async_openai_client(settings)
    payload: list[dict[str, Any]] = []
    for row in rows:
        dl = row.get("application_deadline_utc")
        dl_iso = dl.isoformat() if isinstance(dl, datetime) else None
        facts = {
            "subject": (row.get("notice_subject") or "").strip() or None,
            "customer": (row.get("notice_customer") or "").strip() or None,
            "nmck": (row.get("notice_nmck") or "").strip() or None,
            "purchase_id": (row.get("notice_purchase_id") or "").strip() or None,
            "placement_date_text": (row.get("notice_placement_date") or "").strip() or None,
            "submission_deadline_utc": dl_iso,
        }
        facts = {k: v for k, v in facts.items() if v}
        fallback = " ".join(
            [
                row.get("description") or "",
                (row.get("text_excerpt") or "")[:4000],
            ]
        ).strip()
        payload.append(
            {
                "url": row["url"],
                "structured_facts": facts,
                "page_text_if_subject_empty": fallback[:_MAX_BLOB_PER_ITEM] if not facts.get("subject") else "",
            }
        )
    user_json = json.dumps(payload, ensure_ascii=False)
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.25,
            max_tokens=_MAX_OUTPUT_TOKENS,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You help experienced Russian tender specialists (тендерщики). "
                        "Each input item has `structured_facts` parsed from the official notice card — "
                        "trust `subject` as the procurement object, `customer`, `nmck`, `submission_deadline_utc`. "
                        "`placement_date_text` is ONLY publication/placement date — NEVER present it as the bid deadline. "
                        "Write `summary_ru`: 2–3 tight sentences: what is bought/done, for whom (customer), "
                        "NMCK if present, and the submission deadline in plain words using ONLY `submission_deadline_utc` "
                        "(convert UTC to reader-friendly Moscow date/time when helpful). "
                        "If `structured_facts.subject` is missing, use `page_text_if_subject_empty` briefly. "
                        "Do not say «details not specified» if subject or customer exists in facts. "
                        "Never invent dates. "
                        "Output strictly valid JSON: {\"items\":[{\"url\":\"...\",\"summary_ru\":\"...\"}]} "
                        "covering every input url."
                    ),
                },
                {"role": "user", "content": user_json},
            ],
        )
    except APIError as exc:
        logger.warning("OpenAI tender batch summarization failed: %s", exc)
        return {}
    raw = (resp.choices[0].message.content or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(_strip_json_fence(raw))
    except json.JSONDecodeError as exc:
        logger.warning("OpenAI tender summary JSON parse failed: %s", exc)
        return {}
    items = data.get("items")
    if not isinstance(items, list):
        return {}
    out: dict[str, str] = {}
    for elem in items:
        if not isinstance(elem, dict):
            continue
        u = (elem.get("url") or "").strip()
        s = (elem.get("summary_ru") or elem.get("summary") or "").strip()
        if u and s:
            out[u] = s
    return out


def _preview_coherent_with_zakupki_url(preview: dict[str, Any], request_url: str) -> bool:
    """True when parsed ``purchase_id`` matches ``regNumber`` in the request URL (or cannot be checked)."""
    u = (request_url or "").strip()
    if "zakupki.gov.ru" not in u.lower():
        return True
    reg_u = reg_number_from_zakupki_url(u)
    pid = (preview.get("notice_purchase_id") or "").strip()
    if not reg_u or not pid:
        return True
    return zakupki_reg_numbers_equivalent(reg_u, pid)


def _strip_mismatched_zakupki_notice_fields(
    preview: dict[str, Any], request_url: str
) -> dict[str, Any]:
    """Drop structured notice fields when registry number in URL disagrees with parsed card fields."""
    if _preview_coherent_with_zakupki_url(preview, request_url):
        return preview
    logger.warning(
        "Zakupki URL regNumber vs parsed purchase_id mismatch; ignoring card fields for url=%s",
        (request_url or "")[:200],
    )
    return {
        **preview,
        "notice_subject": "",
        "notice_customer": "",
        "notice_nmck": "",
        "notice_purchase_id": "",
        "notice_placement_date": "",
    }


def _display_url_for_row(request_url: str) -> str:
    """Normalize zakupki notice links so displayed href matches the fetched common-info card."""
    u = (request_url or "").strip()
    if "zakupki.gov.ru" in u.lower():
        return canonical_zakupki_notice_url(u)
    return u


def _attach_deadline_field(out: dict[str, str], preview: dict[str, Any]) -> None:
    """Set ``submission_deadline_utc`` ISO string when the parser found a deadline."""
    d = preview.get("application_deadline_utc")
    if isinstance(d, datetime):
        out["submission_deadline_utc"] = d.isoformat()


def _should_include_for_open_filter(
    preview: dict[str, Any],
    *,
    only_open: bool,
    exclude_unknown: bool,
    now_utc: datetime,
) -> bool:
    """Return False if this hit must be dropped (deadline in the past)."""
    if not only_open:
        return True
    d = preview.get("application_deadline_utc")
    if d is None:
        return not exclude_unknown
    if not isinstance(d, datetime):
        return not exclude_unknown
    return d >= now_utc


async def enrich_tender_search_results(
    items: list[dict[str, str]],
    *,
    max_pages: int | None = None,
    use_ai: bool | None = None,
    only_open_deadlines: bool | None = None,
    exclusion_tokens: list[str] | None = None,
) -> list[dict[str, str]]:
    """Add ``summary`` to each search hit; optionally drop expired tenders by parsed deadline.

    Fetches every result (up to list length) to parse deadlines and text; OpenAI summarization
    applies only to the first ``tender_search_enrich_max_pages`` rows after filtering.

    Args:
        items: Rows from ``search_tender_candidates`` (``title``, ``url``, ``snippet``).
        max_pages: Max rows that receive AI summary (default: ``tender_search_enrich_max_pages``).
        use_ai: Call OpenAI when the key is set (default: ``tender_search_enrich_with_ai``).
        only_open_deadlines: Keep only tenders with submission deadline >= server UTC now
            (default: ``tender_search_only_open_deadlines``).
        exclusion_tokens: Lowercase tokens from user «без X» (e.g. сро); post-filter fetched pages.

    Returns:
        Dicts with ``summary``; optional ``submission_deadline_utc`` (ISO-8601) when parsed.
    """
    settings = get_settings()
    cap = max_pages if max_pages is not None else settings.tender_search_enrich_max_pages
    ai_flag = settings.tender_search_enrich_with_ai if use_ai is None else use_ai
    only_open = settings.tender_search_only_open_deadlines if only_open_deadlines is None else only_open_deadlines
    exclude_unknown = settings.tender_search_exclude_unknown_deadline
    cap = max(0, min(int(cap), 50))

    if not items:
        return []

    conc = max(1, min(settings.tender_search_enrich_concurrency, 10))
    sem = asyncio.Semaphore(conc)

    async def guarded(u: str) -> dict[str, Any]:
        async with sem:
            return await _fetch_preview(u)

    urls = [(it.get("url") or "").strip() for it in items]
    previews = await asyncio.gather(*[guarded(u) for u in urls])
    by_url = {p["url"]: p for p in previews}

    now_utc = datetime.now(timezone.utc)
    kept: list[tuple[dict[str, str], dict[str, Any]]] = []
    for it in items:
        u = (it.get("url") or "").strip()
        prev = by_url.get(u, {})
        if _should_include_for_open_filter(prev, only_open=only_open, exclude_unknown=exclude_unknown, now_utc=now_utc):
            kept.append((it, prev))

    if not kept and only_open and exclude_unknown:
        for it in items:
            u = (it.get("url") or "").strip()
            prev = by_url.get(u, {})
            if _should_include_for_open_filter(
                prev, only_open=only_open, exclude_unknown=False, now_utc=now_utc
            ):
                kept.append((it, prev))

    excl = [t for t in (exclusion_tokens or []) if t]
    if excl and kept:
        filtered = [p for p in kept if not should_drop_for_exclusion_tokens(p[1], excl)]
        if filtered:
            kept = filtered

    if not kept:
        return []

    ai_cap = min(cap, len(kept)) if cap > 0 else 0
    rows_for_ai: list[dict[str, Any]] = []
    for idx, (it, prev) in enumerate(kept):
        u = (it.get("url") or "").strip()
        prev_use = _strip_mismatched_zakupki_notice_fields(prev, u)
        row = {
            "url": u,
            "search_title": it.get("title") or "",
            "search_snippet": it.get("snippet") or "",
            **prev_use,
        }
        if idx < ai_cap:
            rows_for_ai.append(row)

    ai_map: dict[str, str] = {}
    if ai_flag and rows_for_ai:
        ai_map = await _summarize_batch_openai(rows_for_ai, settings)

    out_list: list[dict[str, str]] = []
    for idx, (it, prev) in enumerate(kept):
        u = (it.get("url") or "").strip()
        prev_use = _strip_mismatched_zakupki_notice_fields(prev, u)
        out = dict(it)
        out["url"] = _display_url_for_row(u)
        row = {
            "url": u,
            "search_title": it.get("title") or "",
            "search_snippet": it.get("snippet") or "",
            **prev_use,
        }
        if idx < ai_cap and u in ai_map and ai_map[u]:
            out["summary"] = _truncate_ru(ai_map[u], 900)
        else:
            out["summary"] = _heuristic_from_row(it, row)
        _attach_deadline_field(out, prev)
        subj = (prev_use.get("notice_subject") or "").strip()
        if subj:
            out["title"] = subj[:500]
        out_list.append(out)

    return out_list
