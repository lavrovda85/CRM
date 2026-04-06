"""Structured field extraction from ЕИС (zakupki.gov.ru) notice HTML.

Extracts fields a professional buyer needs: subject, customer, NMCK, contacts, links context,
guarantees, procedure, OKPD2, etc. Table rows are matched by Russian label patterns.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from bs4 import BeautifulSoup

_SUBJECT_RE = re.compile(
    r"(?:наименование объекта закупки|предмет\s+(?:контракта|договора|закупки)|наименование закупки)",
    re.I | re.UNICODE,
)
_CUSTOMER_RE = re.compile(
    r"(?:^|\s)(?:заказчик|организация,?\s+осуществляющая размещение|размещение осуществляет)",
    re.I | re.UNICODE,
)
_NMCK_RE = re.compile(
    r"(?:начальн[аяя].{0,60}цена|нмцк|цена\s+контракта|начальная\s+цена)",
    re.I | re.UNICODE,
)
_PURCHASE_ID_RE = re.compile(
    r"(?:идентификационный код закупки|реестровый номер)",
    re.I | re.UNICODE,
)
_PLACEMENT_RE = re.compile(
    r"дата\s+(?:публикации|размещения)\s+(?:извещения|извещения о закупке)?",
    re.I | re.UNICODE,
)
_INN_RE = re.compile(r"(?:^|\s)инн\b|идентификационный номер налогоплательщика", re.I | re.UNICODE)
_KPP_RE = re.compile(r"^кпп\b", re.I | re.UNICODE)
_CONTACT_RE = re.compile(
    r"контактн[оеая]\s+лицо|ответственн[оеая]\s+должностн[оеая]\s+лицо|ответственное\s+лицо",
    re.I | re.UNICODE,
)
_PHONE_RE = re.compile(
    r"^телефон|номер\s+телефона|местный\s+телефон|контактный\s+телефон|"
    r"номер\s+контактного\s+телефона|контактного\s+телефона",
    re.I | re.UNICODE,
)
_EMAIL_RE = re.compile(
    r"e-?mail|электронн[аяя]\s+почт|адрес\s+электронной\s+почты",
    re.I | re.UNICODE,
)
_FAX_RE = re.compile(r"факс", re.I | re.UNICODE)
_ADDR_RE = re.compile(
    r"юридическ(?:ий|ого)\s+адрес|место\s+нахождения|почтовый\s+адрес",
    re.I | re.UNICODE,
)
_PROC_RE = re.compile(
    r"способ\s+определения\s+поставщика|способ\s+закупки|электронн[аяя]\s+процедура",
    re.I | re.UNICODE,
)
_ETP_RE = re.compile(
    r"наименование\s+электронн[ойая]\s+площадки|оператор\s+электронн[ойая]\s+площадки|электронн[аяя]\s+площадка",
    re.I | re.UNICODE,
)
_DELIVERY_RE = re.compile(
    r"место\s+(?:поставки|доставки)|место\s+выполнения\s+работ|место\s+оказания\s+услуг",
    re.I | re.UNICODE,
)
_BID_SEC_RE = re.compile(
    r"обеспечен(?:ие|ия)\s+заявки|размер\s+обеспечения\s+заявки",
    re.I | re.UNICODE,
)
_CONT_SEC_RE = re.compile(
    r"обеспечен(?:ие|ия)\s+(?:исполнения\s+)?контракта|обеспечение\s+исполнения\s+обязательств",
    re.I | re.UNICODE,
)
_OKPD_RE = re.compile(r"окпд\s*2|код(?:ы)?\s+окпд", re.I | re.UNICODE)

# Fallback when DOM layout omits classes we match (or markup is minified differently).
_NMCK_NEAR_LABEL_RE = re.compile(
    r"(?:начальн[аяя]\s*\(максимальн[аяя]\)\s*цена\s*контракта|"
    r"начальн[аяя]\s+цена\s+контракта|нмцк|цена\s+контракта)"
    r"[\s\S]{0,220}?"
    r"(\d[\d\s\u00a0]*(?:[.,]\d{1,2})?)\s*(?:руб|₽)?",
    re.I | re.UNICODE,
)
_PHONE_FALLBACK_RE = re.compile(
    r"(?:\+?7|8)[\s\-]?(?:\(\d{3}\)|\d{3})[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}",
    re.UNICODE,
)
_EMAIL_FALLBACK_RE = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    re.UNICODE,
)

# (field_name, pattern, max_len, append_multi)
_SPECS: list[tuple[str, re.Pattern[str], int, bool]] = [
    ("subject", _SUBJECT_RE, 2000, False),
    ("purchase_id", _PURCHASE_ID_RE, 200, False),
    ("customer", _CUSTOMER_RE, 2000, False),
    ("customer_inn", _INN_RE, 32, False),
    ("customer_kpp", _KPP_RE, 32, False),
    ("customer_address", _ADDR_RE, 2000, False),
    ("contact_person", _CONTACT_RE, 500, False),
    ("phones", _PHONE_RE, 200, True),
    ("fax", _FAX_RE, 120, False),
    ("emails", _EMAIL_RE, 200, True),
    ("nmck", _NMCK_RE, 500, False),
    ("placement_date", _PLACEMENT_RE, 120, False),
    ("procedure_type", _PROC_RE, 500, False),
    ("etp_name", _ETP_RE, 500, False),
    ("delivery_place", _DELIVERY_RE, 2000, False),
    ("bid_security", _BID_SEC_RE, 400, False),
    ("contract_security", _CONT_SEC_RE, 400, False),
    ("okpd2_line", _OKPD_RE, 800, False),
]


def _norm_label(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _cell_pair_from_tr(tr: Any) -> tuple[str, str] | None:
    cells = tr.find_all(["td", "th"])
    if len(cells) < 2:
        return None
    label = cells[0].get_text(" ", strip=True)
    value = " ".join(c.get_text(" ", strip=True) for c in cells[1:])
    if not label or len(label) > 600:
        return None
    return label, value


@dataclass
class ZakupkiNoticeFields:
    """Human-oriented fields scraped from the ЕИС notice card."""

    subject: str | None = None
    customer: str | None = None
    nmck: str | None = None
    purchase_id: str | None = None
    placement_date: str | None = None
    contact_person: str | None = None
    phones: str | None = None
    emails: str | None = None
    fax: str | None = None
    customer_inn: str | None = None
    customer_kpp: str | None = None
    customer_address: str | None = None
    delivery_place: str | None = None
    procedure_type: str | None = None
    etp_name: str | None = None
    bid_security: str | None = None
    contract_security: str | None = None
    okpd2_line: str | None = None

    def to_public_dict(self) -> dict[str, str]:
        """Serializable non-empty fields for API / cache."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v}


def _apply_row(out: ZakupkiNoticeFields, label: str, value: str) -> None:
    low = _norm_label(label)
    val = (value or "").strip()
    if not val or len(val) > 8000:
        return
    val = val[:8000]
    for fname, pat, mx, multi in _SPECS:
        if not pat.search(low):
            continue
        cur = getattr(out, fname)
        if multi:
            chunk = val[:mx]
            if cur:
                if chunk in cur:
                    return
                merged = f"{cur}; {chunk}"[: mx * 5]
            else:
                merged = chunk
            setattr(out, fname, merged)
            return
        if cur is None:
            setattr(out, fname, val[:mx])
        return


_TITLE_SPAN_CLASSES = re.compile(r"section__title|cardMainInfo__title", re.I)
_VALUE_SPAN_CLASSES = re.compile(r"section__info|cardMainInfo__content", re.I)


def _extract_pairs_modern_eis_layout(soup: BeautifulSoup) -> list[tuple[str, str]]:
    """Collect label/value pairs from ЕИС blockInfo / cardMainInfo (not only HTML tables).

    New zakupki cards use ``section__title`` + ``section__info`` and
    ``cardMainInfo__title`` + ``cardMainInfo__content`` instead of ``<tr>`` rows.
    Prefer **parent-scoped** search so whitespace/comment nodes between siblings do not break pairing.
    """
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add_pair(label: str, value: str) -> None:
        label = (label or "").strip()
        value = (value or "").strip()
        if not label or not value or len(label) > 600 or len(value) > 8000:
            return
        key = (label[:300], value[:500])
        if key in seen:
            return
        seen.add(key)
        pairs.append((label, value))

    for sel in (
        "section.blockInfo__section",
        "div.blockInfo__section",
        "div.cardMainInfo__section",
        "div.price",
    ):
        for node in soup.select(sel):
            tit = node.find(class_=re.compile(r"section__title|cardMainInfo__title", re.I))
            val = node.find(class_=re.compile(r"section__info|cardMainInfo__content", re.I))
            if tit and val:
                add_pair(tit.get_text(" ", strip=True), val.get_text(" ", strip=True))

    for tit in soup.find_all(class_=_TITLE_SPAN_CLASSES):
        val = tit.find_next_sibling(["span", "div"], class_=_VALUE_SPAN_CLASSES)
        if val:
            add_pair(tit.get_text(" ", strip=True), val.get_text(" ", strip=True))

    return pairs


def merge_zakupki_notice_fields_from_cache(zf: ZakupkiNoticeFields, cached: dict[str, str]) -> None:
    """Fill empty ``zf`` attributes from a cached ``notice_fields`` dict (e.g. prior search enrich)."""
    if not cached:
        return
    for k, v in cached.items():
        if not v or not str(v).strip():
            continue
        if not hasattr(zf, k):
            continue
        cur = getattr(zf, k)
        if cur is not None and str(cur).strip():
            continue
        setattr(zf, k, str(v).strip()[:8000])


def _apply_regex_fallbacks(html: str, out: ZakupkiNoticeFields) -> None:
    """Fill missing NMCK / phone / email from raw HTML when structured parsing failed."""
    if not html or not html.strip():
        return
    if not (out.nmck or "").strip():
        m = _NMCK_NEAR_LABEL_RE.search(html)
        if m:
            out.nmck = m.group(1).strip()[:500]
    if not (out.phones or "").strip():
        pm = _PHONE_FALLBACK_RE.search(html)
        if pm:
            out.phones = pm.group(0).strip()[:200]
    if not (out.emails or "").strip():
        em = _EMAIL_FALLBACK_RE.search(html)
        if em:
            out.emails = em.group(0).strip()[:200]


def _extract_mailto_tel(soup: BeautifulSoup, out: ZakupkiNoticeFields) -> None:
    """Fill phones/emails from mailto:/tel: links when table rows missed them."""
    emails: list[str] = []
    phones: list[str] = []
    for a in soup.find_all("a", href=True):
        h = str(a.get("href") or "").strip()
        if h.lower().startswith("mailto:"):
            e = h[7:].split("?", 1)[0].strip()
            if e and "@" in e:
                emails.append(e[:200])
        elif h.lower().startswith("tel:"):
            t = h[4:].strip()
            if t:
                phones.append(t[:80])
    if emails:
        ex = out.emails or ""
        add = "; ".join(dict.fromkeys(emails))
        out.emails = f"{ex}; {add}".strip("; ") if ex else add
    if phones:
        px = out.phones or ""
        addp = "; ".join(dict.fromkeys(phones))
        out.phones = f"{px}; {addp}".strip("; ") if px else addp


def extract_zakupki_notice_fields(html: str) -> ZakupkiNoticeFields:
    """Parse procurement fields from zakupki HTML."""
    out = ZakupkiNoticeFields()
    if not (html and html.strip()):
        return out
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    for tr in soup.find_all("tr"):
        pair = _cell_pair_from_tr(tr)
        if not pair:
            continue
        label, value = pair
        _apply_row(out, label, value)

    for label, value in _extract_pairs_modern_eis_layout(soup):
        _apply_row(out, label, value)

    _extract_mailto_tel(soup, out)
    _apply_regex_fallbacks(html, out)
    return out


def parse_nmck_rubles_to_decimal(nmck: str | None) -> Decimal | None:
    """Parse NMCK string like «1 234 567,89 руб.» into rubles."""
    if not nmck or not str(nmck).strip():
        return None
    s = re.sub(r"[^\d,\.]", "", str(nmck).replace("\xa0", " ").replace(" ", ""))
    if not s:
        return None
    if "," in s:
        parts = s.split(",")
        if len(parts[-1]) <= 2 and len(parts) > 1:
            s = "".join(parts[:-1]) + "." + parts[-1]
        else:
            s = s.replace(",", "")
    try:
        d = Decimal(s)
        if d < 0 or d > Decimal("1e15"):
            return None
        return d
    except InvalidOperation:
        return None


def parse_guarantee_rubles(text: str | None) -> Decimal | None:
    """Parse monetary amount from guarantee / security line (best effort)."""
    return parse_nmck_rubles_to_decimal(text)


def build_notice_description_line(fields: ZakupkiNoticeFields) -> str | None:
    """Single-line description from structured fields."""
    parts: list[str] = []
    if fields.subject:
        parts.append(fields.subject)
    if fields.customer:
        parts.append(f"Заказчик: {fields.customer}")
    if fields.nmck:
        parts.append(f"НМЦК: {fields.nmck}")
    if not parts:
        return None
    return " · ".join(parts)[:4000]
