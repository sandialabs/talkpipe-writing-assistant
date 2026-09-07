"""Pydantic schemas for API models."""

import uuid
from datetime import datetime
from typing import Any

from fastapi_users import schemas
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


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


# Quick-access template schemas
class TemplateSettings(BaseModel):
    """The writing settings a template stores.

    These are the Writing Settings fields of a document's metadata. AI
    source/model and connection settings are deliberately not part of a
    template: they describe where to generate, not how to write. Unknown
    keys (a client posting a whole metadata dict) are ignored.
    """

    model_config = ConfigDict(extra="ignore")

    writing_style: str = "formal"
    target_audience: str = ""
    tone: str = "neutral"
    background_context: str = ""
    generation_directive: str = ""
    word_limit: int | None = None

    @field_validator("word_limit", mode="before")
    @classmethod
    def _blank_word_limit_is_none(cls, value: Any) -> Any:
        # The web form's number field is "" when empty.
        if isinstance(value, str) and not value.strip():
            return None
        return value


class TemplateSave(BaseModel):
    """Body of ``POST /templates/save``: create or replace by name."""

    name: str = Field(min_length=1, max_length=100)
    settings: TemplateSettings

    @field_validator("name")
    @classmethod
    def _name_is_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Template name must not be blank")
        return stripped
