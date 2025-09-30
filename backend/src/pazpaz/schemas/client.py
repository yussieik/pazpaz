"""Pydantic schemas for Client API."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ClientBase(BaseModel):
    """Base schema with common client fields."""

    first_name: str = Field(
        ..., min_length=1, max_length=255, description="Client's first name"
    )
    last_name: str = Field(
        ..., min_length=1, max_length=255, description="Client's last name"
    )
    email: EmailStr | None = Field(None, description="Client's email address")
    phone: str | None = Field(None, max_length=50, description="Client's phone number")
    date_of_birth: date | None = Field(None, description="Client's date of birth")
    consent_status: bool = Field(
        default=False, description="Client consent to store and process data"
    )
    notes: str | None = Field(None, description="General notes about the client")
    tags: list[str] | None = Field(
        None, description="Tags for categorization and filtering"
    )


class ClientCreate(ClientBase):
    """
    Schema for creating a new client.

    SECURITY: workspace_id is NOT accepted from client requests.
    It is automatically injected from the authenticated user's session.
    This prevents workspace injection vulnerabilities.
    """

    pass


class ClientUpdate(BaseModel):
    """Schema for updating an existing client."""

    first_name: str | None = Field(None, min_length=1, max_length=255)
    last_name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = Field(None)
    phone: str | None = Field(None, max_length=50)
    date_of_birth: date | None = Field(None)
    consent_status: bool | None = Field(None)
    notes: str | None = Field(None)
    tags: list[str] | None = Field(None)


class ClientResponse(ClientBase):
    """Schema for client API responses."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClientListResponse(BaseModel):
    """Schema for paginated client list response."""

    items: list[ClientResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
