"""Service layer for document/file management with MinIO storage.

Инкапсулирует логику загрузки файлов в MinIO, генерации
presigned URL для скачивания и управления документами задач.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, BinaryIO

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ExternalServiceError, NotFoundError, ValidationError
from app.models.document import Document, DocumentVersion
from app.models.task import Task
from app.models.tender.tender import Tender

logger = logging.getLogger(__name__)


class DocumentService:
    """Document management service with MinIO S3 backend.

    Сервис управления документами. Обеспечивает загрузку файлов
    в MinIO S3, генерацию presigned URL для скачивания,
    версионирование и фильтрацию документов по задачам.
    """

    PRESIGNED_URL_EXPIRY = 3600

    def __init__(self) -> None:
        """Initialize S3 client from application settings.

        Создаёт boto3 S3 клиент с настройками из конфигурации.
        """
        settings = get_settings()
        self._bucket = settings.minio_bucket
        # Internal client for put/delete operations inside Docker network.
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.minio_endpoint,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=BotoConfig(signature_version="s3v4"),
            region_name="us-east-1",
        )
        # Public client for presigned URLs returned to the browser.
        self._presign_client = boto3.client(
            "s3",
            endpoint_url=settings.minio_public_endpoint,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=BotoConfig(signature_version="s3v4"),
            region_name="us-east-1",
        )
        self._ensure_bucket()

    def get_object_bytes(self, storage_path: str) -> bytes:
        """Read object body from MinIO (internal use for processing pipelines).

        Args:
            storage_path: S3 key under the configured bucket.

        Returns:
            Raw file bytes.

        Raises:
            ExternalServiceError: If the object is missing or access fails.
        """
        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=storage_path)
            return resp["Body"].read()
        except ClientError as exc:
            raise ExternalServiceError("MinIO", "get_object", str(exc)) from exc

    def _ensure_bucket(self) -> None:
        """Create the storage bucket if it does not exist.

        Проверяет наличие бакета и создаёт его при отсутствии.
        """
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in ("404", "NoSuchBucket"):
                self._client.create_bucket(Bucket=self._bucket)
            else:
                raise ExternalServiceError(
                    "MinIO", "head_bucket", str(exc)
                ) from exc

    async def upload_file(
        self,
        db: AsyncSession,
        file: BinaryIO,
        task_id: uuid.UUID | None,
        doc_type: str,
        label: str | None,
        user: dict[str, Any],
        *,
        filename: str = "",
        mime_type: str = "application/octet-stream",
        tender_id: uuid.UUID | None = None,
        extra_data: dict[str, Any] | None = None,
        company_id: uuid.UUID | None = None,
    ) -> Document:
        """Upload a file to MinIO and create a Document record.

        Args:
            db (AsyncSession): Асинхронная сессия SQLAlchemy.
            file (BinaryIO): Файловый объект для загрузки.
            task_id (uuid.UUID | None): UUID задачи (может быть None).
            doc_type (str): Тип документа:
                "photo", "signed_act", "invoice", "report", "other".
            label (str | None): Метка документа (например, "indoor_unit_photo").
            user (dict[str, Any]): Текущий пользователь с ключом "id".
            filename (str): Исходное имя файла.
            mime_type (str): MIME-тип файла.
            tender_id (uuid.UUID | None): Optional tender link (CRM тендеры).
            extra_data (dict | None): Optional JSON metadata (e.g. source URL for imports).

        Returns:
            Document: Созданный объект документа.

        Raises:
            ExternalServiceError: При ошибке загрузки в MinIO.
        """
        doc_id = uuid.uuid4()
        storage_path = self._build_storage_path(task_id, tender_id, doc_id, filename)

        file_data = file.read()
        file_size = len(file_data)

        resolved_company_id = company_id
        if resolved_company_id is None and tender_id is not None:
            tr = await db.get(Tender, tender_id)
            if tr is None:
                raise NotFoundError("Tender", str(tender_id))
            resolved_company_id = tr.company_id
        if resolved_company_id is None and task_id is not None:
            tk = await db.get(Task, task_id)
            if tk is None:
                raise NotFoundError("Task", str(task_id))
            resolved_company_id = tk.company_id
        if resolved_company_id is None:
            raise ValidationError(
                "tender_id",
                "Provide tender_id or task_id (or company_id) so the document is tenant-scoped",
            )

        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=storage_path,
                Body=file_data,
                ContentType=mime_type,
            )
        except ClientError as exc:
            raise ExternalServiceError(
                "MinIO", "put_object", str(exc)
            ) from exc

        document = Document(
            id=doc_id,
            company_id=resolved_company_id,
            task_id=task_id,
            tender_id=tender_id,
            uploaded_by=user["id"],
            doc_type=doc_type,
            label=label,
            filename=filename,
            storage_path=storage_path,
            mime_type=mime_type,
            file_size=file_size,
            version=1,
            extra_data=dict(extra_data) if extra_data else {},
        )
        db.add(document)

        version = DocumentVersion(
            id=uuid.uuid4(),
            document_id=doc_id,
            version=1,
            storage_path=storage_path,
            file_size=file_size,
            uploaded_by=user["id"],
        )
        db.add(version)

        await db.flush()
        await db.refresh(document)
        return document

    def get_download_url(self, document_id: uuid.UUID, storage_path: str) -> str:
        """Generate a presigned download URL for a document.

        Args:
            document_id (uuid.UUID): UUID документа (для логирования).
            storage_path (str): Путь к файлу в MinIO (bucket key).

        Returns:
            str: Presigned URL для скачивания, действительный
                PRESIGNED_URL_EXPIRY секунд.

        Raises:
            ExternalServiceError: При ошибке генерации URL.
        """
        try:
            return self._presign_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": storage_path},
                ExpiresIn=self.PRESIGNED_URL_EXPIRY,
            )
        except ClientError as exc:
            raise ExternalServiceError(
                "MinIO", "generate_presigned_url", str(exc)
            ) from exc

    @staticmethod
    async def list_documents(
        db: AsyncSession,
        task_id: uuid.UUID | None = None,
        doc_type: str | None = None,
    ) -> list[Document]:
        """List documents with optional filters.

        Args:
            db (AsyncSession): Асинхронная сессия SQLAlchemy.
            task_id (uuid.UUID | None): UUID задачи для фильтрации.
            doc_type (str | None): Тип документа для фильтрации.

        Returns:
            list[Document]: Список документов, отсортированных по дате создания (desc).
        """
        stmt = select(Document)

        if task_id is not None:
            stmt = stmt.where(Document.task_id == task_id)
        if doc_type is not None:
            stmt = stmt.where(Document.doc_type == doc_type)

        stmt = stmt.order_by(Document.created_at.desc())

        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _build_storage_path(
        task_id: uuid.UUID | None,
        tender_id: uuid.UUID | None,
        doc_id: uuid.UUID,
        filename: str,
    ) -> str:
        """Build the S3 object key for a document.

        Args:
            task_id: UUID задачи (используется как префикс пути).
            tender_id: UUID тендера (если файл привязан к тендеру без задачи).
            doc_id: UUID документа.
            filename: Исходное имя файла.

        Returns:
            str: S3 object key в формате "tasks/{task_id}/{doc_id}/{filename}"
                или "unlinked/{doc_id}/{filename}".
        """
        safe_filename = filename.replace("/", "_").replace("\\", "_") or "file"
        if task_id:
            return f"tasks/{task_id}/{doc_id}/{safe_filename}"
        if tender_id:
            return f"tenders/{tender_id}/{doc_id}/{safe_filename}"
        return f"unlinked/{doc_id}/{safe_filename}"
