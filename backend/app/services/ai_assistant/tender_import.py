"""Heuristics for tender import UX in the AI assistant (Russian phrasing)."""

from __future__ import annotations

import re
from typing import Any

from app.services.tender.tender_zakupki_urls import canonical_zakupki_notice_url

_TENDER_IMPORT_INTENT_RE = re.compile(
    r"(добавь(те)?|добавить|импорт|внеси(те)?|сохрани(те)?|зарегистр|занеси|перенеси|положи|отправ).{0,80}тендер",
    re.IGNORECASE | re.DOTALL,
)


def parse_tender_list_index_from_message(message: str) -> int | None:
    """Extract 1-based row number from user text (matches assistant's numbered search list).

    Handles: «добавь 4 в тендеры», «номер 3», «#2», «№ 5», «4-й тендер».
    Returns None when no explicit index (caller should use the first result).
    """
    raw = (message or "").strip()
    if not raw:
        return None
    low = raw.lower()
    m = re.search(r"(?:номер|#|№\.?|п\.)\s*(\d{1,2})\b", raw, re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(
        r"(?:добавь(?:те)?|внеси(?:те)?|занеси(?:те)?|импорт(?:ируй(?:те)?)?)\s+(\d{1,2})\b",
        low,
    )
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d{1,2})[-‐]?\s*(?:й|я|ое|ье)\s+.*тендер", low)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(\d{1,2})\s+(?:в\s+)?(?:тендер|закуп)", low)
    if m:
        return int(m.group(1))
    return None


def _urls_point_to_same_zakupki_notice(a: str, b: str) -> bool:
    """True when two URLs refer to the same ЕИС notice (canonical regNumber match)."""
    x = (a or "").strip()
    y = (b or "").strip()
    if not x or not y:
        return False
    if x == y:
        return True
    if "zakupki.gov.ru" not in x.lower() or "zakupki.gov.ru" not in y.lower():
        return False
    try:
        return canonical_zakupki_notice_url(x) == canonical_zakupki_notice_url(y)
    except Exception:
        return False


def get_tender_search_row_for_import(
    session_context: dict[str, Any] | None,
    user_message: str,
) -> dict[str, Any] | None:
    """Return the full session row for an explicit list index (1-based), or None if no index in text."""
    if not session_context:
        return None
    idx = parse_tender_list_index_from_message(user_message)
    if idx is None:
        return None
    rows = session_context.get("last_tender_search_results")
    if not isinstance(rows, list) or not rows:
        return None
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            ri = int(r.get("index", -1))
        except (TypeError, ValueError):
            continue
        if ri == idx:
            return r
    if 1 <= idx <= len(rows):
        r = rows[idx - 1]
        return r if isinstance(r, dict) else None
    return None


def find_tender_search_row_by_url(
    session_context: dict[str, Any] | None,
    url: str,
) -> dict[str, Any] | None:
    """Find a stored search row whose URL matches ``url`` (canonical zakupki compare)."""
    if not session_context or not (url or "").strip():
        return None
    rows = session_context.get("last_tender_search_results")
    if not isinstance(rows, list):
        return None
    for r in rows:
        if not isinstance(r, dict):
            continue
        ru = str(r.get("url") or "").strip()
        if ru and _urls_point_to_same_zakupki_notice(ru, url):
            return r
    return None


def resolve_tender_search_row_for_hints(
    session_context: dict[str, Any] | None,
    user_message: str,
    target_url: str,
) -> dict[str, Any] | None:
    """Pick session search row for import hints: by explicit index if it matches URL, else by URL."""
    u = (target_url or "").strip()
    if not u:
        return None
    by_idx = get_tender_search_row_for_import(session_context, user_message)
    if by_idx:
        ru = str(by_idx.get("url") or "").strip()
        if ru and _urls_point_to_same_zakupki_notice(ru, u):
            return by_idx
    return find_tender_search_row_by_url(session_context, u)


def resolve_tender_search_url_for_import(
    session_context: dict[str, Any] | None,
    user_message: str,
) -> str | None:
    """Pick zakupki URL from last search: by explicit index if present, else first row."""
    if not session_context:
        return None
    idx = parse_tender_list_index_from_message(user_message)
    rows = session_context.get("last_tender_search_results")
    urls = session_context.get("last_tender_search_urls")

    if idx is not None:
        if isinstance(rows, list) and rows:
            for r in rows:
                if not isinstance(r, dict):
                    continue
                try:
                    ri = int(r.get("index", -1))
                except (TypeError, ValueError):
                    continue
                if ri == idx:
                    u = str(r.get("url") or "").strip()
                    if u:
                        return u
            if 1 <= idx <= len(rows):
                r = rows[idx - 1]
                if isinstance(r, dict):
                    u = str(r.get("url") or "").strip()
                    if u:
                        return u
        return None

    u = str(session_context.get("last_tender_search_first_url") or "").strip()
    if u:
        return u
    if isinstance(urls, list) and urls:
        first = str(urls[0] or "").strip()
        return first or None
    return None


def user_wants_tender_import_crm(message: str) -> bool:
    """True when the user asks to add/import a tender into CRM (Russian)."""
    t = (message or "").strip().lower()
    if not t:
        return False
    if "тендер" not in t:
        return False
    if re.search(r"\bкак\s+(добавить|импортировать|сохранить|внести)", t):
        return False
    return bool(_TENDER_IMPORT_INTENT_RE.search(t))


def reply_when_tender_import_not_executed() -> str:
    """Deterministic reply when the model claimed success without calling import_tender_from_url."""
    return (
        "Импорт **не был выполнен**: для записи тендера в CRM нужно вызвать инструмент "
        "`import_tender_from_url` с **полной ссылкой** на карточку zakupki.gov.ru "
        "(из прошлого сообщения или из поиска). Пожалуйста, отправьте **ещё одно сообщение**, "
        "куда вставьте эту ссылку одной строкой, и напишите «добавь этот тендер в CRM» — "
        "я вызову импорт. Либо откройте в приложении **Тендеры → Новый тендер** и вставьте ссылку вручную."
    )


def session_first_tender_search_url(session_context: dict[str, Any] | None) -> str | None:
    """Return the first zakupki URL from the last search (no index in message)."""
    return resolve_tender_search_url_for_import(session_context, "")


def reply_after_auto_tender_import(user_message: str, out: dict[str, Any]) -> str:
    """Build a short confirmation after server-side import_tender_from_url."""
    tid = out.get("id")
    title = str(out.get("title") or "").strip() or "тендер"
    if is_russian(user_message):
        return f"Тендер «{title}» добавлен в CRM (id: {tid})."
    return f"Tender «{title}» added to CRM (id: {tid})."


def is_russian(text: str) -> bool:
    """Heuristic to pick reply language."""
    t = (text or "").lower()
    return any(ch in t for ch in ("а", "б", "в", "г", "д", "е", "ё", "ж", "з", "и", "й", "к", "л"))
