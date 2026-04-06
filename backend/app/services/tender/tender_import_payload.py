"""Assemble CRM import payload from a fetched tender page (ЕИС / best-effort).

Maps scraped notice fields into ``Tender.description``, ``requirements`` JSON, ``notes``,
and auxiliary URLs so imports are usable for professional bid work.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .tender_external_service import FetchedTenderPage
from .tender_zakupki_urls import canonical_zakupki_notice_url, derive_zakupki_documents_url


def build_tender_import_payload(page: FetchedTenderPage) -> dict[str, Any]:
    """Build kwargs-aligned dict for MCP import: description, requirements, notes, documents_url.

    Args:
        page: Result of ``fetch_tender_page``.

    Returns:
        Keys: ``description``, ``requirements``, ``notes``, ``documents_url`` (optional str).
    """
    nf = page.notice_fields or {}
    docs: str | None = None
    for candidate in (page.final_url, page.url):
        if not candidate or "zakupki.gov.ru" not in candidate.lower():
            continue
        docs = derive_zakupki_documents_url(candidate) or derive_zakupki_documents_url(
            canonical_zakupki_notice_url(candidate)
        )
        if docs:
            break

    zak: dict[str, Any] = {k: v for k, v in nf.items() if v}
    if page.application_deadline_utc:
        zak["submission_deadline_utc"] = page.application_deadline_utc.isoformat()
    if docs:
        zak["documents_url"] = docs
    zak["notice_card_url"] = page.final_url

    req: dict[str, Any] = {
        "source_platform": page.source_guess or "web",
        "imported_at_utc": datetime.now(timezone.utc).isoformat(),
        "zakupki": zak,
    }

    desc_parts: list[str] = []
    if nf.get("subject"):
        desc_parts.append(nf["subject"])
    if nf.get("customer"):
        desc_parts.append(f"Заказчик: {nf['customer']}")
    if nf.get("nmck"):
        desc_parts.append(f"НМЦК: {nf['nmck']}")
    if nf.get("procedure_type"):
        desc_parts.append(f"Способ закупки: {nf['procedure_type']}")
    if nf.get("delivery_place"):
        desc_parts.append(f"Место поставки / выполнения: {nf['delivery_place']}")
    if nf.get("etp_name"):
        desc_parts.append(f"Электронная площадка: {nf['etp_name']}")
    description = "\n\n".join(desc_parts)[:8000] if desc_parts else (page.description or "")[:8000]

    note_sections: list[str] = []
    if nf.get("purchase_id"):
        note_sections.append(f"ИКЗ: {nf['purchase_id']}")
    if nf.get("placement_date"):
        note_sections.append(f"Дата размещения извещения: {nf['placement_date']}")
    if nf.get("contact_person"):
        note_sections.append(f"Контакт: {nf['contact_person']}")
    if nf.get("phones"):
        note_sections.append(f"Тел.: {nf['phones']}")
    if nf.get("emails"):
        note_sections.append(f"E-mail: {nf['emails']}")
    if nf.get("fax"):
        note_sections.append(f"Факс: {nf['fax']}")
    if nf.get("customer_inn"):
        note_sections.append(f"ИНН заказчика: {nf['customer_inn']}")
    if nf.get("customer_address"):
        note_sections.append(f"Адрес заказчика: {nf['customer_address']}")
    if nf.get("bid_security"):
        note_sections.append(f"Обеспечение заявки: {nf['bid_security']}")
    if nf.get("contract_security"):
        note_sections.append(f"Обеспечение контракта: {nf['contract_security']}")
    if nf.get("okpd2_line"):
        note_sections.append(f"ОКПД2: {nf['okpd2_line']}")
    if page.http_status >= 400:
        note_sections.append(f"HTTP при загрузке карточки: {page.http_status}")
    notes = "\n".join(note_sections)[:12000] if note_sections else None

    return {
        "description": description,
        "requirements": req,
        "notes": notes,
        "documents_url": docs,
    }
