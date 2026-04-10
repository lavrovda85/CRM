"""Tender management API endpoints.

CRUD операции над тендерами, привязка задач к тендерам.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import logging

from app.core.company_context import ActiveCompanyContext, get_active_company
from app.core.dependencies import PaginationParams, get_current_user, get_db
from app.core.config import Settings, get_settings
from app.core.exceptions import (
    HVACBaseError,
    NotFoundError,
    TenderTransitionError,
    ValidationError,
)
from app.core.pagination import PaginatedResponse
from app.core.security import CurrentUser
from app.models import Document, Task, Tender, TenderComment, TenderChecklist, TenderChecklistItem, User
from app.schemas.task import TaskResponse
from app.schemas.document import DocumentResponse
from app.schemas.tender import (
    TenderBillOfWorksPatch,
    TenderChecklistItemResponse,
    TenderChecklistItemUpdate,
    TenderChecklistResponse,
    TenderCommentCreate,
    TenderCommentResponse,
    TenderCreate,
    TenderResponse,
    TenderTasksFromBillRequest,
    TenderTransitionRequest,
    TenderUpdate,
)
from app.services.task_notification_service import TaskNotificationService
from app.services.task_service import TaskService
from app.services.tender import tender_pipeline, tender_service
from app.services.user_identity import resolve_users_table_id
from app.services.tender.tender_analysis_queue import schedule_tender_analysis
from app.services.tender.tender_analysis_service import enqueue_analysis_reset_pending
from app.services.tender.tender_smeta_queue import schedule_tender_smeta
from app.services.tender.tender_smeta_service import enqueue_smeta_pending

router = APIRouter(prefix="/tenders")
logger = logging.getLogger(__name__)


def _get_s3_client(settings: Settings):
    """Build a boto3 S3 client configured for MinIO."""
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


class TenderDetailResponse(TenderResponse):
    """Extended tender response with linked tasks.

    Атрибуты:
        tasks (list[TaskResponse]): Привязанные задачи.
        allowed_next_statuses: Допустимые следующие статусы пайплайна.
    """

    tasks: list[TaskResponse] = Field(default_factory=list)
    checklists: list[TenderChecklistResponse] = Field(default_factory=list)
    documents: list[DocumentResponse] = Field(default_factory=list)
    comments: list[TenderCommentResponse] = Field(default_factory=list)
    allowed_next_statuses: list[str] = Field(default_factory=list)


class LinkTasksRequest(BaseModel):
    """Schema for linking tasks to a tender.

    Атрибуты:
        task_ids (list[uuid.UUID]): Список ID задач для привязки.
    """

    task_ids: list[uuid.UUID]


class TenderAnalysisRetryResponse(BaseModel):
    """Ack after queueing a tender document analysis job."""

    queued: bool = True
    tender_id: uuid.UUID


class TenderSmetaCalculateResponse(BaseModel):
    """Ack after queueing bill-of-works smeta calculation (FGIS context + LLM)."""

    queued: bool = True
    tender_id: uuid.UUID


class TenderEstimatorTaskRequest(BaseModel):
    """Optional fields for the estimator bill-of-quantities task."""

    assigned_to: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=8000)
    attachment_document_ids: list[uuid.UUID] = Field(default_factory=list)


async def _resolve_db_user(db: AsyncSession, current_user: CurrentUser) -> User:
    """Resolve JWT user to local DB user (``users.id`` or ``keycloak_id`` — same as auth)."""
    uid = await resolve_users_table_id(db, current_user)
    db_user = await db.get(User, uid)
    if db_user is None:
        raise NotFoundError("User", current_user.sub)
    return db_user


@router.post("", response_model=TenderResponse, status_code=201)
async def create_tender(
    body: TenderCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    ctx: ActiveCompanyContext = Depends(get_active_company),
) -> TenderResponse:
    """Create a new tender.

    Создаёт новый тендер с указанным статусом и бюджетом.

    Аргументы:
        body: Данные для создания тендера.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Созданный тендер.
    """
    tender = await tender_service.create_tender_from_schema(
        db, body, company_id=ctx.company_id
    )
    tender_with_customer = await tender_service.load_tender_for_response(db, tender.id)
    return TenderResponse.model_validate(tender_with_customer)


@router.get("", response_model=PaginatedResponse[TenderResponse])
async def list_tenders(
    status: str | None = Query(default=None, description="Filter by status"),
    assigned_to: uuid.UUID | None = Query(default=None, description="Filter by assignee"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> PaginatedResponse[TenderResponse]:
    """List tenders with optional filters.

    Возвращает постраничный список тендеров с фильтрацией
    по статусу и ответственному менеджеру.

    Аргументы:
        status: Фильтр по статусу тендера.
        assigned_to: Фильтр по ID ответственного.
        pagination: Параметры пагинации.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Постраничный ответ со списком тендеров.
    """
    query = select(Tender)
    count_query = select(func.count(Tender.id))

    if status:
        query = query.where(Tender.status == status)
        count_query = count_query.where(Tender.status == status)
    if assigned_to:
        query = query.where(Tender.assigned_to == assigned_to)
        count_query = count_query.where(Tender.assigned_to == assigned_to)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.options(selectinload(Tender.customer))
        .order_by(Tender.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    tenders = result.scalars().all()

    return PaginatedResponse(
        items=[TenderResponse.model_validate(t) for t in tenders],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{tender_id}", response_model=TenderDetailResponse)
async def get_tender(
    tender_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TenderDetailResponse:
    """Get tender detail with linked tasks.

    Возвращает полную информацию о тендере,
    включая все привязанные задачи.

    Аргументы:
        tender_id: UUID тендера.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Детальную информацию о тендере.
    """
    tender = await tender_service.get_tender_detail_for_api(db, tender_id)
    if not tender:
        raise NotFoundError("Tender", str(tender_id))

    db_user = await _resolve_db_user(db, user)
    visible_tasks = [t for t in tender.tasks if TaskService.user_can_view_task(t, db_user.id)]

    tender_data = TenderResponse.model_validate(tender).model_dump()
    tender_data["tasks"] = [TaskResponse.model_validate(t) for t in visible_tasks]
    tender_data["checklists"] = [
        TenderChecklistResponse.model_validate(c) for c in tender.checklists
    ]
    tender_data["documents"] = [DocumentResponse.model_validate(d) for d in tender.documents]
    tender_data["comments"] = [TenderCommentResponse.model_validate(c) for c in tender.comments]
    tender_data["allowed_next_statuses"] = tender_pipeline.allowed_next_statuses(tender.status)
    return TenderDetailResponse(**tender_data)


@router.post("/{tender_id}/analysis/retry", response_model=TenderAnalysisRetryResponse)
async def retry_tender_analysis(
    tender_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TenderAnalysisRetryResponse:
    """Queue background re-analysis of tender documents (risks, profitability, bill of works)."""
    _ = user
    result = await db.execute(select(Tender).where(Tender.id == tender_id))
    if result.scalar_one_or_none() is None:
        raise NotFoundError("Tender", str(tender_id))
    await enqueue_analysis_reset_pending(db, tender_id)
    await db.commit()
    schedule_tender_analysis(tender_id)
    return TenderAnalysisRetryResponse(tender_id=tender_id)


@router.post("/{tender_id}/smeta/calculate", response_model=TenderSmetaCalculateResponse)
async def calculate_tender_smeta(
    tender_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TenderSmetaCalculateResponse:
    """Queue background smeta-style estimate from ``bill_of_works`` (optional FGIS context + LLM)."""
    _ = user
    result = await db.execute(select(Tender).where(Tender.id == tender_id))
    if result.scalar_one_or_none() is None:
        raise NotFoundError("Tender", str(tender_id))
    await enqueue_smeta_pending(db, tender_id)
    await db.commit()
    schedule_tender_smeta(tender_id)
    return TenderSmetaCalculateResponse(tender_id=tender_id)


@router.post("/{tender_id}/estimator-task", response_model=TaskResponse, status_code=201)
async def create_tender_estimator_task(
    tender_id: uuid.UUID,
    body: TenderEstimatorTaskRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TaskResponse:
    """Create a high-priority task for an estimator to verify the bill of works / estimate."""
    db_user = await _resolve_db_user(db, user)
    result = await db.execute(select(Tender).where(Tender.id == tender_id))
    tender = result.scalar_one_or_none()
    if not tender:
        raise NotFoundError("Tender", str(tender_id))

    desc = body.description or (
        "Проверить и доработать ведомость работ по тендеру. "
        "См. разделы анализа и документы в карточке."
    )
    custom_fields: dict[str, Any] = {}
    attach_meta: list[dict[str, str]] = []
    if body.attachment_document_ids:
        doc_res = await db.execute(
            select(Document.id, Document.filename).where(
                Document.id.in_(body.attachment_document_ids),
                Document.tender_id == tender_id,
            )
        )
        found = {str(r[0]): r[1] for r in doc_res.all()}
        missing = [str(x) for x in body.attachment_document_ids if str(x) not in found]
        if missing:
            raise ValidationError("attachment_document_ids", f"Documents not on this tender: {missing}")
        for doc_id, fn in found.items():
            attach_meta.append({"id": doc_id, "filename": fn})
        custom_fields["tender_attachments"] = attach_meta
        names = ", ".join(found[x] for x in found)
        desc = f"{desc}\n\nПрикреплённые файлы тендера: {names}"

    task = await TaskService.create_task(
        db,
        {
            "title": f"Смета и ведомость работ: {tender.title[:200]}",
            "description": desc,
            "tender_id": tender_id,
            "priority": "high",
            "assigned_to": body.assigned_to,
            "custom_fields": custom_fields,
        },
        {"id": db_user.id},
    )
    await db.commit()
    loaded = await TaskService.get_task(db, task.id, only_active=False)
    await TaskNotificationService.notify_after_task_created(db, loaded, db_user.id)
    return TaskResponse.model_validate(loaded)


@router.patch("/{tender_id}/bill-of-works", response_model=TenderResponse)
async def patch_tender_bill_of_works(
    tender_id: uuid.UUID,
    body: TenderBillOfWorksPatch,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TenderResponse:
    """Merge edited bill of works into ``tender_analysis`` (JSONB)."""
    _ = user
    result = await db.execute(select(Tender).where(Tender.id == tender_id))
    tender = result.scalar_one_or_none()
    if not tender:
        raise NotFoundError("Tender", str(tender_id))
    base = dict(tender.tender_analysis) if tender.tender_analysis else {}
    base["bill_of_works"] = [dict(x) for x in body.bill_of_works]
    if body.bill_of_works_notes is not None:
        base["bill_of_works_notes"] = body.bill_of_works_notes
    base["bill_of_works_manual_edit_at"] = datetime.now(timezone.utc).isoformat()
    tender.tender_analysis = base
    await db.flush()
    result = await db.execute(
        select(Tender).options(selectinload(Tender.customer)).where(Tender.id == tender_id)
    )
    tender_out = result.scalar_one()
    await db.commit()
    return TenderResponse.model_validate(tender_out)


@router.post("/{tender_id}/tasks-from-bill", response_model=list[TaskResponse], status_code=201)
async def create_tasks_from_bill(
    tender_id: uuid.UUID,
    body: TenderTasksFromBillRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[TaskResponse]:
    """Create one task per bill row (or selected indices)."""
    db_user = await _resolve_db_user(db, user)
    result = await db.execute(select(Tender).where(Tender.id == tender_id))
    tender = result.scalar_one_or_none()
    if not tender:
        raise NotFoundError("Tender", str(tender_id))
    ta = tender.tender_analysis or {}
    rows = ta.get("bill_of_works") or []
    if not isinstance(rows, list) or not rows:
        raise ValidationError("bill_of_works", "No bill of works rows on this tender.")
    if body.row_indices is not None:
        picked: list[Any] = []
        for i in body.row_indices:
            if isinstance(i, int) and 0 <= i < len(rows):
                picked.append(rows[i])
        rows = picked
    if not rows:
        raise ValidationError("row_indices", "No rows selected.")
    if len(rows) > 100:
        raise ValidationError("rows", "Maximum 100 tasks per request.")

    out_tasks: list[Any] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        pos = str(row.get("position") or "").strip()
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        unit = str(row.get("unit") or "").strip()
        qty = str(row.get("quantity") or "").strip()
        remarks = str(row.get("remarks") or "").strip()
        title = f"{pos} {name}".strip() if pos else name
        title = title[:500]
        desc_parts = [
            f"Тендер: {tender.title}",
            f"Ед. изм.: {unit}" if unit else None,
            f"Количество: {qty}" if qty else None,
            f"Примечание: {remarks}" if remarks else None,
        ]
        description = "\n".join(p for p in desc_parts if p)
        task = await TaskService.create_task(
            db,
            {
                "title": title,
                "description": description,
                "tender_id": tender_id,
                "priority": "medium",
                "assigned_to": body.assigned_to,
            },
            {"id": db_user.id},
        )
        out_tasks.append(task)

    await db.commit()
    loaded_responses: list[TaskResponse] = []
    for t in out_tasks:
        full = await TaskService.get_task(db, t.id, only_active=False)
        await TaskNotificationService.notify_after_task_created(db, full, db_user.id)
        loaded_responses.append(TaskResponse.model_validate(full))
    return loaded_responses


@router.post("/{tender_id}/comments", response_model=TenderCommentResponse, status_code=201)
async def create_tender_comment(
    tender_id: uuid.UUID,
    body: TenderCommentCreate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TenderCommentResponse:
    """Create a comment for a tender with optional attachments.

    Validates that attachment documents belong to the same tender.
    """

    result = await db.execute(select(Tender).where(Tender.id == tender_id))
    tender = result.scalar_one_or_none()
    if not tender:
        raise NotFoundError("Tender", str(tender_id))

    db_user = await _resolve_db_user(db, user)

    clean_body = (body.body or "").strip()
    attachment_ids = body.attachment_doc_ids or []
    if not clean_body and not attachment_ids:
        raise ValidationError("body", "Empty comment. Provide text or attachments.")

    if attachment_ids:
        doc_q = select(Document.id).where(
            Document.id.in_(attachment_ids),
            Document.tender_id == tender_id,
        )
        doc_res = await db.execute(doc_q)
        doc_ids = {str(x) for x in doc_res.scalars().all()}
        missing = [str(x) for x in attachment_ids if str(x) not in doc_ids]
        if missing:
            raise ValidationError("attachment_doc_ids", f"Some attachments are not linked to tender: {missing}")

    comment = TenderComment(
        tender_id=tender_id,
        author_id=db_user.id,
        body=clean_body,
        mentions=[str(m) for m in body.mentions],
        attachments=[str(x) for x in attachment_ids],
    )
    db.add(comment)
    await db.flush()
    await db.refresh(comment)
    return TenderCommentResponse.model_validate(comment)


@router.patch("/{tender_id}", response_model=TenderResponse)
async def update_tender(
    tender_id: uuid.UUID,
    body: TenderUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TenderResponse:
    """Update tender fields.

    Частичное обновление полей тендера.

    Аргументы:
        tender_id: UUID тендера.
        body: Данные для обновления.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Обновлённый тендер.
    """
    result = await db.execute(select(Tender).where(Tender.id == tender_id))
    tender = result.scalar_one_or_none()
    if not tender:
        raise NotFoundError("Tender", str(tender_id))

    update_data = body.model_dump(exclude_unset=True)
    if "status" in update_data:
        new_status = update_data["status"]
        deny = tender_pipeline.transition_denial_reason(tender.status, new_status)
        if deny:
            raise TenderTransitionError(
                str(tender_id),
                tender.status,
                new_status,
                deny,
            )
    if update_data:
        await db.execute(
            update(Tender).where(Tender.id == tender_id).values(**update_data)
        )
        await db.flush()

    result = await db.execute(
        select(Tender).options(selectinload(Tender.customer)).where(Tender.id == tender_id)
    )
    tender_out = result.scalar_one()
    return TenderResponse.model_validate(tender_out)


@router.post("/{tender_id}/transition", response_model=TenderResponse)
async def transition_tender_status(
    tender_id: uuid.UUID,
    body: TenderTransitionRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TenderResponse:
    """Move tender to the next allowed pipeline status.

    Validates transition against the configured tender lifecycle graph.
    Optional reason is appended to internal notes (audit trail).
    """
    _ = user
    await tender_service.apply_tender_status_transition(
        db, tender_id, body.to_status, body.reason
    )

    out = await db.execute(
        select(Tender).options(selectinload(Tender.customer)).where(Tender.id == tender_id)
    )
    return TenderResponse.model_validate(out.scalar_one())


@router.post("/{tender_id}/link-tasks", response_model=TenderDetailResponse)
async def link_tasks_to_tender(
    tender_id: uuid.UUID,
    body: LinkTasksRequest,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TenderDetailResponse:
    """Link tasks to a tender.

    Привязывает список задач к тендеру, устанавливая
    tender_id в каждой указанной задаче.

    Аргументы:
        tender_id: UUID тендера.
        body: Список ID задач для привязки.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Обновлённый тендер с задачами.
    """
    db_user = await _resolve_db_user(db, user)
    await tender_service.link_tasks_to_tender(
        db, tender_id, list(body.task_ids), viewer_user_id=db_user.id
    )

    return await get_tender(tender_id, db, user)


@router.post(
    "/{tender_id}/checklists/items/{item_id}/toggle",
    response_model=TenderChecklistItemResponse,
)
async def toggle_tender_checklist_item(
    tender_id: uuid.UUID,
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TenderChecklistItemResponse:
    """Toggle completion state of a tender checklist item."""
    db_user = await _resolve_db_user(db, user)
    stmt = (
        select(TenderChecklistItem)
        .join(TenderChecklist, TenderChecklistItem.checklist_id == TenderChecklist.id)
        .where(TenderChecklist.tender_id == tender_id, TenderChecklistItem.id == item_id)
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        raise NotFoundError("TenderChecklistItem", str(item_id))

    if item.is_completed:
        item.is_completed = False
        item.completed_by = None
        item.completed_at = None
    else:
        item.is_completed = True
        item.completed_by = db_user.id
        item.completed_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(item)
    return TenderChecklistItemResponse.model_validate(item)


@router.patch(
    "/{tender_id}/checklists/items/{item_id}",
    response_model=TenderChecklistItemResponse,
)
async def update_tender_checklist_item(
    tender_id: uuid.UUID,
    item_id: uuid.UUID,
    body: TenderChecklistItemUpdate,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> TenderChecklistItemResponse:
    """Update a tender checklist item (link calculation task / set completion)."""
    db_user = await _resolve_db_user(db, user)
    stmt = (
        select(TenderChecklistItem)
        .join(TenderChecklist, TenderChecklistItem.checklist_id == TenderChecklist.id)
        .where(TenderChecklist.tender_id == tender_id, TenderChecklistItem.id == item_id)
    )
    result = await db.execute(stmt)
    item = result.scalar_one_or_none()
    if not item:
        raise NotFoundError("TenderChecklistItem", str(item_id))

    payload = body.model_dump(exclude_unset=True)

    if "calculation_task_id" in payload:
        if item.item_type != "calculation":
            raise ValidationError("item_type", "Only calculation item supports linked task")

        task_id = payload["calculation_task_id"]
        if task_id is not None:
            task_stmt = select(Task).where(
                Task.id == task_id,
                Task.tender_id == tender_id,
                Task.active_filter(),
                TaskService.sql_task_visible_to_user(db_user.id),
            )
            task_res = await db.execute(task_stmt)
            if task_res.scalar_one_or_none() is None:
                raise NotFoundError("Task", str(task_id))

        item.calculation_task_id = task_id

    if "is_completed" in payload:
        if payload["is_completed"]:
            item.is_completed = True
            item.completed_by = db_user.id
            item.completed_at = datetime.now(timezone.utc)
        else:
            item.is_completed = False
            item.completed_by = None
            item.completed_at = None

    await db.flush()
    await db.refresh(item)
    return TenderChecklistItemResponse.model_validate(item)


@router.delete("/{tender_id}", status_code=204)
async def delete_tender(
    tender_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> None:
    """Delete a tender.

    Удаляет тендер. Привязанные задачи не удаляются —
    обнуляется их tender_id.

    Аргументы:
        tender_id: UUID тендера.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.
    """
    result = await db.execute(select(Tender).where(Tender.id == tender_id))
    tender = result.scalar_one_or_none()
    if not tender:
        raise NotFoundError("Tender", str(tender_id))

    # Remove documents linked to this tender (including their files in MinIO).
    documents_result = await db.execute(select(Document).where(Document.tender_id == tender_id))
    documents = documents_result.scalars().all()
    if documents:
        try:
            s3 = _get_s3_client(settings)
            for doc in documents:
                try:
                    s3.delete_object(Bucket=settings.minio_bucket, Key=doc.storage_path)
                except Exception as exc:
                    # Keep going; we will remove DB records anyway.
                    logger.warning(
                        "MinIO delete for tender document failed",
                        error=str(exc),
                        tender_id=str(tender_id),
                        document_id=str(doc.id),
                    )
        except Exception as exc:
            logger.warning("MinIO client init/delete failed", error=str(exc), tender_id=str(tender_id))

        for doc in documents:
            await db.delete(doc)

    await db.execute(update(Task).where(Task.tender_id == tender_id).values(tender_id=None))
    await db.delete(tender)
    await db.flush()
