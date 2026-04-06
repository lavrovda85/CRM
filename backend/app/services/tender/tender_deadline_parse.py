"""Extract application submission deadline from tender HTML (ЕИС / similar RU layouts).

Uses only fields related to **submission of applications** (подача/приём заявок), not
certificate validity, license dates, or other «срок» lines that appear on the same page.

Parsed times are interpreted in Europe/Moscow when the page does not specify a zone,
then converted to UTC for comparison with server time.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

_MSK = ZoneInfo("Europe/Moscow")
# ЕИС shows regional time vs Moscow, e.g. «(МСК+4)» for Krasnoyarsk.
_MSK_OFFSET_TO_ZONE = {
    0: _MSK,
    1: ZoneInfo("Europe/Samara"),  # MSK+1 — approximate
    2: ZoneInfo("Asia/Yekaterinburg"),
    3: ZoneInfo("Asia/Omsk"),
    4: ZoneInfo("Asia/Krasnoyarsk"),
    5: ZoneInfo("Asia/Irkutsk"),
    6: ZoneInfo("Asia/Yakutsk"),
    7: ZoneInfo("Asia/Vladivostok"),
    8: ZoneInfo("Asia/Magadan"),
    9: ZoneInfo("Asia/Kamchatka"),
}

# Lines that look like a deadline but refer to certificates, licenses, etc. (exclude).
_WRONG_FIELD_RE = re.compile(
    r"(?:"
    r"срок\s+действия\s+сертификата"
    r"|действия\s+сертификата"
    r"|сертификат[ао]?\s+(?:соответствия|)?"
    r"|лицензи"
    r"|аккредитац"
    r"|квалификац"
    r")",
    re.I | re.UNICODE,
)

# Submission-related labels (more specific patterns first for table matching).
_SUBMISSION_LABEL_RES: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"дата\s+и\s+время\s+окончания\s+срока\s+подачи\s+заявок",
        re.I | re.UNICODE,
    ),
    re.compile(
        r"дата\s+окончания\s+срока\s+подачи\s+заявок",
        re.I | re.UNICODE,
    ),
    re.compile(
        r"крайний\s+срок\s+подачи\s+заявок",
        re.I | re.UNICODE,
    ),
    re.compile(
        r"окончани[ея]\s+срока\s+подачи\s+заявок",
        re.I | re.UNICODE,
    ),
    re.compile(
        r"окончани[ея]\s+подачи\s+заявок",
        re.I | re.UNICODE,
    ),
    re.compile(
        r"срок\s+подачи\s+заявок",
        re.I | re.UNICODE,
    ),
    re.compile(
        r"окончани[ея]\s+приёма\s+заявок",
        re.I | re.UNICODE,
    ),
    re.compile(
        r"приём[а]?\s+заявок",
        re.I | re.UNICODE,
    ),
)

_DD_MM_YYYY_TIME = re.compile(
    r"(\d{2})\.(\d{2})\.(\d{4})(?:\s+(?:в\s+)?(\d{2}):(\d{2})(?::(\d{2}))?)?"
)


def _zone_from_submission_context(value_text: str) -> ZoneInfo:
    """Pick IANA zone for submission deadline line (ЕИС «МСК+N» hints)."""
    low = value_text.lower()
    if "красноярск" in low:
        return ZoneInfo("Asia/Krasnoyarsk")
    if "новосибирск" in low:
        return ZoneInfo("Asia/Novosibirsk")
    m = re.search(r"\(мск\+(\d+)\)", low)
    if m:
        off = int(m.group(1))
        return _MSK_OFFSET_TO_ZONE.get(off, _MSK)
    return _MSK


def _match_to_utc(m: re.Match[str], *, zone: ZoneInfo | None = None) -> datetime | None:
    """Build UTC datetime from regex groups: DD MM YYYY [HH:MM[:SS]]."""
    d, mth, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hh, mm, ss = m.group(4), m.group(5), m.group(6)
    tz = zone or _MSK
    try:
        if hh is not None and mm is not None:
            sec = int(ss) if ss else 0
            local = datetime(y, mth, d, int(hh), int(mm), sec, tzinfo=tz)
        else:
            local = datetime(y, mth, d, 23, 59, 59, tzinfo=tz)
        return local.astimezone(timezone.utc)
    except ValueError:
        return None


def _label_is_submission_deadline(label: str) -> bool:
    low = label.lower().strip()
    if _WRONG_FIELD_RE.search(low) and not any(
        p.search(low) for p in _SUBMISSION_LABEL_RES
    ):
        return False
    return any(p.search(low) for p in _SUBMISSION_LABEL_RES)


def _segment_is_plausible_deadline(segment: str) -> bool:
    """Reject date windows that clearly belong to certificate / wrong block."""
    s = segment.lower()
    if "сертификат" in s and "заявок" not in s:
        return False
    if _WRONG_FIELD_RE.search(segment) and "заявок" not in s:
        return False
    return True


def _extract_from_table_rows(soup: BeautifulSoup) -> datetime | None:
    """ЕИС-style: first column = label, second = value."""
    for tr in soup.find_all("tr"):
        cells = tr.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        label = cells[0].get_text(" ", strip=True)
        value = " ".join(c.get_text(" ", strip=True) for c in cells[1:])
        if len(label) > 500 or len(value) > 500:
            continue
        if _WRONG_FIELD_RE.search(label) and not _label_is_submission_deadline(label):
            continue
        if not _label_is_submission_deadline(label):
            continue
        dm = _DD_MM_YYYY_TIME.search(value)
        if dm:
            z = _zone_from_submission_context(value)
            got = _match_to_utc(dm, zone=z)
            if got:
                return got
    return None


def _extract_from_blockinfo_sections(soup: BeautifulSoup) -> datetime | None:
    """ЕИС blockInfo: ``section__title`` + ``section__info`` (same labels as table rows)."""
    for sec in soup.find_all("section", class_=lambda c: c and "blockInfo__section" in str(c)):
        tit = sec.find("span", class_=re.compile(r"section__title"))
        if not tit:
            continue
        label = tit.get_text(" ", strip=True)
        if len(label) > 500:
            continue
        if _WRONG_FIELD_RE.search(label) and not _label_is_submission_deadline(label):
            continue
        if not _label_is_submission_deadline(label):
            continue
        info = sec.find("span", class_=re.compile(r"section__info"))
        if not info:
            continue
        value = info.get_text(" ", strip=True)
        if not _segment_is_plausible_deadline(value[:200]):
            continue
        dm = _DD_MM_YYYY_TIME.search(value)
        if dm:
            z = _zone_from_submission_context(value)
            got = _match_to_utc(dm, zone=z)
            if got:
                return got
    return None


def _extract_after_labels(flat_text: str) -> datetime | None:
    """Find submission label, then first DD.MM.YYYY in the following window only."""
    text_one = re.sub(r"\s+", " ", flat_text)
    low = text_one.lower()
    for pat in _SUBMISSION_LABEL_RES:
        for m in pat.finditer(low):
            start = m.end()
            segment = text_one[start : start + 200]
            if not _segment_is_plausible_deadline(segment[:120]):
                continue
            dm = _DD_MM_YYYY_TIME.search(segment)
            if dm:
                got = _match_to_utc(dm, zone=_zone_from_submission_context(segment))
                if got:
                    return got
    return None


def extract_application_deadline_utc_from_html(html: str) -> datetime | None:
    """Parse submission deadline from HTML; return aware UTC datetime or None.

    Ignores «срок действия сертификата» and similar fields; only uses application submission lines.

    Args:
        html: Raw HTML of a notice / common-info page.

    Returns:
        Deadline instant in UTC, or None if not found or not parseable.
    """
    if not (html and html.strip()):
        return None
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    got = _extract_from_table_rows(soup)
    if got:
        return got

    got = _extract_from_blockinfo_sections(soup)
    if got:
        return got

    flat = soup.get_text("\n", strip=True)
    return _extract_after_labels(flat)
