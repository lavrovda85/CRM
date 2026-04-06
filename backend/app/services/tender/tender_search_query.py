"""Normalize user tender search strings for ЕИС full-text search vs post-filters.

The EIS search box does not understand constraints like «без СРО» — such phrases often
return zero hits. We strip negative constraints for the HTTP search, then apply them
after fetching notice pages (heuristic: drop when SRO membership looks mandatory).
"""

from __future__ import annotations

import re


def normalize_eis_search_query(raw: str) -> tuple[str, list[str]]:
    """Return (query_for_eis_ddg, exclusion_tokens_for_post_filter).

    Args:
        raw: User or assistant query, e.g. «строительство без СРО Красноярский край».

    Returns:
        Tuple of cleaned string for zakupki/DDG and lowercase tokens taken from «без …».
    """
    s = (raw or "").strip()
    if not s:
        return "", []

    exclusions: list[str] = []
    # «без СРО», «без НДС» — capture word after «без»
    for m in re.finditer(r"(?iu)\bбез\s+([а-яёa-z0-9\-]{2,40})\b", s):
        exclusions.append(m.group(1).lower())
    s = re.sub(r"(?iu)\bбез\s+[а-яёa-z0-9\-]{2,40}\b", " ", s)
    # «кроме СРО», «исключая саморегулирование»
    s = re.sub(r"(?iu)\bкроме\s+[а-яёa-z0-9\-]{2,40}\b", " ", s)
    s = re.sub(r"(?iu)\bисключая\b[^,.;]{1,80}", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    # Typos: «по по» → «по»
    s = re.sub(r"(?i)\bпо\s+по\b", "по", s)

    if len(s) < 4 and raw.strip():
        s = raw.strip()

    return s, exclusions


def _haystack_for_exclusion(prev: dict[str, object]) -> str:
    parts = [
        str(prev.get("notice_subject") or ""),
        str(prev.get("notice_customer") or ""),
        str(prev.get("description") or ""),
        str(prev.get("text_excerpt") or ""),
        str(prev.get("page_title") or ""),
    ]
    return "\n".join(parts).lower()


def should_drop_for_sro_exclusion(text: str) -> bool:
    """True if the notice text suggests SRO membership is mandatory (user asked «без СРО»)."""
    low = text.lower()
    if "сро" not in low and "саморегулирован" not in low:
        return False
    # Explicitly «not required» — keep
    if re.search(
        r"(?i)(?:сро|саморегулирован).{0,40}(?:не\s+треб|не\s+предусмотрен|не\s+обязат|отсутств)",
        low,
    ):
        return False
    if re.search(r"(?i)(?:не\s+треб|без\s+требован).{0,60}(?:сро|членств)", low):
        return False
    # Mandatory SRO — drop
    if re.search(
        r"(?i)(?:требуется|обязательн|наличие|членство|включен\s+в\s+реестр).{0,120}(?:сро|саморегулирован)",
        low,
    ):
        return True
    if re.search(
        r"(?i)(?:сро|членств[ао]\s+в\s+сро).{0,80}(?:требуется|обязательн|наличие)",
        low,
    ):
        return True
    return False


def should_drop_for_exclusion_tokens(prev: dict[str, object], tokens: list[str]) -> bool:
    """Return True if this hit should be removed given «без X» tokens."""
    if not tokens:
        return False
    hay = _haystack_for_exclusion(prev)
    for tok in tokens:
        t = (tok or "").strip().lower()
        if not t:
            continue
        if t == "сро":
            if should_drop_for_sro_exclusion(hay):
                return True
        # Generic: if token is a long phrase, skip fuzzy match
        if len(t) <= 20 and t in hay:
            # «без НДС» — drop if VAT explicitly required (rare); keep simple: don't drop on mere mention
            continue
    return False
