"""Tender import payload and documents URL derivation."""

from datetime import datetime, timezone

from app.services.tender.tender_external_service import FetchedTenderPage
from app.services.tender.tender_import_payload import build_tender_import_payload
from app.services.tender.tender_zakupki_urls import derive_zakupki_documents_url


def test_derive_documents_url() -> None:
    u = "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0123456789012345678"
    d = derive_zakupki_documents_url(u)
    assert d and "documents.html" in d
    assert "regNumber=0123456789012345678" in d


def test_build_payload_contains_zakupki_block() -> None:
    page = FetchedTenderPage(
        url="https://zakupki.gov.ru/x",
        final_url="https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=01",
        http_status=200,
        title="Subject",
        description="Desc",
        text_excerpt="",
        source_guess="zakupki.gov.ru",
        content_type="text/html",
        application_deadline_utc=datetime(2026, 12, 1, 12, 0, tzinfo=timezone.utc),
        notice_fields={
            "subject": "Поставка оборудования",
            "customer": "ООО Тест",
            "phones": "+7 391 111-22-33",
            "purchase_id": "0123456789012345678",
        },
    )
    p = build_tender_import_payload(page)
    assert "requirements" in p
    assert p["requirements"]["zakupki"]["subject"] == "Поставка оборудования"
    assert p["requirements"]["zakupki"]["phones"]
    assert p.get("documents_url")


def test_merge_import_description_uses_enriched_when_card_thin() -> None:
    from app.mcp.tools.tender_tools import _merge_import_description, _deadline_pair_from_enriched_iso

    hint = "НМЦК 1 500 000 ₽. Срок подачи заявок до 15 апреля 2026."
    out = _merge_import_description("x", None, hint)
    assert hint in (out or "")

    d, dt = _deadline_pair_from_enriched_iso("2026-04-15T12:00:00+00:00")
    assert d is not None and d.year == 2026 and dt is not None
