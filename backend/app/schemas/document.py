"""Schemas for document and file management entities.

Схемы валидации для загрузки, метаданных и скачивания
документов, хранящихся в MinIO.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    """Schema for document API response.

    Атрибуты:
        id (uuid.UUID): Уникальный идентификатор документа.
        task_id (uuid.UUID | None): ID задачи.
        uploaded_by (uuid.UUID): ID загрузившего пользователя.
        doc_type (str): Тип документа.
        label (str | None): Метка документа.
        filename (str): Исходное имя файла.
        storage_path (str): Путь в MinIO.
        mime_type (str): MIME-тип файла.
        file_size (int): Размер файла в байтах.
        version (int): Текущая версия.
        metadata (dict): Дополнительные данные.
        description (str | None): Описание.
        created_at (datetime): Дата создания.
        updated_at (datetime): Дата обновления.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID | None = None
    uploaded_by: uuid.UUID
    doc_type: str
    label: str | None = None
    filename: str
    storage_path: str
    mime_type: str
    file_size: int
    version: int
    metadata: dict = Field(default_factory=dict)
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentDownloadResponse(BaseModel):
    """Schema for document download redirect.

    Атрибуты:
        url (str): Presigned URL для скачивания из MinIO.
        filename (str): Исходное имя файла.
    """

    url: str
    filename: str
