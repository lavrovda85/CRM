"""MCP tools for tender management in SPEC CRM/ERP.

Инструменты для создания, обновления статуса, привязки задач
и просмотра тендеров через MCP-протокол. Поведение согласовано с REST API
через ``app.services.tender.tender_service`` и ``tender_pipeline``.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from dataclasses import asdict
from decimal import Decimal
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

from app.core.database import async_session_factory
from app.core.exceptions import NotFoundError, ValidationError
from app.core.permissions import user_sees_all_company_tasks
from app.mcp.server import mcp
from app.schemas.document import DocumentResponse
from app.schemas.task import TaskResponse
from app.schemas.tender import TenderChecklistResponse, TenderCommentResponse, TenderResponse
from app.mcp.actor_context import actor_dict_for_service, current_mcp_user, current_mcp_user_sub
from app.services import company_service
from app.services.tender import tender_pipeline, tender_service
from app.services.tender.tender_analysis_queue import schedule_tender_analysis
from app.services.tender.tender_analysis_service import enqueue_analysis_reset_pending
from app.services.tender.tender_external_service import fetch_tender_page, search_tender_candidates
from app.services.tender.tender_import_payload import build_tender_import_payload
from app.services.tender.tender_notice_fields import parse_guarantee_rubles, parse_nmck_rubles_to_decimal
from app.services.tender.tender_smeta_queue import schedule_tender_smeta
from app.services.tender.tender_smeta_service import enqueue_smeta_pending
from app.services.tender.tender_zakupki_documents import import_zakupki_public_documents
from app.services.task_service import TaskService


def _parse_mcp_deadline(raw: str | None) -> date | None:
    """Parse MCP deadline string into a date (submission deadline)."""
    if raw is None or not str(raw).strip():
        return None
    s = str(raw).strip()
    try:
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            return date.fromisoformat(s[:10])
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.date()
    except ValueError as exc:
        raise ValidationError("deadline", f"Invalid date or ISO datetime: {raw!r}") from exc


def _parse_uuid_optional(raw: str | None, field: str) -> uuid.UUID | None:
    """Parse optional UUID string; empty -> None."""
    if raw is None or not str(raw).strip():
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except ValueError as exc:
        raise ValidationError(field, "Must be a valid UUID") from exc


def _merge_import_description(
    payload_desc: str | None,
    page_desc: str | None,
    enriched_summary: str | None,
) -> str | None:
    """Prefer parsed card text; use search enrichment when the page body is empty or too short."""
    base = (payload_desc or "").strip() or (page_desc or "").strip()
    hint = (enriched_summary or "").strip()
    if not hint:
        return base[:8000] if base else None
    if not base:
        return hint[:8000]
    if len(base) < 40 and len(hint) >= len(base):
        return hint[:8000]
    if hint in base:
        return base[:8000]
    return f"{base}\n\n---\nКратко из поиска:\n{hint}"[:8000]


def _deadline_pair_from_enriched_iso(raw: str | None) -> tuple[date | None, datetime | None]:
    """Parse ISO deadline from last search row when the live page has no submission date."""
    if raw is None or not str(raw).strip():
        return None, None
    s = str(raw).strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.date(), dt
    except ValueError:
        return None, None


@mcp.tool()
async def create_tender(
    title: str,
    source: str | None = None,
    budget: float | None = None,
    deadline: str | None = None,
    assigned_to: str | None = None,
) -> dict:
    """Create a new tender/bid in the system.

    Создаёт новый тендер с начальным статусом "search" и универсальным чеклистом
    (как при создании через REST).

    Args:
        title (str): Название тендера
            (например, "Поставка и монтаж VRF — ТЦ Мега").
        source (str | None): Источник тендера (площадка или заказчик,
            например, "zakupki.gov.ru", "Прямой заказчик").
        budget (float | None): Бюджет тендера в рублях.
        deadline (str | None): Крайний срок подачи заявки: ``YYYY-MM-DD`` или ISO 8601.
        assigned_to (str | None): UUID ответственного менеджера.

    Returns:
        dict: Созданный тендер (поля как у ``TenderResponse``), сериализованный в JSON.

    Example:
        AI agent: "Зарегистрируй новый тендер с zakupki.gov.ru"
        >>> create_tender(
        ...     title="Поставка и монтаж VRF-системы — Школа №5",
        ...     source="zakupki.gov.ru",
        ...     budget=2500000.0,
        ...     deadline="2026-04-30",
        ...     assigned_to="user-uuid-...",
        ... )
    """
    budget_dec: Decimal | None = None
    if budget is not None:
        budget_dec = Decimal(str(budget))

    assignee = _parse_uuid_optional(assigned_to, "assigned_to")
    deadline_d = _parse_mcp_deadline(deadline)

    async with async_session_factory() as session:
        uid = uuid.UUID(current_mcp_user_sub())
        company_id = await company_service.get_default_or_first_company_id(session, uid)
        tender = await tender_service.create_tender_mcp_minimal(
            session,
            company_id=company_id,
            title=title,
            source=source,
            budget=budget_dec,
            deadline=deadline_d,
            assigned_to=assignee,
            status="search",
        )
        await session.commit()
        loaded = await tender_service.load_tender_for_response(session, tender.id)
        return TenderResponse.model_validate(loaded).model_dump(mode="json")


@mcp.tool()
async def update_tender_status(
    tender_id: str,
    status: str,
    reason: str | None = None,
) -> dict:
    """Update the status of a tender.

    Обновляет статус тендера. Допустимые переходы задаются ``tender_pipeline``;
    логика совпадает с ``POST /tenders/{{id}}/transition`` (в т.ч. опциональная
    строка ``reason`` в ``notes``).

    Args:
        tender_id (str): UUID тендера.
        status (str): Новый статус. Допустимые значения:
            "search", "participation", "won", "lost",
            "execution", "completed".
        reason (str | None): Необязательная причина перехода (аудит в ``notes``).

    Returns:
        dict: Обновлённый тендер с полями id, title, from_status,
            to_status, updated_at.

    Example:
        AI agent: "Мы выиграли тендер — обнови статус"
        >>> update_tender_status(
        ...     tender_id="tender-uuid-...",
        ...     status="won",
        ...     reason="Протокол подписан",
        ... )
    """
    try:
        tid = uuid.UUID(str(tender_id).strip())
    except ValueError as exc:
        raise ValidationError("tender_id", "Must be a valid UUID") from exc

    async with async_session_factory() as session:
        from_status, tender = await tender_service.apply_tender_status_transition(
            session, tid, status, reason
        )
        await session.commit()
        return {
            "id": str(tender.id),
            "title": tender.title,
            "from_status": from_status,
            "to_status": status,
            "updated_at": tender.updated_at.isoformat() if tender.updated_at else datetime.now(timezone.utc).isoformat(),
        }


@mcp.tool()
async def link_tasks_to_tender(
    tender_id: str,
    task_ids: list[str],
) -> dict:
    """Link existing tasks to a tender.

    Привязывает задачи к тендеру. Все переданные ``task_ids`` должны существовать;
    иначе возвращается ошибка валидации (как строгая проверка целостности).

    Args:
        tender_id (str): UUID тендера.
        task_ids (list[str]): Список UUID задач для привязки.

    Returns:
        dict: Результат привязки с полями tender_id, linked_count,
            task_ids, linked_at.

    Example:
        AI agent: "Привяжи задачи монтажа и пусконаладки к тендеру"
        >>> link_tasks_to_tender(
        ...     tender_id="tender-uuid-...",
        ...     task_ids=["task-uuid-1", "task-uuid-2"],
        ... )
    """
    try:
        tid = uuid.UUID(str(tender_id).strip())
    except ValueError as exc:
        raise ValidationError("tender_id", "Must be a valid UUID") from exc

    parsed: list[uuid.UUID] = []
    for x in task_ids or []:
        try:
            parsed.append(uuid.UUID(str(x).strip()))
        except ValueError as exc:
            raise ValidationError("task_ids", f"Invalid UUID: {x!r}") from exc

    viewer = uuid.UUID(current_mcp_user_sub())
    async with async_session_factory() as session:
        linked = await tender_service.link_tasks_to_tender(
            session,
            tid,
            parsed,
            viewer_user_id=viewer,
            user_sees_all=user_sees_all_company_tasks(current_mcp_user()),
        )
        await session.commit()

    return {
        "tender_id": str(tid),
        "linked_count": linked,
        "task_ids": [str(x) for x in parsed],
        "linked_at": datetime.now(timezone.utc).isoformat(),
    }


@mcp.tool()
async def list_tenders(
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List tenders with optional status filter.

    Возвращает список тендеров; порядок как в REST — по ``created_at`` убыванию.

    Args:
        status (str | None): Фильтр по статусу тендера:
            "search", "participation", "won", "lost",
            "execution", "completed". Если не указан — все тендеры.
        limit (int): Максимальное количество результатов.
            По умолчанию 50, макс. 200.

    Returns:
        list[dict]: Список тендеров в формате ``TenderResponse`` (JSON).

    Example:
        AI agent: "Покажи все тендеры, в которых мы участвуем"
        >>> list_tenders(status="participation", limit=20)
    """
    if status is not None and str(status).strip() and status not in tender_pipeline.ALL_KNOWN_STATUSES:
        raise ValidationError(
            "status",
            f"Unknown status; allowed: {', '.join(sorted(tender_pipeline.ALL_KNOWN_STATUSES))}",
        )
    try:
        lim = max(1, min(int(limit), 200))
    except (TypeError, ValueError) as exc:
        raise ValidationError("limit", "Must be an integer between 1 and 200") from exc
    filter_status = str(status).strip() if status and str(status).strip() else None

    async with async_session_factory() as session:
        rows = await tender_service.list_tenders_simple(session, status=filter_status, limit=lim)

    return [TenderResponse.model_validate(t).model_dump(mode="json") for t in rows]


@mcp.tool()
async def fetch_tender_from_url(url: str) -> dict:
    """Download a public web page and extract tender-related metadata (title, description, excerpt).

    Не создаёт запись в CRM — только читает страницу по ссылке (https по умолчанию).
    Используйте перед импортом, чтобы проверить содержимое или уточнить заголовок.

    Args:
        url (str): Публичный URL карточки тендера или документации (например, zakupki.gov.ru).

    Returns:
        dict: Поля url, final_url, http_status, title, description, text_excerpt, source_guess,
            content_type.

    Example:
        >>> fetch_tender_from_url("https://zakupki.gov.ru/epz/order/notice/...")
    """
    page = await fetch_tender_page(url)
    d = asdict(page)
    if page.application_deadline_utc:
        d["application_deadline_utc"] = page.application_deadline_utc.isoformat()
    return d


@mcp.tool()
async def search_tenders_on_web(
    query: str | None = None,
    max_results: int | None = None,
    prefer_zakupki_gov: bool = False,
    enrich: bool = True,
    only_open_deadlines: bool | None = None,
    exclude_urls: list[str] | None = None,
) -> list[dict]:
    """Search the public web for tender listings matching keywords (DuckDuckGo).

    Возвращает список ссылок с заголовком, сниппетом и кратким ``summary`` (текст страницы
    и при необходимости ИИ), чтобы выбрать, что импортировать. Для загрузки в CRM выберите URL
    и вызовите ``import_tender_from_url``. При ``prefer_zakupki_gov=True`` поиск
    дополняется DuckDuckGo с ``site:zakupki.gov.ru``.

    Args:
        query (str | None): Ключевые слова (например, «кондиционирование Красноярский край»).
            В вызове через ИИ обязательно передайте строку поиска; допустимы синонимы ``q``, ``keywords``.
        max_results (int | None): Сколько результатов (1–50; по умолчанию из настроек ``TENDER_SEARCH_MAX_RESULTS``).
        prefer_zakupki_gov (bool): Если True — дополнительно выполняется поиск DuckDuckGo с префиксом site:zakupki.gov.ru (основная выдача идёт из ЕИС и широкого DDG).
        enrich (bool): Если False — только title/url/snippet без загрузки страниц и без поля ``summary``.
        only_open_deadlines (bool | None): Если True (по умолчанию из настроек) — исключить закупки,
            у которых срок подачи заявок уже истёк (сравнение с текущим временем сервера в UTC).
            Работает только при ``enrich=True`` (нужна загрузка страницы для даты).
        exclude_urls (list[str] | None): URL извещений, уже показанных пользователю — не возвращать снова;
            бэкенд подставляет их при «ещё / следующие» из сессии.

    Returns:
        list[dict]: title, url, snippet; при ``enrich=True`` также ``summary`` и при удачном разборе
        ``submission_deadline_utc`` (ISO-8601).

    Example:
        >>> search_tenders_on_web("поставка чиллеров", prefer_zakupki_gov=True, max_results=8)
    """
    q = (query or "").strip()
    if not q:
        raise ValidationError(
            "query",
            "Search query is required: pass `query` (or `q` / `keywords`) with non-empty keywords.",
        )
    excl = exclude_urls if isinstance(exclude_urls, list) else None
    return await search_tender_candidates(
        q,
        max_results=max_results,
        prefer_zakupki_gov=prefer_zakupki_gov,
        enrich=enrich,
        only_open_deadlines=only_open_deadlines,
        exclude_urls=excl,
    )


@mcp.tool()
async def import_tender_from_url(
    url: str,
    title_override: str | None = None,
    assigned_to: str | None = None,
    enriched_summary: str | None = None,
    enriched_submission_deadline_utc: str | None = None,
) -> dict:
    """Fetch a tender page from the internet and create a tender record in SPEC CRM.

    Скачивает карточку (ЕИС — common-info), извлекает предмет закупки, заказчика, НМЦК, контакты,
    срок подачи заявок, ссылки на документацию, обеспечение заявки и т.д. Полный снимок полей
    хранится в ``requirements.zakupki``; ``documents_url`` — ссылка на раздел документации на zakupki.

    Args:
        url (str): URL тендерной карточки или закупки.
        title_override (str | None): Принудительное название тендера в CRM.
        assigned_to (str | None): UUID ответственного менеджера.
        enriched_summary (str | None): Текст из последнего обогащённого поиска (ассистент); подставляется
            в описание, если с карточки пришло мало данных.
        enriched_submission_deadline_utc (str | None): ISO-8601 срока из поиска, если на странице нет даты.

    Returns:
        dict: Созданный тендер (как ``TenderResponse``).

    Example:
        >>> import_tender_from_url(
        ...     "https://zakupki.gov.ru/epz/order/notice/...",
        ...     title_override="Поставка VRF — школа №5",
        ... )
    """
    page = await fetch_tender_page(url)
    assignee = _parse_uuid_optional(assigned_to, "assigned_to")

    raw_title = (title_override or "").strip() if title_override else ""
    if not raw_title and page.title:
        raw_title = page.title.strip()
    if not raw_title:
        host = urlparse(page.final_url).netloc or "tender"
        raw_title = f"Tender ({host})"

    payload = build_tender_import_payload(page)
    zak_payload = ((payload.get("requirements") or {}).get("zakupki") or {}) if payload.get("requirements") else {}

    merged_description = _merge_import_description(
        payload.get("description"),
        page.description,
        enriched_summary,
    )

    budget_dec: Decimal | None = None
    if page.notice_fields and page.notice_fields.get("nmck"):
        budget_dec = parse_nmck_rubles_to_decimal(page.notice_fields.get("nmck"))
    if budget_dec is None and zak_payload.get("nmck"):
        budget_dec = parse_nmck_rubles_to_decimal(zak_payload.get("nmck"))

    guarantee_dec: Decimal | None = None
    if page.notice_fields and page.notice_fields.get("bid_security"):
        guarantee_dec = parse_guarantee_rubles(page.notice_fields.get("bid_security"))
    if guarantee_dec is None and zak_payload.get("bid_security"):
        guarantee_dec = parse_guarantee_rubles(zak_payload.get("bid_security"))

    deadline_d: date | None = None
    trade_anchor_utc: datetime | None = None
    if page.application_deadline_utc:
        deadline_d = page.application_deadline_utc.date()
        trade_anchor_utc = page.application_deadline_utc
    else:
        d_hint, t_hint = _deadline_pair_from_enriched_iso(enriched_submission_deadline_utc)
        deadline_d = d_hint
        trade_anchor_utc = t_hint

    async with async_session_factory() as session:
        uid = uuid.UUID(current_mcp_user_sub())
        company_id = await company_service.get_default_or_first_company_id(session, uid)
        tender = await tender_service.create_tender_mcp_import(
            session,
            company_id=company_id,
            title=raw_title[:500],
            tender_link=page.final_url[:1000],
            description=merged_description,
            source=page.source_guess,
            budget=budget_dec,
            max_price=budget_dec,
            deadline=deadline_d,
            trade_start_at=trade_anchor_utc,
            documents_url=payload.get("documents_url"),
            assigned_to=assignee,
            notes=payload.get("notes"),
            requirements=payload.get("requirements"),
            guarantee_amount=guarantee_dec,
        )
        docs_url = payload.get("documents_url")
        doc_notes: list[str] = []
        if docs_url and "zakupki.gov.ru" in docs_url.lower():
            actor = actor_dict_for_service()
            try:
                summary = await import_zakupki_public_documents(
                    session,
                    tender_id=tender.id,
                    documents_page_url=docs_url,
                    user=actor,
                )
            except Exception as exc:
                # Never roll back the tender if optional file import fails (MinIO, network, etc.).
                logger.exception("Zakupki document import failed for tender %s", tender.id)
                summary = {"imported": [], "imported_document_ids": [], "skipped": 0, "errors": []}
                doc_notes.append(
                    "Автозагрузка файлов с ЕИС не выполнена (тендер сохранён). "
                    "Откройте раздел «Документация» на zakupki по ссылке из карточки. "
                    f"Детали: {exc!s}"
                )
            if summary.get("imported"):
                doc_notes.append(
                    "Импортированы файлы с ЕИС: " + ", ".join(summary["imported"][:20])
                )
                req = dict(tender.requirements or {})
                zak = dict((req.get("zakupki") or {}))
                zak["imported_attachment_filenames"] = summary["imported"]
                ids = summary.get("imported_document_ids") or []
                if ids:
                    zak["imported_document_ids"] = ids
                req["zakupki"] = zak
                tender.requirements = req
            if summary.get("errors"):
                doc_notes.append("Файлы ЕИС (ошибки): " + "; ".join(summary["errors"][:5])[:2000])
        merged_notes = payload.get("notes")
        if doc_notes:
            extra = "\n".join(doc_notes)
            merged_notes = f"{merged_notes}\n\n{extra}".strip() if merged_notes else extra
            tender.notes = merged_notes[:12000]
        await session.commit()
        schedule_tender_analysis(tender.id)
        loaded = await tender_service.load_tender_for_response(session, tender.id)
        return TenderResponse.model_validate(loaded).model_dump(mode="json")


@mcp.tool()
async def get_tender(tender_id: str) -> dict:
    """Return full tender detail including ``tender_analysis``, tasks, documents, checklists.

    Same payload shape as ``GET /api/v1/tenders/{id}`` (extended tender card).
    """
    try:
        tid = uuid.UUID(str(tender_id).strip())
    except ValueError as exc:
        raise ValidationError("tender_id", "Must be a valid UUID") from exc

    async with async_session_factory() as session:
        tender = await tender_service.get_tender_detail_for_api(session, tid)
        if not tender:
            raise NotFoundError("Tender", str(tid))
        await session.commit()
        tender_data = TenderResponse.model_validate(tender).model_dump(mode="json")
        tender_data["tasks"] = [TaskResponse.model_validate(t).model_dump(mode="json") for t in tender.tasks]
        tender_data["checklists"] = [
            TenderChecklistResponse.model_validate(c).model_dump(mode="json") for c in tender.checklists
        ]
        tender_data["documents"] = [DocumentResponse.model_validate(d).model_dump(mode="json") for d in tender.documents]
        tender_data["comments"] = [
            TenderCommentResponse.model_validate(c).model_dump(mode="json") for c in tender.comments
        ]
        tender_data["allowed_next_statuses"] = tender_pipeline.allowed_next_statuses(tender.status)
        return tender_data


@mcp.tool()
async def retry_tender_analysis(tender_id: str) -> dict:
    """Queue background re-analysis of tender documents (risks, profitability, bill of works)."""
    from sqlalchemy import select

    from app.models import Tender

    try:
        tid = uuid.UUID(str(tender_id).strip())
    except ValueError as exc:
        raise ValidationError("tender_id", "Must be a valid UUID") from exc

    async with async_session_factory() as session:
        result = await session.execute(select(Tender).where(Tender.id == tid))
        if result.scalar_one_or_none() is None:
            raise NotFoundError("Tender", str(tid))
        await enqueue_analysis_reset_pending(session, tid)
        await session.commit()
    schedule_tender_analysis(tid)
    return {"queued": True, "tender_id": str(tid)}


@mcp.tool()
async def calculate_tender_smeta(tender_id: str) -> dict:
    """Queue indicative smeta calculation from the tender's bill of works (optional FGIS context + AI).

    Reads ``tender_analysis.bill_of_works``, merges optional pricing context from
    ``FGIS_CS_*`` env (see ``fgis_cs_client``), and fills ``tender_analysis.smeta_calculation``.
    Same job as POST ``/tenders/{id}/smeta/calculate``.
    """
    from sqlalchemy import select

    from app.models import Tender

    try:
        tid = uuid.UUID(str(tender_id).strip())
    except ValueError as exc:
        raise ValidationError("tender_id", "Must be a valid UUID") from exc

    async with async_session_factory() as session:
        result = await session.execute(select(Tender).where(Tender.id == tid))
        if result.scalar_one_or_none() is None:
            raise NotFoundError("Tender", str(tid))
        await enqueue_smeta_pending(session, tid)
        await session.commit()
    schedule_tender_smeta(tid)
    return {"queued": True, "tender_id": str(tid)}


@mcp.tool()
async def create_tender_estimator_task(
    tender_id: str,
    assigned_to: str | None = None,
    description: str | None = None,
) -> dict:
    """Create a high-priority task for an estimator (bill of works / смета) linked to the tender."""
    from sqlalchemy import select

    from app.models import Tender

    try:
        tid = uuid.UUID(str(tender_id).strip())
    except ValueError as exc:
        raise ValidationError("tender_id", "Must be a valid UUID") from exc

    assignee = _parse_uuid_optional(assigned_to, "assigned_to")

    async with async_session_factory() as session:
        result = await session.execute(select(Tender).where(Tender.id == tid))
        tender = result.scalar_one_or_none()
        if not tender:
            raise NotFoundError("Tender", str(tid))
        task = await TaskService.create_task(
            session,
            {
                "title": f"Смета и ведомость работ: {tender.title[:200]}",
                "description": description
                or (
                    "Проверить и доработать ведомость работ по тендеру. "
                    "См. разделы анализа и документы в карточке."
                ),
                "tender_id": tid,
                "priority": "high",
                "assigned_to": assignee,
            },
            actor_dict_for_service(),
        )
        await session.commit()
        loaded = await TaskService.get_task(session, task.id, only_active=False)
        return TaskResponse.model_validate(loaded).model_dump(mode="json")
