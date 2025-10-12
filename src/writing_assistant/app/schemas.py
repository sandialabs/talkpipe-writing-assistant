"""Pydantic schemas for API models."""

import uuid
from datetime import datetime
from typing import Optional

from fastapi_users import schemas
from pydantic import BaseModel, EmailStr


# User schemas for FastAPI Users
class UserRead(schemas.BaseUser[uuid.UUID]):
    """Schema for reading user data."""
    id: uuid.UUID
    email: EmailStr
    is_active: bool = True
    is_superuser: bool = False
    is_verified: bool = False
    created_at: datetime


class UserCreate(schemas.BaseUserCreate):
    """Schema for creating a new user."""
    email: EmailStr
    password: str
    is_active: Optional[bool] = True
    is_superuser: Optional[bool] = False
    is_verified: Optional[bool] = False


class UserUpdate(schemas.BaseUserUpdate):
    """Schema for updating user data."""
    password: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_superuser: Optional[bool] = None
    is_verified: Optional[bool] = None


# Document schemas
class DocumentBase(BaseModel):
    """Base document schema."""
    filename: str
    title: str
    content: str


class DocumentCreate(DocumentBase):
    """Schema for creating a document."""
    pass


class DocumentUpdate(BaseModel):
    """Schema for updating a document."""
    filename: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None


class DocumentRead(DocumentBase):
    """Schema for reading a document."""
    id: int
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentList(BaseModel):
    """Schema for listing documents."""
    id: int
    filename: str
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Snapshot schemas
class SnapshotBase(BaseModel):
    """Base snapshot schema."""
    snapshot_name: str
    content: str


class SnapshotCreate(SnapshotBase):
    """Schema for creating a snapshot."""
    pass


class SnapshotRead(SnapshotBase):
    """Schema for reading a snapshot."""
    id: int
    document_id: int
    created_at: datetime

    class Config:
        from_attributes = True
