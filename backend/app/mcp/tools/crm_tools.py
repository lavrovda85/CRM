"""MCP tools for CRM operations in HVAC CRM/ERP.

Инструменты для управления клиентами и сделками
через MCP-протокол.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from app.mcp.server import mcp


@mcp.tool()
async def create_client(
    name: str,
    client_type: str = "individual",
    address: str | None = None,
    phone: str | None = None,
    email: str | None = None,
) -> dict:
    """Create a new client in the CRM system.

    Создаёт нового клиента (физическое лицо или организацию)
    с контактными данными и адресом.

    Args:
        name (str): Имя клиента или название организации.
        client_type (str): Тип клиента: "individual" (физлицо) или
            "organization" (юрлицо). По умолчанию "individual".
        address (str | None): Адрес клиента / объекта.
        phone (str | None): Контактный телефон.
        email (str | None): Электронная почта.

    Returns:
        dict: Созданный клиент с полями id, name, client_type,
            address, phone, email, created_at.

    Example:
        AI agent: "Добавь нового клиента — ООО 'Комфорт Плюс'"
        >>> create_client(
        ...     name='ООО "Комфорт Плюс"',
        ...     client_type="organization",
        ...     address="г. Москва, ул. Ленина, д. 15",
        ...     phone="+7 (495) 123-45-67",
        ...     email="info@comfortplus.ru",
        ... )
    """
    # TODO: INSERT INTO clients (name, client_type, address, phone, email)
    # TODO: Check for DuplicateError by phone/email
    client_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    return {
        "id": client_id,
        "name": name,
        "client_type": client_type,
        "address": address,
        "phone": phone,
        "email": email,
        "created_at": now,
    }


@mcp.tool()
async def search_clients(
    query: str,
    limit: int = 20,
) -> list[dict]:
    """Search clients by name, phone, email, or address.

    Выполняет полнотекстовый поиск клиентов по имени, телефону,
    email или адресу. Результаты ранжируются по релевантности.

    Args:
        query (str): Поисковый запрос (имя, телефон, email или часть адреса).
        limit (int): Максимальное количество результатов. По умолчанию 20.

    Returns:
        list[dict]: Список найденных клиентов, каждый содержит id, name,
            client_type, phone, email, address.

    Example:
        AI agent: "Найди клиента по номеру +7 (495) 123"
        >>> search_clients(query="+7 (495) 123", limit=5)
    """
    # TODO: SELECT * FROM clients WHERE name ILIKE %query%
    #       OR phone ILIKE %query% OR email ILIKE %query%
    #       OR address ILIKE %query%
    # TODO: ORDER BY relevance, LIMIT min(limit, 100)
    return [
        {
            "id": str(uuid.uuid4()),
            "name": f"Placeholder for '{query}'",
            "client_type": "individual",
            "phone": None,
            "email": None,
            "address": None,
        }
    ]


@mcp.tool()
async def create_deal(
    client_id: str,
    title: str,
    amount: float = 0.0,
    stage_id: str | None = None,
) -> dict:
    """Create a new deal in the CRM sales pipeline.

    Создаёт новую сделку в воронке продаж, привязанную к клиенту.
    Если stage_id не указан, сделка помещается в первую стадию воронки.

    Args:
        client_id (str): UUID клиента.
        title (str): Название сделки
            (например, "Монтаж VRF-системы — ТЦ Горизонт").
        amount (float): Сумма сделки в рублях. По умолчанию 0.
        stage_id (str | None): UUID стадии воронки. Если не указан —
            используется первая стадия (по order).

    Returns:
        dict: Созданная сделка с полями id, client_id, title,
            amount, stage_id, stage_name, created_at.

    Example:
        AI agent: "Создай сделку на 150 000 руб. для клиента"
        >>> create_deal(
        ...     client_id="client-uuid-...",
        ...     title="Монтаж сплит-системы — кв. Иванов",
        ...     amount=150000.0,
        ... )
    """
    # TODO: Validate client_id exists
    # TODO: If stage_id is None, SELECT first DealStage by order
    # TODO: INSERT INTO deals (client_id, title, amount, stage_id)
    deal_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    return {
        "id": deal_id,
        "client_id": client_id,
        "title": title,
        "amount": amount,
        "stage_id": stage_id or "first-stage-placeholder",
        "stage_name": "New",
        "created_at": now,
    }


@mcp.tool()
async def move_deal(
    deal_id: str,
    stage_id: str,
) -> dict:
    """Move a deal to a different pipeline stage.

    Перемещает сделку на новую стадию воронки продаж.
    Можно перемещать как вперёд, так и назад.

    Args:
        deal_id (str): UUID сделки.
        stage_id (str): UUID целевой стадии воронки.

    Returns:
        dict: Обновлённая сделка с полями id, title, from_stage, to_stage,
            moved_at.

    Example:
        AI agent: "Переведи сделку на стадию 'Согласование договора'"
        >>> move_deal(
        ...     deal_id="deal-uuid-...",
        ...     stage_id="stage-uuid-agreement",
        ... )
    """
    # TODO: SELECT deal by deal_id, raise NotFoundError if absent
    # TODO: SELECT target DealStage by stage_id
    # TODO: UPDATE deals SET stage_id = stage_id WHERE id = deal_id
    now = datetime.utcnow().isoformat()
    return {
        "id": deal_id,
        "title": "Placeholder deal",
        "from_stage": "previous-stage-placeholder",
        "to_stage": stage_id,
        "moved_at": now,
    }
