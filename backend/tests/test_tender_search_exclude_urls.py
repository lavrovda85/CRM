"""Tests for tender search URL exclusion and deduplication."""

from app.services.tender.tender_external_service import _exclude_url_set, _normalize_url_for_search_dedup


def test_normalize_zakupki_printform_and_common_info_match() -> None:
    a = "https://zakupki.gov.ru/epz/order/notice/printForm/view/common-info.html?regNumber=0119200000126005521"
    b = "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0119200000126005521"
    assert _normalize_url_for_search_dedup(a) == _normalize_url_for_search_dedup(b)


def test_exclude_url_set_dedupes_canonical() -> None:
    a = "https://zakupki.gov.ru/epz/order/notice/printForm/view/common-info.html?regNumber=0119200000126005521"
    b = "https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=0119200000126005521"
    s = _exclude_url_set([a, b])
    assert len(s) == 1
