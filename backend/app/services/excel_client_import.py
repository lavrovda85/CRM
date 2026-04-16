"""Heuristic import of HVAC-style client Excel sheets (Russian headers).

Maps typical columns: тип клиента, наименование/объект, контакты, дата, вид работ, оборудование.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Client
from app.schemas.client import ClientCreate

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
        if _match_field(
            h,
            ("тип клиента", "юр/физ", "юр", "физ", "вид клиента"),
        ) and "client_type" not in fields:
            fields["client_type"] = idx
        elif _match_field(
            h,
            ("наименование", "объект", "название", "организация", "клиент", "адрес"),
        ) and "name" not in fields:
            fields["name"] = idx
        elif _match_field(h, ("контакт", "телефон", "email", "связь", "почта")) and "contacts" not in fields:
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


def _client_type_from_cell(raw: str) -> str:
    s = raw.lower()
    if any(x in s for x in ("юр", "ооо", "организац", "company", "organization")):
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
    # First line as display name, rest as address hint
    lines = [ln.strip() for ln in name_raw.splitlines() if ln.strip()]
    name = lines[0][:500] if lines else ""
    address = ""
    if len(lines) > 1:
        address = "\n".join(lines[1:])[:4000]
    elif len(name_raw) > 200:
        # Long single line: keep as name, duplicate nothing
        name = name_raw[:500]

    ctype = _client_type_from_cell(get("client_type")) if "client_type" in col else "individual"
    blob = get("contacts")
    phone, email = _extract_phone_email(blob)

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
    if not rows:
        return 0, 0, []

    header_idx = find_client_header_row(rows)
    if header_idx is None:
        return 0, 0, [f"Sheet {sheet_name!r}: no client header row detected"]

    header_cells = rows[header_idx]
    headers = [_norm_cell(c) for c in header_cells]
    col = map_client_columns(headers)
    if "name" not in col:
        # Fallback: use widest text column as name
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

            # Dedup: same phone or email or exact name
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

            client = Client(
                company_id=company_id,
                name=body.name,
                client_type=body.client_type,
                address=body.address,
                coordinates=body.coordinates,
                phone=body.phone,
                email=body.email,
                inn=body.inn,
                extra_data=body.extra_data,
                notes=body.notes,
            )
            db.add(client)
            await db.flush()
            created += 1
        except Exception as exc:
            errors.append(f"{sheet_name} row {ridx}: {exc}")
            skipped += 1

    return created, skipped, errors
