"""Heuristic import of HVAC-style client Excel sheets (Russian headers).

Maps columns including «(auto)» normalized exports: компания, контакт, адрес, телефоны, email,
вид клиента, ИНН/КПП/ОГРН, and legacy combined «контакты» cells.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.client import ClientCreate
from app.services.client_payload import extra_data_for_create

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s().\-]{8,}\d)")


def _norm_cell(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%d.%m.%Y")
    s = str(v).replace("\xa0", " ").strip()
    return s


def _norm_header(h: object) -> str:
    return _norm_cell(h).lower()


def score_client_header_row(row: tuple[Any, ...]) -> int:
    """Higher score = more likely a header row for client base."""
    parts = [_norm_header(c) for c in row if c is not None]
    joined = " ".join(parts)
    keywords = (
        "наименование",
        "объект",
        "контакт",
        "телефон",
        "email",
        "адрес",
        "тип клиента",
        "юр",
        "физ",
        "дата",
        "вид работ",
        "оборудование",
        "коммент",
        "исполнитель",
        "п/п",
        "№",
        "компания",
        "auto",
        "почт",
        "инн",
        "кпп",
        "огрн",
    )
    return sum(1 for kw in keywords if kw in joined)


def find_client_header_row(rows: list[tuple[Any, ...]], max_scan: int = 20) -> int | None:
    best_idx: int | None = None
    best_score = 0
    for i, row in enumerate(rows[:max_scan]):
        sc = score_client_header_row(row)
        if sc > best_score:
            best_score = sc
            best_idx = i
    if best_idx is None or best_score < 3:
        return None
    return best_idx


def _match_field(header: str, aliases: tuple[str, ...]) -> bool:
    h = header.strip().lower()
    return any(a in h for a in aliases)


def map_client_columns(headers: list[str]) -> dict[str, int]:
    """Map logical field -> column index (best effort)."""
    fields: dict[str, int] = {}

    for idx, raw in enumerate(headers):
        h = _norm_header(raw)
        if not h:
            continue
        low = raw.lower() if isinstance(raw, str) else str(raw).lower()
        if "(auto)" in low or "（auto）" in low:
            if "компания" in h and "name" not in fields:
                fields["name"] = idx
            elif "контакт" in h and "лицо" in h and "contact_person" not in fields:
                fields["contact_person"] = idx
            elif "адрес" in h and "address_only" not in fields:
                fields["address_only"] = idx
            elif "телефон" in h and "phones" not in fields:
                fields["phones"] = idx
            elif "email" in h and "email_col" not in fields:
                fields["email_col"] = idx

    for idx, raw in enumerate(headers):
        h = _norm_header(raw)
        if not h:
            continue
        if _match_field(
            h,
            ("тип клиента", "юр/физ", "вид клиента", "физ/юр"),
        ) and "client_type" not in fields:
            fields["client_type"] = idx
        elif _match_field(h, ("инн", "inn")) and "inn" not in fields:
            fields["inn"] = idx
        elif ("кпп" in h or "kpp" in h) and "kpp" not in fields:
            fields["kpp"] = idx
        elif ("огрнип" in h or "ogrnip" in h) and "ogrnip" not in fields:
            fields["ogrnip"] = idx
        elif ("огрн" in h or "ogrn" in h) and "ogrn" not in fields:
            fields["ogrn"] = idx
        elif ("бик" in h or "bik" in h) and "bik" not in fields:
            fields["bik"] = idx
        elif _match_field(h, ("р/с", "р/сч", "расчетный сч", "рс ", "р с ")) and "bank_account" not in fields:
            fields["bank_account"] = idx
        elif _match_field(h, ("к/с", "к/сч", "корр", "кс ")) and "corr_account" not in fields:
            fields["corr_account"] = idx
        elif "банк" in h and "bank_name" not in fields and "бик" not in h:
            fields["bank_name"] = idx
        elif _match_field(
            h,
            ("наименование", "объект", "название", "организация", "клиент"),
        ) and "name" not in fields:
            fields["name"] = idx
        elif ("лицо" in h and "контакт" in h) and "contact_person" not in fields:
            fields["contact_person"] = idx
        elif _match_field(h, ("фио контакт",)) and "contact_person" not in fields:
            fields["contact_person"] = idx
        elif _match_field(h, ("адрес",)) and "address_only" not in fields and "email" not in h:
            fields["address_only"] = idx
        elif _match_field(h, ("телефон", "тел.", "моб")) and "phones" not in fields:
            fields["phones"] = idx
        elif _match_field(h, ("email", "e-mail", "почта", "mail")) and "email_col" not in fields:
            fields["email_col"] = idx
        elif (
            _match_field(h, ("телефон", "email", "связь", "почта"))
            or ("контакт" in h and "лицо" not in h)
        ) and "contacts" not in fields:
            fields["contacts"] = idx
        elif _match_field(h, ("дата",)) and "event_date" not in fields:
            fields["event_date"] = idx
        elif _match_field(h, ("вид работ", "тип работ", "работы")) and "work_type" not in fields:
            fields["work_type"] = idx
        elif _match_field(h, ("оборудование", "модель", "бренд")) and "equipment" not in fields:
            fields["equipment"] = idx
        elif _match_field(h, ("коммент", "исполнитель", "примечание")) and "extra" not in fields:
            fields["extra"] = idx
    return fields


def _extract_phone_email(blob: str) -> tuple[str | None, str | None]:
    if not blob:
        return None, None
    em = _EMAIL_RE.search(blob)
    email = em.group(0) if em else None
    phone = None
    for m in _PHONE_RE.finditer(blob):
        raw = re.sub(r"\s+", " ", m.group(0).strip())
        digits = re.sub(r"\D", "", raw)
        if len(digits) >= 10:
            phone = raw[:50]
            break
    return phone, email


def _extract_email_only(blob: str) -> str | None:
    if not blob:
        return None
    em = _EMAIL_RE.search(blob)
    return em.group(0) if em else None


def _client_type_from_cell(raw: str) -> str:
    s = raw.lower().strip()
    if any(x in s for x in ("юр", "ооо", "организац", "company", "organization", "legal")):
        return "organization"
    if any(x in s for x in ("физ", "individual", "частн")):
        return "individual"
    if "ип" in s and len(s) <= 40:
        return "organization"
    return "individual"


def row_to_client_create(
    row: tuple[Any, ...],
    col: dict[str, int],
) -> ClientCreate | None:
    """Build ClientCreate from a data row; return None to skip."""
    def get(field: str) -> str:
        i = col.get(field)
        if i is None or i >= len(row):
            return ""
        return _norm_cell(row[i])

    name_raw = get("name")
    if not name_raw:
        return None
    lines = [ln.strip() for ln in name_raw.splitlines() if ln.strip()]
    name = lines[0][:500] if lines else ""
    address = ""
    if "address_only" in col:
        address = get("address_only")[:4000]
    elif len(lines) > 1:
        address = "\n".join(lines[1:])[:4000]
    elif len(name_raw) > 200:
        name = name_raw[:500]

    ctype = _client_type_from_cell(get("client_type")) if "client_type" in col else "individual"

    phone: str | None = None
    email: str | None = None

    if "phones" in col:
        pb = get("phones")
        phone, em_ph = _extract_phone_email(pb)
        if not email:
            email = em_ph

    blob = get("contacts")
    if not phone:
        phone, em_c = _extract_phone_email(blob)
        if not email:
            email = em_c
    if not email and "email_col" in col:
        email = _extract_email_only(get("email_col"))
    if not email and blob:
        email = _extract_email_only(blob)

    contact_person = get("contact_person") if "contact_person" in col else ""
    primary_contact_name = contact_person.strip()[:255] if contact_person.strip() else None
    if ctype == "individual" and isinstance(primary_contact_name, str):
        # For physical persons, keep client display name equal to the contact person.
        name = primary_contact_name[:500]

    inn = get("inn").strip()[:20] if get("inn") else None
    kpp = get("kpp").strip()[:20] if get("kpp") else None
    ogrn = get("ogrn").strip()[:20] if get("ogrn") else None
    ogrnip = get("ogrnip").strip()[:20] if get("ogrnip") else None
    bik = get("bik").strip()[:20] if get("bik") else None
    bank_account = get("bank_account").strip()[:50] if get("bank_account") else None
    corr_account = get("corr_account").strip()[:50] if get("corr_account") else None
    bank_name = get("bank_name").strip()[:500] if get("bank_name") else None

    parts_notes: list[str] = []
    if get("event_date"):
        parts_notes.append(f"Дата (из файла): {get('event_date')}")
    if get("work_type"):
        parts_notes.append(f"Вид работ: {get('work_type')}")
    if get("equipment"):
        parts_notes.append(f"Оборудование: {get('equipment')}")
    if get("extra"):
        parts_notes.append(get("extra"))
    notes = "\n".join(parts_notes) if parts_notes else None

    extra: dict[str, Any] = {"import_source": "excel_unified"}
    if get("work_type"):
        extra["work_type"] = get("work_type")[:500]
    if get("equipment"):
        extra["equipment"] = get("equipment")[:500]

    return ClientCreate(
        name=name or "Без названия",
        client_type=ctype,
        address=address or None,
        phone=phone,
        email=email,
        inn=inn or None,
        primary_contact_name=primary_contact_name,
        kpp=kpp or None,
        ogrn=ogrn or None,
        ogrnip=ogrnip or None,
        bik=bik or None,
        bank_account=bank_account or None,
        corr_account=corr_account or None,
        bank_name=bank_name or None,
        extra_data=extra,
        notes=notes,
    )


async def import_clients_from_sheet(
    db: AsyncSession,
    *,
    company_id: uuid.UUID,
    rows: list[tuple[Any, ...]],
    sheet_name: str,
) -> tuple[int, int, list[str]]:
    """Import client rows from one worksheet. Returns (created, skipped, errors)."""
    from app.models import Client, ClientContact

    if not rows:
        return 0, 0, []

    header_idx = find_client_header_row(rows)
    if header_idx is None:
        return 0, 0, [f"Sheet {sheet_name!r}: no client header row detected"]

    header_cells = rows[header_idx]
    headers = [_norm_cell(c) for c in header_cells]
    col = map_client_columns(headers)
    if "name" not in col:
        best_j = None
        best_len = 0
        sample = rows[header_idx + 1 : header_idx + 4] if len(rows) > header_idx + 1 else []
        for j in range(len(headers)):
            tot = 0
            for sr in sample:
                if j < len(sr) and sr[j] is not None:
                    tot += len(str(sr[j]))
            if tot > best_len:
                best_len = tot
                best_j = j
        if best_j is not None:
            col["name"] = best_j

    if "name" not in col:
        return 0, 0, [f"Sheet {sheet_name!r}: could not detect name column"]

    created = 0
    skipped = 0
    errors: list[str] = []

    for ridx, row in enumerate(rows[header_idx + 1 :], start=header_idx + 2):
        try:
            body = row_to_client_create(row, col)
            if body is None:
                skipped += 1
                continue

            dup = False
            if body.phone:
                q = await db.execute(
                    select(Client.id).where(
                        Client.company_id == company_id,
                        Client.phone == body.phone,
                    ).limit(1)
                )
                dup = q.scalar_one_or_none() is not None
            if not dup and body.email:
                q = await db.execute(
                    select(Client.id).where(
                        Client.company_id == company_id,
                        Client.email == body.email,
                    ).limit(1)
                )
                dup = q.scalar_one_or_none() is not None
            if not dup:
                q = await db.execute(
                    select(Client.id).where(
                        Client.company_id == company_id,
                        Client.name == body.name,
                    ).limit(1)
                )
                dup = q.scalar_one_or_none() is not None

            if dup:
                skipped += 1
                continue

            extra_merged = extra_data_for_create(body)
            client = Client(
                company_id=company_id,
                name=body.name,
                client_type=body.client_type,
                address=body.address,
                coordinates=body.coordinates,
                phone=body.phone,
                email=body.email,
                inn=body.inn,
                extra_data=extra_merged,
                notes=body.notes,
            )
            db.add(client)
            await db.flush()
            pc = (body.primary_contact_name or "").strip()
            if pc:
                db.add(
                    ClientContact(
                        client_id=client.id,
                        full_name=pc[:255],
                        is_primary=True,
                    )
                )
            created += 1
        except Exception as exc:
            errors.append(f"{sheet_name} row {ridx}: {exc}")
            skipped += 1

    return created, skipped, errors
