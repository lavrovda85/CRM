"""Tests for Excel client column mapping and row parsing."""

from app.services.excel_client_import import map_client_columns, row_to_client_create


def test_map_auto_columns() -> None:
    headers = [
        "Компания (auto)",
        "Контактное лицо (auto)",
        "Адрес (auto)",
        "Телефоны (auto)",
        "Email (auto)",
        "Вид клиента физ/юр",
    ]
    col = map_client_columns(headers)
    assert col.get("name") == 0
    assert col.get("contact_person") == 1
    assert col.get("address_only") == 2
    assert col.get("phones") == 3
    assert col.get("email_col") == 4
    assert col.get("client_type") == 5


def test_row_parsing_auto_sheet() -> None:
    headers = [
        "Компания (auto)",
        "Контактное лицо (auto)",
        "Адрес (auto)",
        "Телефоны (auto)",
        "Email (auto)",
        "Вид клиента физ/юр",
    ]
    col = map_client_columns(headers)
    row = (
        "ООО Ромашка",
        "Иванов И.И.",
        "ул. Пушкина 10",
        "+7 912 345-67-89",
        "ivan@example.com",
        "юр",
    )
    body = row_to_client_create(row, col)
    assert body is not None
    assert body.name == "ООО Ромашка"
    assert body.client_type == "organization"
    assert body.address == "ул. Пушкина 10"
    assert body.phone is not None and "912" in body.phone
    assert body.email == "ivan@example.com"
    assert body.primary_contact_name == "Иванов И.И."


def test_ogrnip_before_ogrn_headers() -> None:
    headers = ["ОГРНИП", "ОГРН"]
    col = map_client_columns(headers)
    assert col.get("ogrnip") == 0
    assert col.get("ogrn") == 1
