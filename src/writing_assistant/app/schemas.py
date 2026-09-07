"""Pydantic schemas for API models."""

import uuid
from datetime import datetime

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
    is_active: bool | None = True
    is_superuser: bool | None = False
    is_verified: bool | None = False


class UserUpdate(schemas.BaseUserUpdate):
    """Schema for updating user data."""

    password: str | None = None
    email: EmailStr | None = None
    is_active: bool | None = None
    is_superuser: bool | None = None
    is_verified: bool | None = None


class PasswordChange(BaseModel):
    """Body of POST /user/change-password.

    The current password is required so that a leaked bearer token alone
    cannot be used to take over the account (the fastapi-users
    ``PATCH /users/me`` route, which does not ask for it, is not mounted).
    """

    current_password: str
    new_password: str


class EmailChange(BaseModel):
    """Body of POST /user/change-email.

    Same rule as PasswordChange: the email is where a password reset
    goes, so moving it requires the current password.
    """

    current_password: str
    new_email: EmailStr


# Document schemas
class DocumentBase(BaseModel):
    """Base document schema."""

    filename: str
    title: str
    content: str


class DocumentCreate(DocumentBase):
    """Schema for creating a document."""


class DocumentUpdate(BaseModel):
    """Schema for updating a document."""

    filename: str | None = None
    title: str | None = None
    content: str | None = None


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


class SnapshotRead(SnapshotBase):
    """Schema for reading a snapshot."""

    id: int
    document_id: int
    created_at: datetime

    class Config:
        from_attributes = True
