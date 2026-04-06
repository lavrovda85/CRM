"""Tests for tender search enrichment (mocked fetch / OpenAI)."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.tender.tender_external_service import FetchedTenderPage
from app.services.tender.tender_search_enrich_service import enrich_tender_search_results


def _fake_page(url: str, *, deadline=None) -> FetchedTenderPage:
    return FetchedTenderPage(
        url=url,
        final_url=url,
        http_status=200,
        title="Поставка систем вентиляции для школы",
        description="Закупка оборудования для нужд заказчика в Красноярском крае.",
        text_excerpt="Начальная цена 1 200 000 руб. Срок подачи заявок до 15.04.2026.",
        source_guess="zakupki.gov.ru",
        content_type="text/html",
        application_deadline_utc=deadline,
        notice_fields=None,
    )


@pytest.mark.asyncio
async def test_enrich_adds_heuristic_summary_without_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch(u: str) -> FetchedTenderPage:
        return _fake_page(u)

    mock_fetch = AsyncMock(side_effect=fake_fetch)
    monkeypatch.setattr(
        "app.services.tender.tender_search_enrich_service.fetch_tender_page",
        mock_fetch,
    )
    items = [
        {
            "title": "Тендер № 1",
            "url": "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=1",
            "snippet": "ЕИС",
        }
    ]
    with patch("app.services.tender.tender_search_enrich_service.get_settings") as gs:
        s = gs.return_value
        s.tender_search_enrich_max_pages = 8
        s.tender_search_enrich_with_ai = False
        s.tender_search_enrich_concurrency = 2
        s.openai_api_key = None
        s.tender_search_only_open_deadlines = False
        s.tender_search_exclude_unknown_deadline = False
        out = await enrich_tender_search_results(items, use_ai=False, only_open_deadlines=False)
    assert len(out) == 1
    assert "summary" in out[0]
    assert "вентиляции" in out[0]["summary"] or "1 200 000" in out[0]["summary"]
    mock_fetch.assert_awaited()


@pytest.mark.asyncio
async def test_second_row_heuristic_when_ai_cap_is_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """All rows are fetched; only the first ``max_pages`` rows get OpenAI (here AI off)."""

    async def fake_fetch(u: str) -> FetchedTenderPage:
        return _fake_page(u)

    mock_fetch = AsyncMock(side_effect=fake_fetch)
    monkeypatch.setattr(
        "app.services.tender.tender_search_enrich_service.fetch_tender_page",
        mock_fetch,
    )
    items = [
        {
            "title": "First",
            "url": "https://example.com/a",
            "snippet": "s1",
        },
        {
            "title": "Second tail",
            "url": "https://example.com/b",
            "snippet": "only snippet for second",
        },
    ]
    with patch("app.services.tender.tender_search_enrich_service.get_settings") as gs:
        s = gs.return_value
        s.tender_search_enrich_max_pages = 1
        s.tender_search_enrich_with_ai = False
        s.tender_search_enrich_concurrency = 2
        s.tender_search_only_open_deadlines = False
        s.tender_search_exclude_unknown_deadline = False
        out = await enrich_tender_search_results(items, max_pages=1, use_ai=False, only_open_deadlines=False)
    assert len(out) == 2
    assert "вентиляции" in out[1]["summary"] or "1 200 000" in out[1]["summary"]
    assert mock_fetch.await_count == 2


@pytest.mark.asyncio
async def test_only_open_drops_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime, timezone

    past = datetime(2020, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    async def fake_fetch(u: str) -> FetchedTenderPage:
        return _fake_page(u, deadline=past)

    mock_fetch = AsyncMock(side_effect=fake_fetch)
    monkeypatch.setattr(
        "app.services.tender.tender_search_enrich_service.fetch_tender_page",
        mock_fetch,
    )
    items = [
        {"title": "Old", "url": "https://example.com/x", "snippet": "s"},
    ]
    with patch("app.services.tender.tender_search_enrich_service.get_settings") as gs:
        s = gs.return_value
        s.tender_search_enrich_max_pages = 8
        s.tender_search_enrich_with_ai = False
        s.tender_search_enrich_concurrency = 2
        s.tender_search_only_open_deadlines = True
        s.tender_search_exclude_unknown_deadline = False
        out = await enrich_tender_search_results(items, use_ai=False, only_open_deadlines=True)
    assert out == []
    mock_fetch.assert_awaited()


@pytest.mark.asyncio
async def test_mismatch_reg_and_purchase_id_keeps_search_title_and_skips_wrong_subject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When parsed purchase_id disagrees with regNumber in URL, do not overwrite title or AI facts."""

    async def fake_fetch(u: str) -> FetchedTenderPage:
        return FetchedTenderPage(
            url=u,
            final_url=u,
            http_status=200,
            title="t",
            description="Описание с карточки",
            text_excerpt="Текст",
            source_guess="zakupki.gov.ru",
            content_type="text/html",
            application_deadline_utc=None,
            notice_fields={
                "subject": "Чужой предмет закупки",
                "purchase_id": "209150000012600999",
                "customer": "Чужой заказчик",
                "nmck": "9",
            },
        )

    mock_fetch = AsyncMock(side_effect=fake_fetch)
    monkeypatch.setattr(
        "app.services.tender.tender_search_enrich_service.fetch_tender_page",
        mock_fetch,
    )
    items = [
        {
            "title": "Заголовок из поиска",
            "url": (
                "https://zakupki.gov.ru/epz/order/notice/printForm/view/"
                "common-info.html?regNumber=209150000012600162"
            ),
            "snippet": "Кратко из выдачи",
        }
    ]
    with patch("app.services.tender.tender_search_enrich_service.get_settings") as gs:
        s = gs.return_value
        s.tender_search_enrich_max_pages = 8
        s.tender_search_enrich_with_ai = False
        s.tender_search_enrich_concurrency = 2
        s.openai_api_key = None
        s.tender_search_only_open_deadlines = False
        s.tender_search_exclude_unknown_deadline = False
        out = await enrich_tender_search_results(items, use_ai=False, only_open_deadlines=False)
    assert len(out) == 1
    assert out[0]["title"] == "Заголовок из поиска"
    assert "Чужой предмет" not in out[0]["summary"]
    assert "common-info.html" in out[0]["url"]
    assert "209150000012600162" in out[0]["url"]
