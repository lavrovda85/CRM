"""Zakupki URL canonicalization and notice field extraction."""

from app.services.tender.tender_notice_fields import extract_zakupki_notice_fields
from app.services.tender.tender_zakupki_urls import (
    canonical_zakupki_notice_url,
    extract_reg_number_from_zakupki_html,
    reg_number_from_zakupki_url,
    zakupki_common_info_url,
    zakupki_reg_numbers_equivalent,
)


def test_extract_reg_number_from_zakupki_html() -> None:
    html = '<a href="/epz/order/notice/ea20/view/common-info.html?regNumber=0119300004425000073">x</a>'
    assert extract_reg_number_from_zakupki_html(html) == "0119300004425000073"


def test_zakupki_common_info_url() -> None:
    u = zakupki_common_info_url("0119300004425000073", "ea20")
    assert "common-info.html" in u
    assert "regNumber=0119300004425000073" in u


def test_regex_fallback_fills_nmck_when_no_sections() -> None:
    html = (
        "<html><body>Шум до "
        "Начальная (максимальная) цена контракта</td><td>9 999 111,50 руб."
        "</body></html>"
    )
    zf = extract_zakupki_notice_fields(html)
    assert zf.nmck and "9" in zf.nmck


def test_reg_number_from_zakupki_url() -> None:
    u = "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=209150000012600162"
    assert reg_number_from_zakupki_url(u) == "209150000012600162"


def test_zakupki_reg_numbers_equivalent_ignores_formatting() -> None:
    assert zakupki_reg_numbers_equivalent("209150000012600162", "209 150 000012600162") is True
    assert zakupki_reg_numbers_equivalent("209150000012600162", "111") is False


def test_canonical_zakupki_notice_url_rewrites_to_common_info() -> None:
    u = "https://zakupki.gov.ru/epz/order/notice/ea20/view/documents.html?regNumber=0119300004425000073"
    got = canonical_zakupki_notice_url(u)
    assert "common-info.html" in got
    assert "regNumber=0119300004425000073" in got


def test_extract_notice_fields_modern_eis_blockinfo() -> None:
    """ЕИС common-info uses section__title / section__info (not only tables)."""
    html = (
        "<html><body>"
        '<section class="blockInfo__section section">'
        '<span class="section__title">\u041d\u0430\u0447\u0430\u043b\u044c\u043d\u0430\u044f '
        "(\u043c\u0430\u043a\u0441\u0438\u043c\u0430\u043b\u044c\u043d\u0430\u044f) "
        "\u0446\u0435\u043d\u0430 \u043a\u043e\u043d\u0442\u0440\u0430\u043a\u0442\u0430</span>"
        '<span class="section__info">64 145,12</span>'
        "</section>"
        '<section class="blockInfo__section section">'
        '<span class="section__title">\u041d\u043e\u043c\u0435\u0440 '
        "\u043a\u043e\u043d\u0442\u0430\u043a\u0442\u043d\u043e\u0433\u043e "
        '\u0442\u0435\u043b\u0435\u0444\u043e\u043d\u0430</span>'
        '<span class="section__info">8-391-2225569</span>'
        "</section>"
        "</body></html>"
    )
    zf = extract_zakupki_notice_fields(html)
    assert zf.nmck and "64" in zf.nmck
    assert zf.phones and "2225569" in zf.phones


def test_extract_notice_fields_from_table() -> None:
    html = """<html><body><table>
    <tr><td>Наименование объекта закупки</td><td>Монтаж системы вентиляции здания</td></tr>
    <tr><td>Заказчик</td><td>Администрация района</td></tr>
    <tr><td>Начальная (максимальная) цена контракта</td><td>1 234 567,89 руб.</td></tr>
    </table></body></html>"""
    zf = extract_zakupki_notice_fields(html)
    assert "вентиляции" in (zf.subject or "")
    assert zf.customer and "Администрация" in zf.customer
    assert zf.nmck and "1 234" in zf.nmck
