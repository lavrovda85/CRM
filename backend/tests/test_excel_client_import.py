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


def test_individual_uses_contact_as_name() -> None:
    headers = [
        "Компания (auto)",
        "Контактное лицо (auto)",
        "Вид клиента физ/юр",
    ]
    col = map_client_columns(headers)
    row = (
        "Случайное имя из файла",
        "Петров П.П.",
        "физ",
    )
    body = row_to_client_create(row, col)
    assert body is not None
    assert body.client_type == "individual"
    assert body.name == "Петров П.П."
    assert body.primary_contact_name == "Петров П.П."


def test_empty_company_uses_address_as_name_individual() -> None:
    """No company + address: physical person, name is the address text (collapsed)."""
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
        "",
        "Игнор",
        "ул. Ленина 1, офис 2\nдоп. строка",
        "+7 900 000-00-00",
        "",
        "юр",
    )
    body = row_to_client_create(row, col)
    assert body is not None
    assert body.name == "ул. Ленина 1, офис 2 доп. строка"
    assert "доп. строка" in (body.address or "")
    assert body.client_type == "individual"
    assert body.primary_contact_name == "Игнор"


def test_empty_company_and_address_use_contact_name() -> None:
    """When company and address are empty, use the contact person column as the client name."""
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
        "",
        "Сидоров С.С.",
        "",
        "+7 900 111-22-33",
        "",
        "юр",
    )
    body = row_to_client_create(row, col)
    assert body is not None
    assert body.name == "Сидоров С.С."
    assert body.client_type == "organization"
    assert body.primary_contact_name == "Сидоров С.С."
