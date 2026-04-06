"""Document management API endpoints.

Загрузка файлов в MinIO, метаданные документов,
скачивание по presigned URL.
"""

import uuid

import structlog
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.dependencies import PaginationParams, get_current_user, get_db
from app.core.exceptions import ExternalServiceError, NotFoundError
from app.core.pagination import PaginatedResponse
from app.core.security import CurrentUser
from app.models import Document, User
from app.schemas.document import DocumentDownloadResponse, DocumentResponse

logger = structlog.get_logger()

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


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    task_id: uuid.UUID | None = Form(default=None),
    doc_type: str = Form(default="other"),
    label: str | None = Form(default=None),
    description: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> DocumentResponse:
    """Upload a file to MinIO storage.

    Загружает файл в MinIO, создаёт запись Document в БД
    с метаданными файла.

    Аргументы:
        file: Загружаемый файл.
        task_id: ID задачи для привязки.
        doc_type: Тип документа — photo, signed_act, invoice, report, other.
        label: Метка документа.
        description: Описание файла.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.
        settings: Настройки приложения.

    Возвращает:
        Метаданные загруженного документа.
    """
    user_result = await db.execute(
        select(User).where(User.keycloak_id == user.sub)
    )
    db_user = user_result.scalar_one_or_none()
    if not db_user:
        raise NotFoundError("User", user.sub)

    file_content = await file.read()
    file_size = len(file_content)
    filename = file.filename or "unnamed"
    content_type = file.content_type or "application/octet-stream"

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
        task_id=task_id,
        uploaded_by=db_user.id,
        doc_type=doc_type,
        label=label,
        filename=filename,
        storage_path=storage_key,
        mime_type=content_type,
        file_size=file_size,
        version=1,
        metadata={},
        description=description,
    )
    db.add(document)
    await db.flush()
    await db.refresh(document)
    return DocumentResponse.model_validate(document)


@router.get("/", response_model=PaginatedResponse[DocumentResponse])
async def list_documents(
    task_id: uuid.UUID | None = Query(default=None, description="Filter by task"),
    doc_type: str | None = Query(default=None, description="Filter by document type"),
    pagination: PaginationParams = Depends(),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> PaginatedResponse[DocumentResponse]:
    """List documents with optional filters.

    Возвращает постраничный список документов
    с фильтрацией по задаче и типу документа.

    Аргументы:
        task_id: Фильтр по ID задачи.
        doc_type: Фильтр по типу документа.
        pagination: Параметры пагинации.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.

    Возвращает:
        Постраничный ответ со списком документов.
    """
    query = select(Document)
    count_query = select(func.count(Document.id))

    if task_id:
        query = query.where(Document.task_id == task_id)
        count_query = count_query.where(Document.task_id == task_id)
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
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise NotFoundError("Document", str(document_id))
    return DocumentResponse.model_validate(document)


@router.get("/{document_id}/download", response_model=DocumentDownloadResponse)
async def download_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> DocumentDownloadResponse:
    """Get a presigned URL to download a document from MinIO.

    Генерирует presigned URL для скачивания файла
    из MinIO с ограниченным временем жизни (1 час).

    Аргументы:
        document_id: UUID документа.
        db: Асинхронная сессия БД.
        user: Текущий аутентифицированный пользователь.
        settings: Настройки приложения.

    Возвращает:
        Presigned URL и имя файла.
    """
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if not document:
        raise NotFoundError("Document", str(document_id))

    try:
        s3 = _get_s3_client(settings)
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
    result = await db.execute(select(Document).where(Document.id == document_id))
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
