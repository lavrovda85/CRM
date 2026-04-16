"""Document management API endpoints.

Загрузка файлов в MinIO, метаданные документов,
скачивание через presigned URL или прокси через API (см. ``document_file_proxy_enabled``).
"""

import asyncio
import uuid
import logging
from urllib.parse import quote

try:
    import structlog  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    structlog = None  # type: ignore
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.company_context import ActiveCompanyContext, get_active_company
from app.core.config import Settings, get_settings
from app.core.dependencies import PaginationParams, get_current_user, get_db
from app.core.exceptions import ExternalServiceError, NotFoundError, ValidationError
from app.core.file_proxy_token import (
    content_disposition_header,
    decode_document_file_token,
    encode_document_file_token,
)
from app.core.pagination import PaginatedResponse
from app.core.security import CurrentUser
from app.models import Document, Task, Tender, User
from app.schemas.document import DocumentDownloadResponse, DocumentResponse
from app.services.tender.tender_analysis_queue import schedule_tender_analysis
from app.services.user_identity import resolve_users_table_id

logger = structlog.get_logger() if structlog is not None else logging.getLogger(__name__)

router = APIRouter(prefix="/documents")


def _get_s3_client(settings: Settings):
    """Build a boto3 S3 client configured for MinIO.

    Создаёт клиент boto3 с настройками подключения к MinIO.

    Аргументы:
        settings: Настройки приложения.

    Возвращает:
        Клиент boto3 для S3-совместимого хранилища.
    """
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


def _get_presign_s3_client(settings: Settings):
    """Build an S3 client for presigned URL generation.

    This client must use an endpoint reachable from the user's browser.
    """
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.minio_public_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    task_id: uuid.UUID | None = Form(default=None),
    tender_id: uuid.UUID | None = Form(default=None),
    doc_type: str = Form(default="other"),
    label: str | None = Form(default=None),
    description: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    ctx: ActiveCompanyContext = Depends(get_active_company),
    settings: Settings = Depends(get_settings),
) -> DocumentResponse:
    """Upload a file to MinIO storage.

    Загружает файл в MinIO, создаёт запись Document в БД
    с метаданными файла.

    Аргументы:
        file: Загружаемый файл.
        task_id: ID задачи для привязки.
        tender_id: ID тендера для привязки.
        doc_type: Тип документа — photo, signed_act, invoice, report, other.
        label: Метка документа.
        description: Описание файла.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.
        settings: Настройки приложения.

    Возвращает:
        Метаданные загруженного документа.
    """
    uid = await resolve_users_table_id(db, user)
    db_user = await db.get(User, uid)
    if not db_user:
        raise NotFoundError("User", user.sub)

    file_content = await file.read()
    file_size = len(file_content)
    filename = file.filename or "unnamed"
    content_type = file.content_type or "application/octet-stream"

    company_id = ctx.company_id
    if tender_id is not None:
        tr = await db.get(Tender, tender_id)
        if tr is None:
            raise NotFoundError("Tender", str(tender_id))
        if tr.company_id != ctx.company_id:
            raise NotFoundError("Tender", str(tender_id))
        company_id = tr.company_id
    elif task_id is not None:
        tk = await db.get(Task, task_id)
        if tk is None:
            raise NotFoundError("Task", str(task_id))
        if tk.company_id != ctx.company_id:
            raise NotFoundError("Task", str(task_id))
        company_id = tk.company_id

    doc_id = uuid.uuid4()
    storage_key = f"documents/{doc_id}/{filename}"

    try:
        s3 = _get_s3_client(settings)
        s3.put_object(
            Bucket=settings.minio_bucket,
            Key=storage_key,
            Body=file_content,
            ContentType=content_type,
        )
    except Exception as exc:
        logger.error("MinIO upload failed", error=str(exc), key=storage_key)
        raise ExternalServiceError(
            service="MinIO",
            operation="put_object",
            detail=str(exc),
        ) from exc

    document = Document(
        id=doc_id,
        company_id=company_id,
        task_id=task_id,
        tender_id=tender_id,
        uploaded_by=db_user.id,
        doc_type=doc_type,
        label=label,
        filename=filename,
        storage_path=storage_key,
        mime_type=content_type,
        file_size=file_size,
        version=1,
        extra_data={},
        description=description,
    )
    db.add(document)
    await db.flush()
    await db.refresh(document)
    await db.commit()
    if tender_id:
        schedule_tender_analysis(tender_id)
    return DocumentResponse.model_validate(document)


@router.get("", response_model=PaginatedResponse[DocumentResponse])
async def list_documents(
    task_id: uuid.UUID | None = Query(default=None, description="Filter by task"),
    tender_id: uuid.UUID | None = Query(default=None, description="Filter by tender"),
    doc_type: str | None = Query(default=None, description="Filter by document type"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    ctx: ActiveCompanyContext = Depends(get_active_company),
) -> PaginatedResponse[DocumentResponse]:
    """List documents with optional filters.

    Возвращает постраничный список документов
    с фильтрацией по задаче и типу документа.

    Аргументы:
        task_id: Фильтр по ID задачи.
        tender_id: Фильтр по ID тендера.
        doc_type: Фильтр по типу документа.
        pagination: Параметры пагинации.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Постраничный ответ со списком документов.
    """
    _ = user.sub
    query = select(Document).where(Document.company_id == ctx.company_id)
    count_query = select(func.count(Document.id)).where(Document.company_id == ctx.company_id)  # pylint: disable=not-callable

    if task_id:
        query = query.where(Document.task_id == task_id)
        count_query = count_query.where(Document.task_id == task_id)
    if tender_id:
        query = query.where(Document.tender_id == tender_id)
        count_query = count_query.where(Document.tender_id == tender_id)
    if doc_type:
        query = query.where(Document.doc_type == doc_type)
        count_query = count_query.where(Document.doc_type == doc_type)

    total = (await db.execute(count_query)).scalar() or 0
    result = await db.execute(
        query.order_by(Document.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    documents = result.scalars().all()

    return PaginatedResponse(
        items=[DocumentResponse.model_validate(d) for d in documents],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    ctx: ActiveCompanyContext = Depends(get_active_company),
) -> DocumentResponse:
    """Get document metadata.

    Возвращает метаданные документа без содержимого файла.

    Аргументы:
        document_id: UUID документа.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Метаданные документа.
    """
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.company_id == ctx.company_id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise NotFoundError("Document", str(document_id))
    _ = user.sub
    return DocumentResponse.model_validate(document)


@router.get("/{document_id}/file")
async def stream_document_file(
    document_id: uuid.UUID,
    token: str = Query(..., min_length=8, description="Signed token from GET /documents/{id}/download"),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    """Stream document bytes from MinIO (internal Docker network); browser uses ``?token=`` from /download."""
    if not settings.document_file_proxy_enabled:
        raise NotFoundError("Document", str(document_id))

    payload = decode_document_file_token(settings.secret_key, token, max_age=3600)
    if not payload or str(document_id) != payload.get("d"):
        raise ValidationError("token", "Invalid or expired download token")

    try:
        company_id = uuid.UUID(str(payload.get("c")))
    except (ValueError, TypeError) as exc:
        raise ValidationError("token", "Invalid download token payload") from exc

    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.company_id == company_id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise NotFoundError("Document", str(document_id))

    def _load() -> tuple[bytes, str]:
        s3 = _get_s3_client(settings)
        resp = s3.get_object(Bucket=settings.minio_bucket, Key=document.storage_path)
        body = resp["Body"].read()
        ct = (resp.get("ContentType") or document.mime_type or "application/octet-stream").strip()
        return body, ct

    try:
        data, content_type = await asyncio.to_thread(_load)
    except Exception as exc:
        logger.error("MinIO get_object failed", error=str(exc), document_id=str(document_id))
        raise ExternalServiceError("MinIO", "get_object", str(exc)) from exc

    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": content_disposition_header(document.filename, content_type)},
    )


@router.get("/{document_id}/download", response_model=DocumentDownloadResponse)
async def download_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    ctx: ActiveCompanyContext = Depends(get_active_company),
    settings: Settings = Depends(get_settings),
) -> DocumentDownloadResponse:
    """Return a URL to download the document (API proxy with token, or legacy MinIO presigned URL).

    When ``DOCUMENT_FILE_PROXY_ENABLED`` is true (default), ``url`` is same-origin
    ``/api/v1/documents/{id}/file?token=...`` so the browser never calls MinIO directly.

    Аргументы:
        document_id: UUID документа.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.
        settings: Настройки приложения.

    Возвращает:
        Download URL и имя файла.
    """
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.company_id == ctx.company_id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise NotFoundError("Document", str(document_id))

    if settings.document_file_proxy_enabled:
        raw = encode_document_file_token(
            settings.secret_key,
            document_id=document.id,
            company_id=document.company_id,
            user_sub=user.sub or "",
        )
        url = f"/api/v1/documents/{document_id}/file?token={quote(raw, safe='')}"
        return DocumentDownloadResponse(url=url, filename=document.filename)

    try:
        s3 = _get_presign_s3_client(settings)
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.minio_bucket, "Key": document.storage_path},
            ExpiresIn=3600,
        )
    except Exception as exc:
        logger.error("MinIO presigned URL generation failed", error=str(exc))
        raise ExternalServiceError(
            service="MinIO",
            operation="generate_presigned_url",
            detail=str(exc),
        ) from exc

    return DocumentDownloadResponse(url=url, filename=document.filename)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    ctx: ActiveCompanyContext = Depends(get_active_company),
    settings: Settings = Depends(get_settings),
) -> None:
    """Delete a document and its file from MinIO.

    Удаляет документ из БД и файл из MinIO хранилища.

    Аргументы:
        document_id: UUID документа.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.
        settings: Настройки приложения.
    """
    _ = user.sub
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.company_id == ctx.company_id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise NotFoundError("Document", str(document_id))

    try:
        s3 = _get_s3_client(settings)
        s3.delete_object(
            Bucket=settings.minio_bucket,
            Key=document.storage_path,
        )
    except Exception as exc:
        logger.warning("MinIO delete failed, removing DB record anyway", error=str(exc))

    await db.delete(document)
    await db.flush()
