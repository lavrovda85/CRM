"""Heuristics for tender web search UX (pagination / «ещё») in the AI assistant."""

from __future__ import annotations

import re
from typing import Any


_MORE_TENDER_RESULTS_RE = re.compile(
    r"(ещ[ёе]|следующ|дальше|продолж|покажи\s+ещ|еще\s+вариант|другие\s+результат|ещё\s+раз|"
    r"след\s+страниц|next\s+page|load\s+more)",
    re.IGNORECASE,
)


def user_wants_more_tender_results(message: str) -> bool:
    """True when the user likely asks for the next chunk of search results (same topic).

    Used to inject ``exclude_urls`` from session and avoid repeating already shown notices.
    """
    t = (message or "").strip().lower()
    if not t:
        return False
    if _MORE_TENDER_RESULTS_RE.search(t):
        return True
    if t in ("ещё", "еще", "дальше", "следующие", "следующая", "ещё.", "еще."):
        return True
    return False


def should_force_tender_web_search(message: str) -> bool:
    """True when the user asks for public procurement / ЕИС search, not CRM-internal lists.

    Used to inject ``search_tenders_on_web`` if the model replied without tools and that search
    has not run yet this turn (avoids generic hallucinated links after a spurious first tool call).
    """
    t = (message or "").strip().lower()
    if len(t) < 10:
        return False
    tender_kw = any(
        x in t
        for x in (
            "тендер",
            "тендеры",
            "закупк",
            "закупки",
            "еис",
            "zakupki",
            "goszakup",
            "госзакуп",
        )
    )
    if not tender_kw:
        return False
    # Prefer CRM list tools, not web search
    if any(x in t for x in ("в crm", "в срм", "в системе", "наши тендеры", "мои тендеры", "список тендеров в")):
        return False
    if "http://" in t or "https://" in t:
        return False
    webish = any(
        x in t
        for x in (
            "актуальн",
            "найди",
            "поиск",
            "посмотри",
            "есть ли",
            "какие ",
            "подбери",
            "интернет",
            "на сайте",
            "госзакуп",
            "закупки гос",
            "краснояр",
            "област",
            "край",
            "регион",
            "вентиляц",
            "кондицион",
            "монтаж",
            "поставк",
        )
    )
    return webish


def collect_exclude_urls_from_session(session_context: dict[str, Any] | None) -> list[str]:
    """Return normalized list of URLs already shown (for ``exclude_urls``), capped."""
    if not session_context:
        return []
    raw = session_context.get("tender_search_seen_urls")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for u in raw:
        s = str(u).strip()
        if s:
            out.append(s)
        if len(out) >= 400:
            break
    return out
