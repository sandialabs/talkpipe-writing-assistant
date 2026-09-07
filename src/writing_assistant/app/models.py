"""Database models for multi-user support."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi_users.db import SQLAlchemyBaseUserTable
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import CHAR, TypeDecorator, TypeEngine


def utcnow() -> datetime:
    """Current UTC time as a naive datetime, the form the timestamp columns store.

    The columns are ``DateTime`` without ``timezone=True``, so SQLite hands
    back naive values regardless of what was written; keeping writes naive
    (and UTC) means every stored row means the same thing. Attach the offset
    when serialising — see ``iso_utc``.
    """
    return datetime.now(UTC).replace(tzinfo=None)


def iso_utc(value: datetime) -> str:
    """Serialise a stored (naive UTC) timestamp with an explicit ``+00:00``.

    Without the offset, ``new Date(...)`` in a browser reads the string as
    local time and shows the UTC wall-clock shifted by the user's zone.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


class GUID(TypeDecorator[uuid.UUID]):
    """Platform-independent GUID type.

    Uses PostgreSQL's UUID type, otherwise uses CHAR(36), storing as stringified hex values.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine[Any]:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID())
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(
        self, value: uuid.UUID | str | None, dialect: Dialect
    ) -> str | None:
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        if not isinstance(value, uuid.UUID):
            return str(uuid.UUID(value))
        return str(value)

    def process_result_value(
        self, value: uuid.UUID | str | None, dialect: Dialect
    ) -> uuid.UUID | None:
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(value)
        return value


class Base(DeclarativeBase):
    """Base class for all database models."""


class User(SQLAlchemyBaseUserTable[uuid.UUID], Base):
    """User model for authentication."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(
        String(320), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(1024), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Additional user fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    # User preferences (JSON stored as text)
    preferences: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    # Relationship to documents
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="owner", cascade="all, delete-orphan"
    )
    templates: Mapped[list["WritingTemplate"]] = relationship(
        "WritingTemplate", back_populates="owner", cascade="all, delete-orphan"
    )


class Document(Base):
    """Document model for storing user documents."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # User relationship
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Document metadata
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    # Document content (JSON stored as text)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    # Relationships
    owner: Mapped[User] = relationship("User", back_populates="documents")
    snapshots: Mapped[list["DocumentSnapshot"]] = relationship(
        "DocumentSnapshot", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename={self.filename}, user_id={self.user_id})>"


class DocumentSnapshot(Base):
    """Snapshot model for document history."""

    __tablename__ = "document_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Document relationship
    document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Snapshot metadata
    snapshot_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Snapshot content (JSON stored as text)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )

    # Relationships
    document: Mapped[Document] = relationship("Document", back_populates="snapshots")

    def __repr__(self) -> str:
        return f"<DocumentSnapshot(id={self.id}, name={self.snapshot_name}, document_id={self.document_id})>"


class WritingTemplate(Base):
    """A named, reusable set of writing settings (quick-access template).

    Templates are per user and shared by every client (web UI and TUI), so
    they live on the server rather than in a browser's local storage. The
    settings are the document-metadata fields of the Writing Settings tab
    (style, audience, tone, context, directive, word limit), stored as JSON.
    """

    __tablename__ = "writing_templates"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_writing_templates_user_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    settings: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )

    owner: Mapped[User] = relationship("User", back_populates="templates")

    def __repr__(self) -> str:
        return (
            f"<WritingTemplate(id={self.id}, name={self.name}, user_id={self.user_id})>"
        )
