"""Database models for multi-user support."""

from datetime import datetime
from typing import Optional
import uuid

from fastapi_users.db import SQLAlchemyBaseUserTable
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class User(SQLAlchemyBaseUserTable[uuid.UUID], Base):
    """User model for authentication."""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        String(36), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(320), unique=True, index=True, nullable=False
    )
    hashed_password: Mapped[str] = mapped_column(String(1024), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Additional user fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationship to documents
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="owner", cascade="all, delete-orphan"
    )


class Document(Base):
    """Document model for storing user documents."""
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # User relationship
    user_id: Mapped[uuid.UUID] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Document metadata
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")

    # Document content (JSON stored as text)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
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
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Snapshot metadata
    snapshot_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Snapshot content (JSON stored as text)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    # Relationships
    document: Mapped[Document] = relationship("Document", back_populates="snapshots")

    def __repr__(self) -> str:
        return f"<DocumentSnapshot(id={self.id}, name={self.snapshot_name}, document_id={self.document_id})>"
