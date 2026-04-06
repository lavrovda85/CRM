"""Document and version models for file management.

Документы (фото, акты, PDF) привязаны к задачам,
хранятся в MinIO с поддержкой версионирования.
"""

import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Document(BaseModel):
    """File attachment linked to a task.

    Атрибуты:
        task_id: ID задачи.
        uploaded_by: ID загрузившего пользователя.
        doc_type: Тип документа (photo, signed_act, invoice, report, other).
        label: Метка документа (indoor_unit_installed, etc.).
        filename: Исходное имя файла.
        storage_path: Путь в MinIO (bucket/key).
        mime_type: MIME-тип файла.
        file_size: Размер файла в байтах.
        version: Текущая версия.
        metadata: Дополнительные данные (EXIF, GPS, подпись).
    """

    __tablename__ = "documents"

    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False, default="other", index=True)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    task = relationship("Task", back_populates="documents")
    uploader = relationship("User", foreign_keys=[uploaded_by])
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan",
                            order_by="DocumentVersion.version")


class DocumentVersion(BaseModel):
    """Historical version of a document.

    Атрибуты:
        document_id: ID документа.
        version: Номер версии.
        storage_path: Путь к этой версии в MinIO.
        file_size: Размер файла в байтах.
        uploaded_by: ID загрузившего пользователя.
    """

    __tablename__ = "document_versions"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    document = relationship("Document", back_populates="versions")
    uploader = relationship("User", foreign_keys=[uploaded_by])
