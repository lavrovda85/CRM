"""Unit tests for tender page HTML extraction (no network)."""

from app.services.tender.tender_external_service import (
    _extract_from_html,
    _parse_zakupki_extended_search_html,
)


def test_parse_zakupki_extended_search_finds_notice_links() -> None:
    html = """<html><body>
    <a href="/epz/order/notice/ea20/view/common-info.html?regNumber=123">Тестовая закупка</a>
    <a href="https://zakupki.gov.ru/epz/order/notice/zk504/view/common-info.html?regNumber=456">Вторая</a>
    </body></html>"""
    out = _parse_zakupki_extended_search_html(html, 10)
    assert len(out) == 2
    assert "regNumber=123" in out[0]["url"] or "regNumber=123" in out[1]["url"]


def test_extract_from_html_og_title_and_description() -> None:
    html = """<!DOCTYPE html>
<html><head>
<meta property="og:title" content="Официальное оповещение №123" />
<meta property="og:description" content="Описание закупки оборудования." />
<title>Fallback title</title>
</head><body><main><p>Дополнительный текст на странице.</p></main></body></html>"""
    out = _extract_from_html(html, "https://zakupki.gov.ru/epz/order/notice/view.html")
    assert out["title"] == "Официальное оповещение №123"
    assert out["description"] == "Описание закупки оборудования."
    assert out["source_guess"] == "zakupki.gov.ru"
    assert out["text_excerpt"] and "Дополнительный" in out["text_excerpt"]
