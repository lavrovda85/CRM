"""MCP tools for CRM operations (clients and deals).

Uses the same persistence rules as ``/api/v1/clients`` and ``/api/v1/deals``.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import or_, select, update

from app.core.database import async_session_factory
from app.core.exceptions import NotFoundError, ValidationError
from app.mcp.actor_context import resolve_mcp_actor_users_table_id
from app.mcp.server import mcp
from app.models import Client, ClientContact, Deal, DealStage
from app.schemas.client import ClientCreate
from app.schemas.deal import DealResponse
from app.services import company_service
from app.services.client_payload import build_client_response, extra_data_for_create


def _uuid(raw: str, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(raw).strip())
    except ValueError as exc:
        raise ValidationError(field, "Must be a valid UUID") from exc


@mcp.tool()
async def create_client(
    name: str,
    client_type: str = "individual",
    address: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    inn: str | None = None,
    primary_contact_name: str | None = None,
    kpp: str | None = None,
    ogrn: str | None = None,
    ogrnip: str | None = None,
    bik: str | None = None,
    bank_account: str | None = None,
    corr_account: str | None = None,
    bank_name: str | None = None,
) -> dict:
    """Create a new client in the MCP actor's default company."""
    body = ClientCreate(
        name=name.strip(),
        client_type=client_type,
        address=address,
        phone=phone,
        email=email,
        inn=inn,
        primary_contact_name=primary_contact_name,
        kpp=kpp,
        ogrn=ogrn,
        ogrnip=ogrnip,
        bik=bik,
        bank_account=bank_account,
        corr_account=corr_account,
        bank_name=bank_name,
    )
    async with async_session_factory() as session:
        uid = await resolve_mcp_actor_users_table_id(session)
        company_id = await company_service.get_default_or_first_company_id(session, uid)
        extra = extra_data_for_create(body)
        client = Client(
            company_id=company_id,
            name=body.name,
            client_type=body.client_type,
            address=body.address,
            coordinates=body.coordinates,
            phone=body.phone,
            email=body.email,
            inn=body.inn,
            extra_data=extra,
            notes=body.notes,
        )
        session.add(client)
        await session.flush()
        pc = (body.primary_contact_name or "").strip()
        if pc:
            session.add(
                ClientContact(
                    client_id=client.id,
                    full_name=pc[:255],
                    is_primary=True,
                )
            )
        await session.flush()
        await session.refresh(client, attribute_names=["contacts"])
        await session.commit()
        return build_client_response(client).model_dump(mode="json")


@mcp.tool()
async def search_clients(
    query: str,
    limit: int = 20,
) -> list[dict]:
    """Search clients by name, phone, or email (case-insensitive)."""
    q = (query or "").strip()
    if not q:
        raise ValidationError("query", "Search query must not be empty")
    lim = max(1, min(int(limit), 100))
    pattern = f"%{q}%"

    async with async_session_factory() as session:
        uid = await resolve_mcp_actor_users_table_id(session)
        company_id = await company_service.get_default_or_first_company_id(session, uid)
        stmt = (
            select(Client)
            .where(
                Client.company_id == company_id,
                or_(
                    Client.name.ilike(pattern),
                    Client.phone.ilike(pattern),
                    Client.email.ilike(pattern),
                ),
            )
            .order_by(Client.name)
            .limit(lim)
        )
        res = await session.execute(stmt)
        rows = res.scalars().all()

    return [build_client_response(c).model_dump(mode="json") for c in rows]


async def _default_deal_stage_id(session) -> uuid.UUID:
    res = await session.execute(select(DealStage).order_by(DealStage.order.asc()).limit(1))
    stage = res.scalar_one_or_none()
    if stage is None:
        raise ValidationError(
            "pipeline",
            "No deal stages configured; create stages via admin/REST first",
        )
    return stage.id


@mcp.tool()
async def create_deal(
    client_id: str,
    title: str,
    amount: float = 0.0,
    stage_id: str | None = None,
) -> dict:
    """Create a deal; uses first pipeline stage when ``stage_id`` is omitted."""
    cid = _uuid(client_id, "client_id")
    clean_title = (title or "").strip()
    if not clean_title:
        raise ValidationError("title", "Deal title must not be empty")

    async with async_session_factory() as session:
        client_row = await session.get(Client, cid)
        if client_row is None:
            raise NotFoundError("Client", client_id)

        if stage_id and str(stage_id).strip():
            sid = _uuid(stage_id, "stage_id")
            st = await session.get(DealStage, sid)
            if st is None:
                raise NotFoundError("DealStage", stage_id)
        else:
            sid = await _default_deal_stage_id(session)

        deal = Deal(
            client_id=cid,
            title=clean_title,
            amount=Decimal(str(amount)),
            stage_id=sid,
        )
        session.add(deal)
        await session.flush()
        await session.refresh(deal)
        await session.commit()
        return DealResponse.model_validate(deal).model_dump(mode="json")


@mcp.tool()
async def move_deal(
    deal_id: str,
    stage_id: str,
) -> dict:
    """Move a deal to another pipeline stage."""
    did = _uuid(deal_id, "deal_id")
    sid = _uuid(stage_id, "stage_id")

    async with async_session_factory() as session:
        deal = await session.get(Deal, did)
        if deal is None:
            raise NotFoundError("Deal", deal_id)
        stage = await session.get(DealStage, sid)
        if stage is None:
            raise NotFoundError("DealStage", stage_id)

        from_stage_id = deal.stage_id
        from_stage = await session.get(DealStage, from_stage_id)
        await session.execute(update(Deal).where(Deal.id == did).values(stage_id=sid))
        await session.flush()
        await session.refresh(deal)
        await session.commit()

        to_stage = stage
    return {
        "id": str(deal.id),
        "title": deal.title,
        "from_stage": from_stage.name if from_stage else str(from_stage_id),
        "to_stage": to_stage.name,
        "moved_at": deal.updated_at.isoformat() if deal.updated_at else None,
    }
