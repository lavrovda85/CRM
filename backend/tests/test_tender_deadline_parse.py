"""Unit tests for tender deadline extraction from HTML."""

from datetime import timezone

from app.services.tender.tender_deadline_parse import extract_application_deadline_utc_from_html


def test_extract_deadline_from_labeled_table_row() -> None:
    html = """<html><body><table>
    <tr><td>Дата окончания срока подачи заявок</td><td>15.04.2026</td></tr>
    </table></body></html>"""
    got = extract_application_deadline_utc_from_html(html)
    assert got is not None
    assert got.tzinfo == timezone.utc
    # Date-only: end of day MSK -> UTC same calendar date or +1 depending on MSK; April is MSK+3
    assert got.year == 2026 and got.month == 4 and got.day == 15


def test_extract_deadline_with_time() -> None:
    html = """<div>Окончание подачи заявок 20.12.2027 14:30</div>"""
    got = extract_application_deadline_utc_from_html(html)
    assert got is not None
    assert got.year == 2027 and got.month == 12 and got.day == 20


def test_prefers_submission_deadline_over_certificate_row() -> None:
    html = """<html><body><table>
    <tr><td>Срок действия сертификата</td><td>12.09.2025</td></tr>
    <tr><td>Дата окончания срока подачи заявок</td><td>15.11.2026 18:00</td></tr>
    </table></body></html>"""
    got = extract_application_deadline_utc_from_html(html)
    assert got is not None
    assert got.year == 2026 and got.month == 11 and got.day == 15


def test_extract_deadline_from_blockinfo_section() -> None:
    html = """<html><body>
    <section class="blockInfo__section">
      <span class="section__title">Дата и время окончания срока подачи заявок</span>
      <span class="section__info">
        10.04.2026 08:00 <span class="timeZoneName">(МСК+4)</span>
      </span>
    </section>
    </body></html>"""
    got = extract_application_deadline_utc_from_html(html)
    assert got is not None
    assert got.year == 2026 and got.month == 4 and got.day == 10


def test_certificate_only_does_not_yield_deadline() -> None:
    html = """<html><body><table>
    <tr><td>Срок действия сертификата</td><td>12.09.2025</td></tr>
    </table></body></html>"""
    assert extract_application_deadline_utc_from_html(html) is None
