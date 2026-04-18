"""Helpers for client legal fields stored in ``Client.extra_data`` JSON."""

from __future__ import annotations

from typing import Any

from app.schemas.client import ClientContactResponse, ClientCreate, ClientResponse, ClientUpdate

_LEGAL_KEYS = (
    "kpp",
    "ogrn",
    "ogrnip",
    "bik",
    "bank_account",
    "corr_account",
    "bank_name",
)


def merge_legal_into_extra_data(
    extra: dict[str, Any] | None,
    *,
    kpp: str | None = None,
    ogrn: str | None = None,
    ogrnip: str | None = None,
    bik: str | None = None,
    bank_account: str | None = None,
    corr_account: str | None = None,
    bank_name: str | None = None,
) -> dict[str, Any]:
    """Merge optional legal requisites into ``extra_data`` (non-empty strings only)."""
    out: dict[str, Any] = dict(extra or {})
    for key, raw in (
        ("kpp", kpp),
        ("ogrn", ogrn),
        ("ogrnip", ogrnip),
        ("bik", bik),
        ("bank_account", bank_account),
        ("corr_account", corr_account),
        ("bank_name", bank_name),
    ):
        if raw is None:
            continue
        s = str(raw).strip()
        if not s:
            continue
        out[key] = s[:500]
    return out


def extra_data_for_create(body: ClientCreate) -> dict[str, Any]:
    """Build ``extra_data`` for a new client from body + user ``extra_data``."""
    base = dict(body.extra_data or {})
    return merge_legal_into_extra_data(
        base,
        kpp=body.kpp,
        ogrn=body.ogrn,
        ogrnip=body.ogrnip,
        bik=body.bik,
        bank_account=body.bank_account,
        corr_account=body.corr_account,
        bank_name=body.bank_name,
    )


def extra_data_for_update(
    existing: dict[str, Any] | None,
    body: ClientUpdate,
) -> dict[str, Any] | None:
    """Merge legal fields from ``ClientUpdate`` into existing ``extra_data``."""
    dump = body.model_dump(exclude_unset=True)
    touched_legal = any(k in dump for k in _LEGAL_KEYS)
    if body.extra_data is None and not touched_legal:
        return None
    base = dict(existing or {})
    if body.extra_data is not None:
        base.update(body.extra_data)
    if not touched_legal:
        return base
    return merge_legal_into_extra_data(
        base,
        kpp=body.kpp if "kpp" in dump else None,
        ogrn=body.ogrn if "ogrn" in dump else None,
        ogrnip=body.ogrnip if "ogrnip" in dump else None,
        bik=body.bik if "bik" in dump else None,
        bank_account=body.bank_account if "bank_account" in dump else None,
        corr_account=body.corr_account if "corr_account" in dump else None,
        bank_name=body.bank_name if "bank_name" in dump else None,
    )


def legal_fields_from_extra(extra: dict[str, Any] | None) -> dict[str, str | None]:
    """Extract legal requisites from ``extra_data`` for API responses."""
    ed = extra or {}
    return {
        "kpp": ed.get("kpp") if isinstance(ed.get("kpp"), str) else None,
        "ogrn": ed.get("ogrn") if isinstance(ed.get("ogrn"), str) else None,
        "ogrnip": ed.get("ogrnip") if isinstance(ed.get("ogrnip"), str) else None,
        "bik": ed.get("bik") if isinstance(ed.get("bik"), str) else None,
        "bank_account": ed.get("bank_account") if isinstance(ed.get("bank_account"), str) else None,
        "corr_account": ed.get("corr_account") if isinstance(ed.get("corr_account"), str) else None,
        "bank_name": ed.get("bank_name") if isinstance(ed.get("bank_name"), str) else None,
    }


def build_client_response(client: Any) -> ClientResponse:
    """Map ORM client to API response including legal fields from ``extra_data``."""
    leg = legal_fields_from_extra(client.extra_data)
    contacts = list(client.contacts) if client.contacts is not None else []
    return ClientResponse(
        id=client.id,
        name=client.name,
        client_type=client.client_type,
        address=client.address,
        phone=client.phone,
        email=client.email,
        inn=client.inn,
        kpp=leg.get("kpp"),
        ogrn=leg.get("ogrn"),
        ogrnip=leg.get("ogrnip"),
        bik=leg.get("bik"),
        bank_account=leg.get("bank_account"),
        corr_account=leg.get("corr_account"),
        bank_name=leg.get("bank_name"),
        coordinates=client.coordinates,
        extra_data=dict(client.extra_data or {}),
        notes=client.notes,
        contacts=[ClientContactResponse.model_validate(c) for c in contacts],
        created_at=client.created_at,
        updated_at=client.updated_at,
    )
