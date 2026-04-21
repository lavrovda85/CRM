"""MCP tools for task management in SPEC CRM/ERP.

Инструменты для создания, обновления, перехода статусов,
получения списка и деталей задач через MCP-протокол.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo
import httpx

logger = logging.getLogger(__name__)

_MAX_BULK_TASKS = 50
_MOSCOW_TZ = ZoneInfo("Europe/Moscow")

from app.mcp.actor_context import actor_dict_for_service, current_mcp_user, current_mcp_user_sub
from app.mcp.server import mcp
from app.mcp.tools.user_tools import _find_active_users_by_query
from app.core.database import async_session_factory
from app.core.config import get_settings
from app.schemas.task import TaskDetail, TaskResponse
from app.services.task_notification_service import TaskNotificationService
from app.services.task_service import TaskService
from app.services.template_service import TemplateService
from sqlalchemy import select, update as sa_update
from sqlalchemy.orm import selectinload

from app.core.exceptions import HVACBaseError, WorkflowTransitionError
from app.models.checklist import Checklist
from app.models.task import Task
from app.models.task_status import TaskStatusHistory
from app.services.workflow_engine import WorkflowEngine
from app.core.permissions import user_sees_all_company_tasks


def _mcp_user_sees_all_tasks() -> bool:
    """Whether the MCP actor is on the global task visibility allowlist (JWT identity)."""
    return user_sees_all_company_tasks(current_mcp_user())


def _resolve_create_task_title(title: str | None, name: str | None) -> str:
    """Pick a non-empty headline from ``title`` or synonym ``name`` (LLM / MCP clients)."""
    for val in (title, name):
        if val is None:
            continue
        cleaned = str(val).strip()
        if cleaned:
            return cleaned
    return ""


def _parse_due_date_optional(raw: str | None) -> datetime | None:
    """Parse optional due date from ISO 8601 or Russian ``dd.mm.yyyy`` (optional time)."""
    from app.core.exceptions import ValidationError

    if raw is None or not str(raw).strip():
        return None
    s = str(raw).strip()
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        pass
    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            naive = datetime.strptime(s, fmt)
            return naive.replace(tzinfo=_MOSCOW_TZ)
        except ValueError:
            continue
    raise ValidationError("due_date", f"Unrecognized date format: {raw!r}")


# Labels from spreadsheets (team/section headers) that are not CRM users — treat as
# no assignee instead of failing validation when the model maps a column to assigned_to.
_PLACEHOLDER_ASSIGNEE_LABELS: frozenset[str] = frozenset(
    {
        "-",
        "—",
        "–",
        "?",
        "???",
        "n/a",
        "na",
        "tbd",
        "нет",
        "н/д",
        "не указано",
        "отсутствует",
        "без исполнителя",
        "не назначен",
        "не назначено",
        "исполнитель не указан",
        "рабочая группа",
        "производственная группа",
        "монтажная группа",
        "монтажная бригада",
        "производственная бригада",
        "бригада",
        "смр",
        "отдел",
        "участок",
        "требуется назначение",
    }
)
_PLACEHOLDER_GROUP_TAIL = re.compile(
    r"^(рабочая|производственная|монтажная|смр)\s+группа(\s*\d+)?\.?$",
    re.IGNORECASE,
)


def _is_placeholder_assignee_label(raw: str | None) -> bool:
    """Return True if ``raw`` is a team/section label or empty marker, not a person name.

    Used so bulk_create_tasks / create_task can leave tasks unassigned when Excel columns
    contain «Рабочая группа» instead of a user UUID or unique name.
    """
    if raw is None:
        return False
    s = str(raw).strip()
    if not s:
        return True
    key = " ".join(s.lower().replace("ё", "е").split())
    key = key.strip(".")
    if key in _PLACEHOLDER_ASSIGNEE_LABELS:
        return True
    if len(key) <= 2 and key in ("-", "—", "–", "?"):
        return True
    if _PLACEHOLDER_GROUP_TAIL.match(key):
        return True
    return False


async def _resolve_assigned_to_uuid(db: Any, assigned_to: str | None) -> uuid.UUID | None:
    """Resolve ``assigned_to``: valid UUID string, else unique active user match by name substring."""
    from app.core.exceptions import ValidationError

    if assigned_to is None or not str(assigned_to).strip():
        return None
    at = str(assigned_to).strip()
    try:
        return uuid.UUID(at)
    except ValueError:
        pass
    users = await _find_active_users_by_query(db, at, limit=25)
    if not users:
        if _is_placeholder_assignee_label(at):
            return None
        raise ValidationError(
            "assigned_to",
            f"No active user matches «{at}». Pass a user UUID or use assign_task_to_user after create.",
        )
    if len(users) > 1:
        names = ", ".join(u.full_name for u in users[:5])
        raise ValidationError(
            "assigned_to",
            f"Multiple users match «{at}»: {names}. Pass a UUID or narrow the name.",
        )
    return users[0].id


async def _resolve_assignee_from_item(db: Any, item: dict[str, Any]) -> uuid.UUID | None:
    """Resolve assignee for bulk row: UUID in ``assigned_to``, else ``assignee_query``, else name in ``assigned_to``."""
    from app.core.exceptions import ValidationError

    at_raw = item.get("assigned_to")
    at_s = str(at_raw).strip() if at_raw is not None and str(at_raw).strip() else ""
    if at_s:
        try:
            return uuid.UUID(at_s)
        except ValueError:
            pass
    aq_raw = item.get("assignee_query")
    if aq_raw is not None and str(aq_raw).strip():
        q = str(aq_raw).strip()
        users = await _find_active_users_by_query(db, q, limit=25)
        if users:
            if len(users) > 1:
                names = ", ".join(u.full_name for u in users[:5])
                raise ValidationError(
                    "assignee_query",
                    f"Multiple users match «{q}»: {names}.",
                )
            return users[0].id
        if not _is_placeholder_assignee_label(q):
            raise ValidationError("assignee_query", f"No active user matches «{q}».")
    if at_s:
        users = await _find_active_users_by_query(db, at_s, limit=25)
        if users:
            if len(users) > 1:
                names = ", ".join(u.full_name for u in users[:5])
                raise ValidationError(
                    "assigned_to",
                    f"Multiple users match «{at_s}»: {names}.",
                )
            return users[0].id
        if _is_placeholder_assignee_label(at_s):
            return None
        raise ValidationError("assigned_to", f"No active user matches «{at_s}».")
    return None


async def _resolve_single_user_id_by_query(
    db: Any,
    *,
    query: str,
    field_name: str,
) -> uuid.UUID:
    """Resolve exactly one active user by substring query (case-insensitive).

    Raises:
        ValidationError: If no users match or if several users match.
    """
    from app.core.exceptions import ValidationError

    q = (query or "").strip()
    if not q:
        raise ValidationError(field_name, "Empty query")
    users = await _find_active_users_by_query(db, q, limit=25)
    if not users:
        raise ValidationError(field_name, f"No active user matches «{q}».")
    if len(users) > 1:
        names = ", ".join(u.full_name for u in users[:5])
        raise ValidationError(
            field_name,
            f"Multiple active users match «{q}»: {names}. Pass a UUID or narrow the name.",
        )
    return users[0].id


def _parse_uuid_list_field(value: Any, field_name: str) -> list[uuid.UUID]:
    """Parse a list of UUID strings from MCP/JSON input."""
    from app.core.exceptions import ValidationError

    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError(field_name, "Must be a list of UUID strings")
    out: list[uuid.UUID] = []
    for x in value:
        if x is None or (isinstance(x, str) and not str(x).strip()):
            continue
        try:
            out.append(uuid.UUID(str(x).strip()))
        except ValueError as exc:
            raise ValidationError(field_name, f"Invalid UUID: {x!r}") from exc
    return out


async def _resolve_uuid_or_user_query_list_field(
    db: Any,
    value: Any,
    field_name: str,
) -> list[uuid.UUID]:
    """Resolve list entries that can be UUIDs or active users name queries.

    This is a robustness layer for AI/MCP clients that may pass human-readable
    full names into `*_assignee_ids` fields.
    """
    from app.core.exceptions import ValidationError

    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError(field_name, "Must be a list of UUID strings or name queries")

    out: list[uuid.UUID] = []
    for x in value:
        if x is None or (isinstance(x, str) and not str(x).strip()):
            continue
        raw = str(x).strip()
        try:
            out.append(uuid.UUID(raw))
            continue
        except ValueError:
            pass

        users = await _find_active_users_by_query(db, raw, limit=25)
        if not users:
            raise ValidationError(field_name, f"No active user matches «{raw}». Pass UUID instead.")
        if len(users) > 1:
            names = ", ".join(u.full_name for u in users[:5])
            raise ValidationError(
                field_name,
                f"Multiple users match «{raw}»: {names}. Pass UUID or narrow the name.",
            )
        out.append(users[0].id)

    # Keep order, but drop duplicates.
    seen: set[uuid.UUID] = set()
    deduped: list[uuid.UUID] = []
    for uid in out:
        if uid in seen:
            continue
        seen.add(uid)
        deduped.append(uid)
    return deduped


async def _geocode_address(address: str) -> dict[str, Any]:
    """Resolve address via Yandex geocoder; return ambiguity when needed."""
    key = (get_settings().yandex_geocoder_api_key or "").strip()
    if not key:
        return {"ok": False, "code": "AMBIGUOUS_LOCATION", "message": "Set YANDEX_GEOCODER_API_KEY to resolve addresses."}
    url = "https://geocode-maps.yandex.ru/1.x/"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            url,
            params={"apikey": key, "format": "json", "geocode": address, "results": 3},
        )
    data = resp.json()
    members = (
        data.get("response", {})
        .get("GeoObjectCollection", {})
        .get("featureMember", [])
    )
    if not members:
        return {"ok": False, "code": "AMBIGUOUS_LOCATION", "message": f"Address not found: {address}"}
    if len(members) > 1:
        candidates: list[dict[str, Any]] = []
        for it in members[:3]:
            obj = it.get("GeoObject", {})
            pos = (obj.get("Point", {}).get("pos") or "").split()
            if len(pos) != 2:
                continue
            lon, lat = pos
            candidates.append(
                {
                    "address": obj.get("metaDataProperty", {}).get("GeocoderMetaData", {}).get("text"),
                    "latitude": float(lat),
                    "longitude": float(lon),
                }
            )
        return {
            "ok": False,
            "code": "AMBIGUOUS_LOCATION",
            "message": "Address matches multiple locations. Please уточните адрес или передайте координаты.",
            "candidates": candidates,
        }
    obj = members[0].get("GeoObject", {})
    pos = (obj.get("Point", {}).get("pos") or "").split()
    if len(pos) != 2:
        return {"ok": False, "code": "AMBIGUOUS_LOCATION", "message": "Could not parse coordinates from geocoder response."}
    lon, lat = pos
    return {
        "ok": True,
        "address": obj.get("metaDataProperty", {}).get("GeocoderMetaData", {}).get("text") or address,
        "latitude": float(lat),
        "longitude": float(lon),
    }


async def _resolve_geo_payload(
    *,
    address: str | None,
    latitude: float | None,
    longitude: float | None,
    custom_fields: dict | None,
) -> dict[str, Any]:
    """Compose custom_fields with geo and return structured ambiguity if needed."""
    merged = dict(custom_fields or {})
    lat = latitude
    lng = longitude
    addr = address.strip() if isinstance(address, str) else None
    if addr:
        merged["address"] = addr
    if lat is not None:
        merged["latitude"] = float(lat)
    if lng is not None:
        merged["longitude"] = float(lng)
    if addr and (lat is None or lng is None):
        geo = await _geocode_address(addr)
        if geo.get("ok") is not True:
            return geo
        merged["address"] = geo["address"]
        merged["latitude"] = geo["latitude"]
        merged["longitude"] = geo["longitude"]
    if (lat is None) ^ (lng is None):
        return {
            "ok": False,
            "code": "AMBIGUOUS_LOCATION",
            "message": "Provide both latitude and longitude together.",
        }
    return {"ok": True, "custom_fields": merged}


@mcp.tool()
async def create_task(
    title: str | None = None,
    name: str | None = None,
    description: str | None = None,
    template_id: str | None = None,
    client_id: str | None = None,
    assigned_to: str | None = None,
    requested_by: str | None = None,
    co_assignee_ids: Any = None,
    observer_query: str | None = None,
    observer_queries: Any = None,
    observer_ids: Any = None,
    custom_fields: dict | None = None,
    address: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    priority: str = "medium",
    due_date: str | None = None,
    visibility: str = "company",
) -> dict:
    """Create a new task in the SPEC CRM/ERP system.

    Создаёт новую задачу, опционально из шаблона. Если указан template_id,
    задача наследует workflow, чек-листы и обязательные поля из шаблона.

    Args:
        title (str | None): Заголовок задачи. Должен быть непустым (или задайте ``name``).
        name (str | None): Синоним ``title`` для ИИ-агентов, если поле ``title`` не используется.
        template_id (str | None): UUID шаблона задачи. Если указан — задача
            создаётся из шаблона с наследованием workflow и чек-листов.
        client_id (str | None): UUID клиента, к которому привязана задача.
        description (str | None): Текстовое описание (обычная задача или из шаблона).
        assigned_to (str | None): UUID исполнителя или уникальное ФИО/фрагмент имени
            (как у search_users); иначе передайте UUID.
        custom_fields (dict | None): Словарь кастомных полей {key: value}.
        address (str | None): Адрес объекта; при отсутствии координат будет попытка геокодирования.
        latitude (float | None): Широта.
        longitude (float | None): Долгота.
        priority (str): Приоритет задачи: "low", "medium", "high", "critical".
            По умолчанию "medium".
        due_date (str | None): Крайний срок: ISO 8601 или ``dd.mm.yyyy[ HH:MM[:SS]]`` (Europe/Moscow).
        visibility (str): ``company`` (вся компания) или ``participants`` (только исполнители, соисполнители, наблюдатели, создатель, постановщик).
        requested_by (str | None): UUID постановщика (если не задан — только ``created_by`` в БД).
        co_assignee_ids (list | None): UUID соисполнителей (дополнительно к основному исполнителю).
        observer_query (str | None): Подстрока имени наблюдателя для резолва в ``user_id``.
        observer_queries (list | None): Список подстрок для резолва нескольких наблюдателей.
        observer_ids (list | None): UUID наблюдателей (получают уведомления о событиях по задаче).

    Returns:
        dict: Созданная задача с полями id, title, status, priority,
            assigned_to, template_id, client_id, custom_fields,
            due_date, created_at.

    Example:
        AI agent: "Создай задачу на монтаж кондиционера для клиента"
        >>> create_task(
        ...     title="Монтаж кондиционера Daikin FTXB35C",
        ...     template_id="a1b2c3d4-...",
        ...     client_id="e5f6a7b8-...",
        ...     assigned_to="c9d0e1f2-...",
        ...     priority="high",
        ...     due_date="2026-04-15T18:00:00Z",
        ... )
    """
    from app.core.exceptions import ValidationError
    from app.models.task import ALLOWED_TASK_VISIBILITIES

    resolved_title = _resolve_create_task_title(title, name)
    if not resolved_title:
        raise ValidationError("title", "Title is required")

    vis_raw = (visibility or "company").strip()
    if vis_raw not in ALLOWED_TASK_VISIBILITIES:
        raise ValidationError("visibility", "Must be 'company' or 'participants'")

    desc_clean = (description or "").strip() or None
    # Resolve co-observers/assignees later (needs DB for name->UUID).
    co_ids_raw = co_assignee_ids
    obs_ids_raw = observer_ids
    req_by: uuid.UUID | None = None
    if requested_by and str(requested_by).strip():
        req_by = uuid.UUID(str(requested_by).strip())

    geo_payload = await _resolve_geo_payload(
        address=address,
        latitude=latitude,
        longitude=longitude,
        custom_fields=custom_fields,
    )
    if geo_payload.get("ok") is not True:
        return geo_payload

    async with async_session_factory() as db:
        actor = actor_dict_for_service()
        assignee_uuid = await _resolve_assigned_to_uuid(db, assigned_to)

        co_ids = await _resolve_uuid_or_user_query_list_field(db, co_ids_raw, "co_assignee_ids")
        obs_ids = await _resolve_uuid_or_user_query_list_field(db, obs_ids_raw, "observer_ids")

        # Resolve observer ids from human-readable name queries.
        if observer_query and str(observer_query).strip():
            uid = await _resolve_single_user_id_by_query(
                db,
                query=str(observer_query),
                field_name="observer_query",
            )
            if uid not in obs_ids:
                obs_ids.append(uid)

        if observer_queries is not None:
            if not isinstance(observer_queries, list):
                from app.core.exceptions import ValidationError
                raise ValidationError("observer_queries", "observer_queries must be a list of strings")
            for q in observer_queries:
                if q is None or (isinstance(q, str) and not q.strip()):
                    continue
                uid = await _resolve_single_user_id_by_query(
                    db,
                    query=str(q),
                    field_name="observer_queries",
                )
                if uid not in obs_ids:
                    obs_ids.append(uid)

        due_dt = _parse_due_date_optional(due_date)
        cid: uuid.UUID | None = None
        if client_id and str(client_id).strip():
            cid = uuid.UUID(str(client_id).strip())
        if template_id:
            tid_tpl = uuid.UUID(template_id)
            params: dict[str, Any] = {
                "title": resolved_title,
                "description": desc_clean,
                "client_id": cid,
                "assigned_to": assignee_uuid,
                "requested_by": req_by,
                "co_assignee_ids": co_ids,
                "observer_ids": obs_ids,
                "custom_fields": geo_payload["custom_fields"],
                "priority": priority,
                "visibility": vis_raw,
            }
            if due_dt:
                params["due_date"] = due_dt
            task = await TemplateService.instantiate_template(db, tid_tpl, params, actor)
        else:
            payload: dict[str, Any] = {
                "title": resolved_title,
                "description": desc_clean,
                "template_id": None,
                "client_id": cid,
                "assigned_to": assignee_uuid,
                "requested_by": req_by,
                "co_assignee_ids": co_ids,
                "observer_ids": obs_ids,
                "custom_fields": geo_payload["custom_fields"],
                "priority": priority,
                "visibility": vis_raw,
            }
            if due_dt:
                payload["due_date"] = due_dt
            task = await TaskService.create_task(db, payload, actor)
        await db.commit()
        await db.refresh(task)
        # `TaskResponse` uses `assignee` and `template` relations; make sure they're
        # eagerly loaded to avoid `MissingGreenlet` during Pydantic validation.
        task_for_api = await TaskService.get_task(db, task.id, viewer_user_id=actor["id"], user_sees_all=_mcp_user_sees_all_tasks())
        await TaskNotificationService.notify_after_task_created(db, task_for_api, actor["id"])
        return TaskResponse.model_validate(task_for_api).model_dump(mode="json")


@mcp.tool()
async def bulk_create_tasks(
    items: list[dict[str, Any]],
    template_id: str | None = None,
    client_id: str | None = None,
) -> dict[str, Any]:
    """Create many tasks in one call from a list or pasted table (names as assignees supported).

    Use this when the user provides several rows (list, TSV, or table). Do not call ``create_task``
    once per row with a human name in ``assigned_to`` unless rows are few; prefer this tool.

    Args:
        items: List of objects, each with at least ``title`` (or ``name``). Optional per row:
            ``description``, ``due_date`` (ISO or ``dd.mm.yyyy HH:MM:SS``), ``assigned_to`` (UUID
            or unique name), ``assignee_query`` (explicit name lookup), ``priority``, ``custom_fields``,
            ``requested_by`` (UUID), ``co_assignee_ids`` (list of UUID strings), optional
            per-row ``observer_ids`` (list of UUID strings), or ``observer_query`` /
            ``observer_queries`` name-based resolvers.
        template_id: Optional shared template UUID for every row.
        client_id: Optional shared client UUID for every row.

    Returns:
        dict: ``created_count``, ``failed_count``, ``created`` (``index``, ``id``, ``title``),
            ``errors`` (``index``, ``title``, ``message``, optional ``code``). Commits all successful rows.
    """
    from app.core.exceptions import ValidationError

    if not isinstance(items, list):
        raise ValidationError("items", "items must be a JSON array of objects")
    n = len(items)
    if n < 1:
        raise ValidationError("items", "At least one item is required")
    if n > _MAX_BULK_TASKS:
        raise ValidationError("items", f"At most {_MAX_BULK_TASKS} items per call")

    tid_tpl: uuid.UUID | None = None
    if template_id and str(template_id).strip():
        tid_tpl = uuid.UUID(str(template_id).strip())
    cid: uuid.UUID | None = None
    if client_id and str(client_id).strip():
        cid = uuid.UUID(str(client_id).strip())

    created: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    async with async_session_factory() as db:
        actor = actor_dict_for_service()
        for idx, raw in enumerate(items):
            title_for_err: str | None = None
            if not isinstance(raw, dict):
                errors.append(
                    {"index": idx, "title": None, "message": "Item must be an object", "code": "BAD_ITEM"},
                )
                continue
            row_title = _resolve_create_task_title(raw.get("title"), raw.get("name"))
            title_for_err = row_title or None
            if not row_title:
                errors.append(
                    {
                        "index": idx,
                        "title": None,
                        "message": "title (or name) is required",
                        "code": "VALIDATION_ERROR",
                    },
                )
                continue
            try:
                assignee_uuid = await _resolve_assignee_from_item(db, raw)
                due_dt = _parse_due_date_optional(raw.get("due_date"))
                prio = str(raw.get("priority") or "medium").strip() or "medium"
                cf = raw.get("custom_fields") if isinstance(raw.get("custom_fields"), dict) else {}
                addr = str(raw.get("address")).strip() if raw.get("address") is not None else None
                lat_raw = raw.get("latitude")
                lng_raw = raw.get("longitude")
                lat = float(lat_raw) if lat_raw is not None and str(lat_raw).strip() else None
                lng = float(lng_raw) if lng_raw is not None and str(lng_raw).strip() else None
                geo_payload = await _resolve_geo_payload(
                    address=addr,
                    latitude=lat,
                    longitude=lng,
                    custom_fields=cf,
                )
                if geo_payload.get("ok") is not True:
                    errors.append(
                        {
                            "index": idx,
                            "title": title_for_err,
                            "message": str(geo_payload.get("message") or "Location is ambiguous"),
                            "code": str(geo_payload.get("code") or "AMBIGUOUS_LOCATION"),
                        },
                    )
                    continue
                desc_clean = (raw.get("description") or "")
                desc_clean = str(desc_clean).strip() or None
                rb_raw = raw.get("requested_by")
                req_by_row: uuid.UUID | None = None
                if rb_raw is not None and str(rb_raw).strip():
                    req_by_row = uuid.UUID(str(rb_raw).strip())
                co_row = await _resolve_uuid_or_user_query_list_field(
                    db, raw.get("co_assignee_ids"), "co_assignee_ids"
                )
                obs_row = await _resolve_uuid_or_user_query_list_field(
                    db, raw.get("observer_ids"), "observer_ids"
                )
                obs_query_raw = raw.get("observer_query") or raw.get("observer_name")
                obs_queries_raw = raw.get("observer_queries")
                if obs_query_raw is not None and str(obs_query_raw).strip():
                    uid = await _resolve_single_user_id_by_query(
                        db,
                        query=str(obs_query_raw),
                        field_name="observer_query",
                    )
                    if uid not in obs_row:
                        obs_row.append(uid)
                if obs_queries_raw is not None:
                    if not isinstance(obs_queries_raw, list):
                        from app.core.exceptions import ValidationError
                        raise ValidationError(
                            "observer_queries", "observer_queries must be a list of strings"
                        )
                    for q in obs_queries_raw:
                        if q is None or (isinstance(q, str) and not q.strip()):
                            continue
                        uid = await _resolve_single_user_id_by_query(
                            db,
                            query=str(q),
                            field_name="observer_queries",
                        )
                        if uid not in obs_row:
                            obs_row.append(uid)
                if tid_tpl is not None:
                    params: dict[str, Any] = {
                        "title": row_title,
                        "description": desc_clean,
                        "client_id": cid,
                        "assigned_to": assignee_uuid,
                        "requested_by": req_by_row,
                        "co_assignee_ids": co_row,
                        "observer_ids": obs_row,
                        "custom_fields": geo_payload["custom_fields"],
                        "priority": prio,
                    }
                    if due_dt:
                        params["due_date"] = due_dt
                    task = await TemplateService.instantiate_template(db, tid_tpl, params, actor)
                else:
                    payload: dict[str, Any] = {
                        "title": row_title,
                        "description": desc_clean,
                        "template_id": None,
                        "client_id": cid,
                        "assigned_to": assignee_uuid,
                        "requested_by": req_by_row,
                        "co_assignee_ids": co_row,
                        "observer_ids": obs_row,
                        "custom_fields": geo_payload["custom_fields"],
                        "priority": prio,
                    }
                    if due_dt:
                        payload["due_date"] = due_dt
                    task = await TaskService.create_task(db, payload, actor)
                await db.flush()
                row_loaded = await TaskService.get_task(db, task.id, viewer_user_id=actor["id"], user_sees_all=_mcp_user_sees_all_tasks())
                await TaskNotificationService.notify_after_task_created(db, row_loaded, actor["id"])
                created.append({"index": idx, "id": str(task.id), "title": task.title})
            except HVACBaseError as exc:
                errors.append(
                    {
                        "index": idx,
                        "title": title_for_err,
                        "message": exc.message,
                        "code": exc.code,
                    },
                )
            except (ValueError, TypeError) as exc:
                errors.append(
                    {
                        "index": idx,
                        "title": title_for_err,
                        "message": str(exc),
                        "code": "BAD_ARGUMENTS",
                    },
                )
        await db.commit()

    return {
        "created_count": len(created),
        "failed_count": len(errors),
        "created": created,
        "errors": errors,
    }


@mcp.tool()
async def update_task(task_id: str, fields: dict) -> dict:
    """Update fields of an existing task.

    Обновляет одно или несколько полей существующей задачи.
    Нельзя менять статус через этот инструмент — используйте transition_task.

    Args:
        task_id (str): UUID задачи для обновления.
        fields (dict): Словарь полей для обновления. Допустимые ключи:
            title, description, priority, assigned_to, requested_by,
            co_assignee_ids (list UUID), observer_ids (list UUID),
            due_date, started_at, completed_at, sla_deadline, custom_fields, address, latitude, longitude.

    Returns:
        dict: Обновлённая задача с полями id, title, status, priority,
            assigned_to, custom_fields, due_date, updated_at.

    Example:
        AI agent: "Измени приоритет задачи на критический и назначь нового исполнителя"
        >>> update_task(
        ...     task_id="a1b2c3d4-...",
        ...     fields={"priority": "critical", "assigned_to": "new-user-uuid"},
        ... )
    """
    tid = uuid.UUID(task_id)
    _viewer = uuid.UUID(current_mcp_user_sub())
    normalized: dict[str, Any] = dict(fields or {})
    if "assigned_to" in normalized and normalized["assigned_to"]:
        normalized["assigned_to"] = uuid.UUID(str(normalized["assigned_to"]))
    if "requested_by" in normalized:
        rb = normalized["requested_by"]
        normalized["requested_by"] = (
            uuid.UUID(str(rb).strip()) if rb is not None and str(rb).strip() else None
        )
    # Keep `co_assignee_ids` and `observer_ids` un-resolved until we have a DB session,
    # because they may contain name queries (not only UUIDs).
    if "co_assignee_ids" in normalized:
        raw_co = normalized["co_assignee_ids"]
        normalized["co_assignee_ids"] = [] if raw_co is None else raw_co
    if "observer_ids" in normalized:
        raw_obs = normalized["observer_ids"]
        normalized["observer_ids"] = [] if raw_obs is None else raw_obs
    # Optional name-based resolvers: convert to `observer_ids` before calling TaskService.
    obs_query = normalized.pop("observer_query", None) if "observer_query" in normalized else None
    obs_queries = normalized.pop("observer_queries", None) if "observer_queries" in normalized else None
    if "observer_name" in normalized and obs_query is None:
        obs_query = normalized.pop("observer_name")
    if "client_id" in normalized and normalized["client_id"]:
        normalized["client_id"] = uuid.UUID(str(normalized["client_id"]))
    addr = normalized.pop("address", None) if "address" in normalized else None
    lat = normalized.pop("latitude", None) if "latitude" in normalized else None
    lng = normalized.pop("longitude", None) if "longitude" in normalized else None
    geo_payload = await _resolve_geo_payload(
        address=str(addr).strip() if addr is not None else None,
        latitude=float(lat) if lat is not None and str(lat).strip() else None,
        longitude=float(lng) if lng is not None and str(lng).strip() else None,
        custom_fields=normalized.get("custom_fields") if isinstance(normalized.get("custom_fields"), dict) else {},
    )
    if geo_payload.get("ok") is not True:
        return geo_payload
    if any(k is not None for k in (addr, lat, lng)) or "custom_fields" in normalized:
        normalized["custom_fields"] = geo_payload["custom_fields"]
    _dt_keys = ("due_date", "started_at", "completed_at", "sla_deadline")
    for dk in _dt_keys:
        if dk not in normalized:
            continue
        raw = normalized[dk]
        if raw is None or raw == "":
            normalized[dk] = None
        else:
            normalized[dk] = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))

    async with async_session_factory() as db:
        # Resolve possibly mixed (UUID or name query) lists into UUIDs
        if "co_assignee_ids" in normalized:
            normalized["co_assignee_ids"] = await _resolve_uuid_or_user_query_list_field(
                db, normalized.get("co_assignee_ids"), "co_assignee_ids"
            )

        if "observer_ids" in normalized:
            normalized["observer_ids"] = await _resolve_uuid_or_user_query_list_field(
                db, normalized.get("observer_ids"), "observer_ids"
            )

        if (obs_query is not None or obs_queries is not None) and "observer_ids" not in normalized:
            normalized["observer_ids"] = []

        # Resolve observer queries to UUIDs.
        if obs_query is not None and str(obs_query).strip():
            resolved = await _resolve_single_user_id_by_query(
                db,
                query=str(obs_query),
                field_name="observer_query",
            )
            current: list[uuid.UUID] = list(normalized.get("observer_ids") or [])
            if resolved not in current:
                current.append(resolved)
            normalized["observer_ids"] = current

        if obs_queries is not None:
            if not isinstance(obs_queries, list):
                from app.core.exceptions import ValidationError
                raise ValidationError("observer_queries", "observer_queries must be a list of strings")
            for q in obs_queries:
                if q is None or (isinstance(q, str) and not q.strip()):
                    continue
                resolved = await _resolve_single_user_id_by_query(
                    db,
                    query=str(q),
                    field_name="observer_queries",
                )
                current = list(normalized.get("observer_ids") or [])
                if resolved not in current:
                    current.append(resolved)
                normalized["observer_ids"] = current

        prev_task = await TaskService.get_task(db, tid, viewer_user_id=_viewer, user_sees_all=_mcp_user_sees_all_tasks())
        prev_assignee = prev_task.assigned_to
        actor = actor_dict_for_service()

        # Update + notifications in one transaction so observers get
        # messages for changes performed via MCP.
        task = await TaskService.update_task(db, tid, normalized, actor)

        task_for_api = await TaskService.get_task(db, task.id, viewer_user_id=_viewer, user_sees_all=_mcp_user_sees_all_tasks())
        actor_id = actor["id"]

        if "assigned_to" in normalized and prev_assignee != task_for_api.assigned_to:
            await TaskNotificationService.notify_assignee_change(
                db,
                task_for_api,
                prev_assignee=prev_assignee,
                new_assignee=task_for_api.assigned_to,
                actor_id=actor_id,
            )

        changed: set[str] = {k for k in ("due_date", "priority", "title") if k in normalized}
        if "co_assignee_ids" in normalized:
            changed.add("co_assignees")
        if changed:
            await TaskNotificationService.notify_task_fields_changed(
                db,
                task_for_api,
                actor_id=actor_id,
                changed=changed,
            )

        await db.commit()
        return TaskResponse.model_validate(task_for_api).model_dump(mode="json")


@mcp.tool()
async def assign_task_to_user(task_id: str, assignee_query: str) -> dict:
    """Assign a task to an employee by human-readable name (search + update in one tool call).

    Prefer this over chaining ``search_users`` + ``update_task`` to avoid multi-step tool loops.
    Uses the same name matching as ``search_users`` (order-independent for «Фамилия Имя»).

    Args:
        task_id: Task UUID (use ``last_task_id`` from session when the user says «эту задачу»).
        assignee_query: Substring or full name, e.g. «Лавров» or «Дмитрий Лавров».

    Returns:
        Updated task (``TaskResponse`` shape), or ``{"ok": false, "code": "AMBIGUOUS_USER", ...}``
        if several people match—then narrow ``assignee_query`` or pick ``id`` from ``candidates``.
    """
    from app.core.exceptions import ValidationError

    tid = uuid.UUID(str(task_id).strip())
    query = (assignee_query or "").strip()
    if len(query) < 2:
        raise ValidationError("assignee_query", "Use at least 2 characters")

    _viewer = uuid.UUID(current_mcp_user_sub())
    async with async_session_factory() as db:
        prev_task = await TaskService.get_task(db, tid, viewer_user_id=_viewer, user_sees_all=_mcp_user_sees_all_tasks())
        prev_assignee = prev_task.assigned_to
        users = await _find_active_users_by_query(db, query, limit=25)
        if not users:
            raise ValidationError(
                "assignee_query",
                f"No active user matches «{query}». Try a shorter surname or check spelling.",
            )
        if len(users) > 1:
            return {
                "ok": False,
                "code": "AMBIGUOUS_USER",
                "message": "Multiple users match; narrow the name or pass a UUID via update_task.",
                "candidates": [
                    {
                        "id": str(u.id),
                        "full_name": u.full_name,
                        "email": u.email,
                        "role": u.role,
                    }
                    for u in users
                ],
            }

        chosen = users[0]
        actor = actor_dict_for_service()
        task = await TaskService.update_task(db, tid, {"assigned_to": chosen.id}, actor)
        task_for_api = await TaskService.get_task(db, task.id, viewer_user_id=_viewer, user_sees_all=_mcp_user_sees_all_tasks())

        if prev_assignee != task_for_api.assigned_to:
            await TaskNotificationService.notify_assignee_change(
                db,
                task_for_api,
                prev_assignee=prev_assignee,
                new_assignee=task_for_api.assigned_to,
                actor_id=actor["id"],
            )

        await db.commit()
        return TaskResponse.model_validate(task_for_api).model_dump(mode="json")


@mcp.tool()
async def transition_task(
    task_id: str,
    to_status: str,
    reason: str = "",
) -> dict:
    """Transition a task to a new workflow status.

    Выполняет переход задачи в новый статус согласно workflow_definition
    шаблона. Проверяет допустимость перехода и заполненность gate-чеклистов.

    Args:
        task_id (str): UUID задачи.
        to_status (str): Целевой статус (например, "in_progress", "review",
            "completed"). Должен быть допустимым переходом из текущего статуса.
        reason (str): Причина перехода (для аудита). По умолчанию пустая строка.

    Returns:
        dict: Результат перехода с полями id, from_status, to_status,
            transitioned_at, reason.

    Example:
        AI agent: "Переведи задачу в статус 'выполнена'"
        >>> transition_task(
        ...     task_id="a1b2c3d4-...",
        ...     to_status="completed",
        ...     reason="Все работы выполнены, акт подписан",
        ... )
    """
    tid = uuid.UUID(task_id)
    user = current_mcp_user()
    _viewer = uuid.UUID(current_mcp_user_sub())

    async with async_session_factory() as db:
        task = await TaskService.get_task(db, tid, viewer_user_id=_viewer, user_sees_all=_mcp_user_sees_all_tasks())
        from_status = task.status

        # Используем WorkflowEngine, но поддерживаем обратные переходы,
        # как и REST API (если to_status левее from_status в workflow.states).
        engine = WorkflowEngine(db, user)
        try:
            await engine.execute_transition(task, to_status, user, db, reason=reason)
        except WorkflowTransitionError as exc:
            logger.info(
                "MCP transition_task: engine denied transition; evaluating backwards fallback",
                extra={
                    "task_id": str(tid),
                    "from_status": from_status,
                    "to_status": to_status,
                    "workflow_reason": exc.details.get("reason") if exc.details else str(exc),
                },
            )
            # Align with REST: allow backwards along template.states order when engine rejects.
            states = (task.template.workflow_definition or {}).get("states") if task.template else None
            order: dict[str, int] = {s: i for i, s in enumerate(states or [])}
            is_backwards = (
                from_status in order
                and to_status in order
                and order[to_status] < order[from_status]
            )
            if not is_backwards:
                raise

            await db.execute(sa_update(Task).where(Task.id == tid).values(status=to_status))
            db.add(
                TaskStatusHistory(
                    task_id=tid,
                    from_status=from_status,
                    to_status=to_status,
                    changed_by=uuid.UUID(current_mcp_user_sub()),
                    reason=reason or "Backwards transition via MCP",
                    transition_data={},
                )
            )
            await db.flush()

        await db.commit()
        updated = await TaskService.get_task(db, tid, viewer_user_id=_viewer, user_sees_all=_mcp_user_sees_all_tasks())
        await TaskNotificationService.notify_observers_status_changed(
            db,
            updated,
            actor_id=uuid.UUID(current_mcp_user_sub()),
            from_status=from_status,
            to_status=to_status,
        )
        await db.commit()
        return {
            "id": str(updated.id),
            "from_status": from_status,
            "to_status": updated.status,
            "transitioned_at": updated.updated_at.isoformat() if updated.updated_at else None,
            "reason": reason,
        }


@mcp.tool()
async def list_tasks(
    status: str | None = None,
    assigned_to: str | None = None,
    involves_user: str | None = None,
    client_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List tasks with optional filters.

    Возвращает список задач с возможностью фильтрации по статусу,
    исполнителю и клиенту. Результаты отсортированы по дате создания (desc).

    Args:
        status (str | None): Фильтр по статусу задачи
            (например, "new", "in_progress", "completed").
        assigned_to (str | None): UUID основного исполнителя.
        involves_user (str | None): UUID пользователя — основной исполнитель или соисполнитель.
        client_id (str | None): UUID клиента для фильтрации.
        limit (int): Максимальное количество задач. По умолчанию 50, макс. 200.

    Returns:
        list[dict]: Список задач, каждая содержит id, title, status,
            priority, assigned_to, client_id, due_date, created_at.

    Example:
        AI agent: "Покажи все незавершённые задачи монтажника Иванова"
        >>> list_tasks(
        ...     status="in_progress",
        ...     assigned_to="user-uuid-ivanov",
        ...     limit=20,
        ... )
    """
    filters: dict[str, Any] = {
        "status": status,
        "client_id": uuid.UUID(client_id) if client_id else None,
        "limit": limit,
        "viewer_user_id": uuid.UUID(current_mcp_user_sub()),
        "user_sees_all": _mcp_user_sees_all_tasks(),
    }
    if involves_user and str(involves_user).strip():
        filters["involves_user"] = uuid.UUID(str(involves_user).strip())
    elif assigned_to:
        filters["assigned_to"] = uuid.UUID(str(assigned_to).strip())
    async with async_session_factory() as db:
        tasks = await TaskService.list_tasks(db, filters)
        return [TaskResponse.model_validate(t).model_dump(mode="json") for t in tasks]


@mcp.tool()
async def search_tasks(
    q: str,
    status: str | None = None,
    assigned_to: str | None = None,
    involves_user: str | None = None,
    client_id: str | None = None,
    limit: int = 25,
) -> list[dict]:
    """Find tasks by text in title, description, or custom_fields (e.g. address).

    Use this before ``delete_task``, ``update_task``, or ``get_task_detail`` when the user \
    refers to a task by address or words in the title (e.g. «Копылова 72»), not by UUID.

    Args:
        q: Substring to search (min 2 characters).
        status: Optional status filter.
        assigned_to: Optional primary assignee UUID.
        involves_user: Optional UUID — assignee or co-assignee.
        client_id: Optional client UUID.
        limit: Max results (1–100).

    Returns:
        Same shape as ``list_tasks`` (``TaskResponse`` dicts) with matching ``id`` for follow-up tools.
    """
    from app.core.exceptions import ValidationError

    assignee_uuid: uuid.UUID | None = None
    involves_uuid: uuid.UUID | None = None
    if involves_user and str(involves_user).strip():
        try:
            involves_uuid = uuid.UUID(str(involves_user).strip())
        except ValueError as exc:
            raise ValidationError("involves_user", "Must be a valid UUID") from exc
    elif assigned_to and str(assigned_to).strip():
        try:
            assignee_uuid = uuid.UUID(str(assigned_to).strip())
        except ValueError as exc:
            raise ValidationError("assigned_to", "Must be a valid UUID") from exc
    client_uuid: uuid.UUID | None = None
    if client_id and str(client_id).strip():
        try:
            client_uuid = uuid.UUID(str(client_id).strip())
        except ValueError as exc:
            raise ValidationError("client_id", "Must be a valid UUID") from exc

    try:
        lim = int(limit)
    except (TypeError, ValueError):
        lim = 25

    async with async_session_factory() as db:
        tasks = await TaskService.search_tasks(
            db,
            q=q,
            limit=lim,
            status=status,
            assigned_to=assignee_uuid,
            involves_user=involves_uuid,
            client_id=client_uuid,
            viewer_user_id=uuid.UUID(current_mcp_user_sub()),
            user_sees_all=_mcp_user_sees_all_tasks(),
        )
        return [TaskResponse.model_validate(t).model_dump(mode="json") for t in tasks]


@mcp.tool()
async def get_task_detail(task_id: str) -> dict:
    """Get full details of a specific task including relations.

    Возвращает полную информацию о задаче, включая связанные данные:
    клиент, исполнитель, шаблон, чек-листы, документы и историю статусов.

    Args:
        task_id (str): UUID задачи.

    Returns:
        dict: Полные данные задачи с вложенными объектами:
            id, title, description, status, priority, due_date,
            template (id, name), client (id, name), assignee (id, name),
            checklists (list), documents (list), status_history (list),
            custom_fields, created_at, updated_at.

    Example:
        AI agent: "Покажи полную информацию по задаче монтажа"
        >>> get_task_detail(task_id="a1b2c3d4-...")
    """
    from app.core.exceptions import ValidationError

    try:
        tid = uuid.UUID(str(task_id).strip())
    except ValueError as exc:
        raise ValidationError("task_id", "Must be a valid UUID; use search_tasks to find id") from exc

    async with async_session_factory() as db:
        result = await db.execute(
            select(Task)
            .options(
                selectinload(Task.checklists).selectinload(Checklist.items),
                selectinload(Task.comments),
                selectinload(Task.documents),
                selectinload(Task.time_entries),
                selectinload(Task.status_history),
                selectinload(Task.assignee),
                selectinload(Task.template),
                selectinload(Task.creator),
                selectinload(Task.requester_user),
                selectinload(Task.co_assignees),
                selectinload(Task.observers),
            )
            .where(
                Task.id == tid,
                Task.active_filter(),
                TaskService.sql_tasks_row_visible(
                    uuid.UUID(current_mcp_user_sub()),
                    user_sees_all=_mcp_user_sees_all_tasks(),
                ),
            )
        )
        task = result.scalar_one_or_none()
        if task is None:
            from app.core.exceptions import NotFoundError
            raise NotFoundError("Task", str(tid))
        return TaskDetail.model_validate(task).model_dump(mode="json")


@mcp.tool()
async def delete_task(task_id: str) -> dict:
    """Soft-delete a task (hidden from lists; history kept; use ``restore_task`` to undo).

    Аргументы:
        task_id: UUID задачи.
    """
    from app.core.exceptions import ValidationError

    try:
        tid = uuid.UUID(str(task_id).strip())
    except ValueError as exc:
        raise ValidationError("task_id", "Must be a valid UUID; use search_tasks to find id") from exc
    _viewer = uuid.UUID(current_mcp_user_sub())
    async with async_session_factory() as db:
        await TaskService.get_task(db, tid, viewer_user_id=_viewer, user_sees_all=_mcp_user_sees_all_tasks())
        await TaskService.delete_task(db, tid, actor_dict_for_service())
        await db.commit()
        return {"deleted": True, "id": task_id, "soft": True}


@mcp.tool()
async def bulk_delete_tasks(
    status: str | None = None,
    assigned_to: str | None = None,
    involves_user: str | None = None,
    client_id: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Soft-delete many tasks matched by filters (safe bulk operation).

    This tool is meant for assistant commands like «удали все задачи» or
    «удали все задачи в статусе new». It first fetches matching tasks and then
    soft-deletes them in one call.

    Args:
        status: Optional task status filter.
        assigned_to: Optional primary assignee UUID.
        involves_user: Optional UUID — assignee/co-assignee/observer.
        client_id: Optional client UUID.
        limit: Max tasks to delete in one call (capped at 200).

    Returns:
        dict: {deleted_count, deleted: [{id, title, status}], limit, filters}
    """
    from app.core.exceptions import ValidationError

    try:
        lim = int(limit)
    except (TypeError, ValueError):
        lim = 200
    lim = max(1, min(lim, 200))

    filters: dict[str, Any] = {
        "status": status,
        "limit": lim,
        "viewer_user_id": uuid.UUID(current_mcp_user_sub()),
        "user_sees_all": _mcp_user_sees_all_tasks(),
    }
    if client_id and str(client_id).strip():
        try:
            filters["client_id"] = uuid.UUID(str(client_id).strip())
        except ValueError as exc:
            raise ValidationError("client_id", "Must be a valid UUID") from exc
    if involves_user and str(involves_user).strip():
        try:
            filters["involves_user"] = uuid.UUID(str(involves_user).strip())
        except ValueError as exc:
            raise ValidationError("involves_user", "Must be a valid UUID") from exc
    elif assigned_to and str(assigned_to).strip():
        try:
            filters["assigned_to"] = uuid.UUID(str(assigned_to).strip())
        except ValueError as exc:
            raise ValidationError("assigned_to", "Must be a valid UUID") from exc

    async with async_session_factory() as db:
        tasks = await TaskService.list_tasks(db, filters)
        deleted: list[dict[str, Any]] = []
        actor = actor_dict_for_service()
        for t in tasks:
            await TaskService.delete_task(db, t.id, actor)
            deleted.append({"id": str(t.id), "title": t.title, "status": t.status})
        await db.commit()

    return {
        "deleted_count": len(deleted),
        "deleted": deleted,
        "limit": lim,
        "filters": {
            "status": status,
            "assigned_to": assigned_to,
            "involves_user": involves_user,
            "client_id": client_id,
        },
    }


@mcp.tool()
async def restore_task(task_id: str) -> dict:
    """Restore a soft-deleted task (clears trash flags; same as POST /tasks/{id}/restore).

    Args:
        task_id: UUID of a soft-deleted task.

    Returns:
        dict: Restored task in ``TaskResponse`` shape.
    """
    from app.core.exceptions import ValidationError

    try:
        tid = uuid.UUID(str(task_id).strip())
    except ValueError as exc:
        raise ValidationError("task_id", "Must be a valid UUID") from exc

    async with async_session_factory() as db:
        await TaskService.restore_task(db, tid, actor_dict_for_service())
        loaded = await db.execute(
            select(Task)
            .options(
                selectinload(Task.assignee),
                selectinload(Task.template),
                selectinload(Task.creator),
                selectinload(Task.requester_user),
                selectinload(Task.co_assignees),
                selectinload(Task.observers),
            )
            .where(Task.id == tid)
        )
        row = loaded.scalar_one()
        await db.commit()
    return TaskResponse.model_validate(row).model_dump(mode="json")
