"""Tender persistence helpers shared by REST API and MCP.

Centralizes universal checklist seeding and task linking so behavior
stays aligned across entry points.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, TenderTransitionError, ValidationError
from app.models import Task, Tender, TenderChecklist, TenderChecklistItem
from app.services.task_service import TaskService
from app.schemas.tender import TenderCreate
from . import tender_pipeline


async def seed_universal_tender_checklist(session: AsyncSession, tender_id: uuid.UUID) -> None:
    """Create the default universal checklist and items for a tender.

    Args:
        session: Active async DB session (caller manages transaction).
        tender_id: Tender UUID to attach the checklist to.
    """
    checklist = TenderChecklist(
        tender_id=tender_id,
        title="Универсальный чеклист тендера",
    )
    session.add(checklist)
    await session.flush()

    session.add_all(
        [
            TenderChecklistItem(
                checklist_id=checklist.id,
                title="Первичный анализ (подтверждение руководством)",
                item_type="primary_analysis",
                order=0,
            ),
            TenderChecklistItem(
                checklist_id=checklist.id,
                title="Расчет (связь с задачей на расчет)",
                item_type="calculation",
                order=1,
            ),
            TenderChecklistItem(
                checklist_id=checklist.id,
                title="Подготовка пакета документов (чтение, краткий конспект, проверка средств)",
                item_type="document_package",
                order=2,
            ),
            TenderChecklistItem(
                checklist_id=checklist.id,
                title="Проверка за сутки до торгов",
                item_type="check_1d",
                order=3,
                scheduled_offset_hours=24,
            ),
            TenderChecklistItem(
                checklist_id=checklist.id,
                title="Проверка за два часа до торгов",
                item_type="check_2h",
                order=4,
                scheduled_offset_hours=2,
            ),
        ]
    )
    await session.flush()


async def create_tender_from_schema(
    session: AsyncSession,
    body: TenderCreate,
    *,
    company_id: uuid.UUID,
) -> Tender:
    """Persist a tender from the REST ``TenderCreate`` schema and seed checklist.

    Args:
        session: DB session (no commit; FastAPI ``get_db`` commits).
        body: Validated create payload.
        company_id: Active tenant (required; ``tenders.company_id`` is NOT NULL).

    Returns:
        The flushed ``Tender`` ORM instance (relationships may be lazy).
    """
    tender = Tender(
        company_id=company_id,
        title=body.title,
        tender_link=body.tender_link,
        customer_id=body.customer_id,
        guarantee_amount=body.guarantee_amount,
        max_price=body.max_price,
        min_price=body.min_price,
        trade_start_at=body.trade_start_at,
        trade_end_at=body.trade_end_at,
        source=body.source,
        budget=body.budget,
        our_price=body.our_price,
        status=body.status,
        deadline=body.deadline,
        assigned_to=body.assigned_to,
        requirements=body.requirements,
        notes=body.notes,
    )
    session.add(tender)
    await session.flush()
    await session.refresh(tender)
    await seed_universal_tender_checklist(session, tender.id)
    return tender


async def create_tender_mcp_import(
    session: AsyncSession,
    *,
    company_id: uuid.UUID,
    title: str,
    tender_link: str | None = None,
    description: str | None = None,
    source: str | None = None,
    budget: Decimal | None = None,
    max_price: Decimal | None = None,
    deadline: date | None = None,
    trade_start_at: datetime | None = None,
    documents_url: str | None = None,
    assigned_to: uuid.UUID | None = None,
    notes: str | None = None,
    requirements: dict | None = None,
    guarantee_amount: Decimal | None = None,
    status: str = "search",
) -> Tender:
    """Create a tender from MCP import (URL fetch + optional fields) and seed checklist.

    Args:
        session: DB session (caller commits).
        title: Non-empty tender title.
        tender_link: Canonical link to the tender on an external platform.
        description: Short description from the page.
        source: Platform label (e.g. zakupki.gov.ru).
        budget: Optional budget / НМЦК in rubles (legacy; see ``max_price``).
        max_price: Contract maximum (НМЦК) for UI «Максимальная цена».
        deadline: Submission deadline (date).
        trade_start_at: Anchor instant for reminders (submission end UTC preferred).
        documents_url: Link to documentation package if distinct from tender_link.
        assigned_to: Responsible user id.
        notes: Extra notes (e.g. fetch warnings).
        requirements: Structured snapshot (e.g. zakupki.*) for CRM / integrations.
        guarantee_amount: Bid security / guarantee in rubles when parsed from the notice.
        status: Initial pipeline status.

    Returns:
        Flushed ``Tender`` instance.
    """
    clean_title = title.strip()
    if not clean_title:
        raise ValidationError("title", "Title must be non-empty")

    req = dict(requirements) if requirements else {}

    tender = Tender(
        company_id=company_id,
        title=clean_title[:500],
        tender_link=(tender_link.strip()[:1000] if tender_link and tender_link.strip() else None),
        description=(description.strip() if description and description.strip() else None),
        source=(source.strip()[:255] if source and source.strip() else None),
        budget=budget,
        max_price=max_price,
        status=status,
        deadline=deadline,
        trade_start_at=trade_start_at,
        assigned_to=assigned_to,
        requirements=req,
        documents_url=(documents_url.strip()[:1000] if documents_url and documents_url.strip() else None),
        notes=notes.strip() if notes and notes.strip() else None,
        guarantee_amount=guarantee_amount,
    )
    session.add(tender)
    await session.flush()
    await session.refresh(tender)
    await seed_universal_tender_checklist(session, tender.id)
    return tender


async def load_tender_for_response(session: AsyncSession, tender_id: uuid.UUID) -> Tender:
    """Load tender with ``customer`` eager-loaded for ``TenderResponse``."""
    result = await session.execute(
        select(Tender).options(selectinload(Tender.customer)).where(Tender.id == tender_id)
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise NotFoundError("Tender", str(tender_id))
    return row


async def create_tender_mcp_minimal(
    session: AsyncSession,
    *,
    company_id: uuid.UUID,
    title: str,
    source: str | None = None,
    budget: Decimal | None = None,
    deadline: date | None = None,
    assigned_to: uuid.UUID | None = None,
    status: str = "search",
    notes: str | None = None,
) -> Tender:
    """Create a tender from MCP-style minimal fields and seed checklist.

    Args:
        session: DB session (caller commits).
        title: Non-empty tender title.
        source: Optional platform / origin label.
        budget: Optional budget.
        deadline: Optional submission deadline (date).
        assigned_to: Optional responsible user id.
        status: Initial pipeline status (validated by caller).
        notes: Optional free-text notes.

    Returns:
        Flushed ``Tender`` instance.
    """
    clean_title = title.strip()
    if not clean_title:
        raise ValidationError("title", "Title must be non-empty")

    tender = Tender(
        company_id=company_id,
        title=clean_title,
        source=source.strip() if source else None,
        budget=budget,
        status=status,
        deadline=deadline,
        assigned_to=assigned_to,
        requirements={},
        notes=notes.strip() if notes else None,
    )
    session.add(tender)
    await session.flush()
    await session.refresh(tender)
    await seed_universal_tender_checklist(session, tender.id)
    return tender


async def link_tasks_to_tender(
    session: AsyncSession,
    tender_id: uuid.UUID,
    task_ids: list[uuid.UUID],
    *,
    viewer_user_id: uuid.UUID | None = None,
    user_sees_all: bool = False,
) -> int:
    """Set ``tender_id`` on tasks; all IDs must exist.

    Args:
        session: DB session (caller commits).
        tender_id: Target tender.
        task_ids: Task UUIDs to attach (duplicates ignored for update count).
        viewer_user_id: If set, only tasks visible to this user may be linked.
        user_sees_all: If True (admin), any task id in the company may be linked.

    Returns:
        Number of tasks updated.

    Raises:
        NotFoundError: Tender missing.
        ValidationError: Any task id not found in ``tasks`` table.
    """
    tender_row = await session.get(Tender, tender_id)
    if tender_row is None:
        raise NotFoundError("Tender", str(tender_id))

    if not task_ids:
        return 0

    unique_ids = list(dict.fromkeys(task_ids))
    stmt = select(Task.id).where(Task.id.in_(unique_ids), Task.active_filter())
    if viewer_user_id is not None:
        stmt = stmt.where(
            TaskService.sql_tasks_row_visible(
                viewer_user_id,
                user_sees_all=user_sees_all,
            )
        )
    res = await session.execute(stmt)
    found = {row for row in res.scalars().all()}
    missing = [tid for tid in unique_ids if tid not in found]
    if missing:
        raise ValidationError(
            "task_ids",
            "Unknown task IDs: " + ", ".join(str(x) for x in missing),
        )

    await session.execute(
        update(Task).where(Task.id.in_(unique_ids)).values(tender_id=tender_id)
    )
    await session.flush()
    return len(unique_ids)


async def apply_tender_status_transition(
    session: AsyncSession,
    tender_id: uuid.UUID,
    to_status: str,
    reason: str | None = None,
) -> tuple[str, Tender]:
    """Validate pipeline transition and update tender status (optional notes line).

    Same rules as ``POST /tenders/{id}/transition``: optional ``reason`` is
    appended to ``tender.notes`` with a UTC timestamp.

    Args:
        session: DB session (caller commits / uses request-scoped transaction).
        tender_id: Tender UUID.
        to_status: Target pipeline status.
        reason: Optional audit note for ``notes`` field.

    Returns:
        ``(previous_status, updated_tender)`` — refreshed ORM row after update.

    Raises:
        NotFoundError: Tender does not exist.
        TenderTransitionError: Transition not allowed by ``tender_pipeline``.
    """
    result = await session.execute(select(Tender).where(Tender.id == tender_id))
    tender = result.scalar_one_or_none()
    if tender is None:
        raise NotFoundError("Tender", str(tender_id))

    from_status = tender.status
    deny = tender_pipeline.transition_denial_reason(from_status, to_status)
    if deny:
        raise TenderTransitionError(str(tender_id), from_status, to_status, deny)

    values: dict = {"status": to_status}
    if reason and reason.strip():
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        line = f"\n[{stamp}] {from_status} → {to_status}: {reason.strip()}"
        base = (tender.notes or "").strip()
        values["notes"] = f"{base}{line}" if base else line.strip()

    await session.execute(update(Tender).where(Tender.id == tender_id).values(**values))
    await session.flush()
    await session.refresh(tender)
    return from_status, tender


async def list_tenders_simple(
    session: AsyncSession,
    *,
    status: str | None = None,
    limit: int = 50,
) -> list[Tender]:
    """Return tenders ordered by ``created_at`` desc with customer loaded.

    Args:
        session: DB session.
        status: Optional status filter.
        limit: Max rows (capped at 200 by caller).

    Returns:
        List of ``Tender`` ORM rows.
    """
    stmt = select(Tender).options(selectinload(Tender.customer))
    if status:
        stmt = stmt.where(Tender.status == status)
    stmt = stmt.order_by(Tender.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def load_tender_detail_row(
    session: AsyncSession,
    tender_id: uuid.UUID,
) -> Tender | None:
    """Load tender with relations required for ``GET /tenders/{id}``."""
    result = await session.execute(
        select(Tender)
        .options(
            selectinload(Tender.tasks).selectinload(Task.assignee),
            selectinload(Tender.tasks).selectinload(Task.template),
            selectinload(Tender.tasks).selectinload(Task.creator),
            selectinload(Tender.tasks).selectinload(Task.requester_user),
            selectinload(Tender.tasks).selectinload(Task.co_assignees),
            selectinload(Tender.tasks).selectinload(Task.observers),
            selectinload(Tender.documents),
            selectinload(Tender.comments),
            selectinload(Tender.customer),
            selectinload(Tender.checklists).selectinload(TenderChecklist.items),
        )
        .where(Tender.id == tender_id)
    )
    return result.scalar_one_or_none()


async def get_tender_detail_for_api(
    session: AsyncSession,
    tender_id: uuid.UUID,
) -> Tender | None:
    """Load tender for detail view; seed universal checklist when missing (same as REST)."""
    tender = await load_tender_detail_row(session, tender_id)
    if not tender:
        return None
    if not tender.checklists:
        await seed_universal_tender_checklist(session, tender.id)
        await session.flush()
        tender = await load_tender_detail_row(session, tender_id)
    return tender
