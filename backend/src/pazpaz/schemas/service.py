"""Pydantic schemas for Service API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ServiceBase(BaseModel):
    """Base schema with common service fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Service name")
    description: str | None = Field(
        None, description="Optional description of the service"
    )
    default_duration_minutes: int = Field(
        ..., gt=0, description="Default duration in minutes (must be > 0)"
    )
    is_active: bool = Field(
        default=True, description="Active services appear in scheduling UI"
    )


class ServiceCreate(ServiceBase):
    """
    Schema for creating a new service.

    SECURITY: workspace_id is NOT accepted from client requests.
    It is automatically injected from the authenticated user's session.
    This prevents workspace injection vulnerabilities.
    """

    pass


class ServiceUpdate(BaseModel):
    """Schema for updating an existing service."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None)
    default_duration_minutes: int | None = Field(None, gt=0)
    is_active: bool | None = Field(None)


class ServiceResponse(ServiceBase):
    """Schema for service API responses."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceListResponse(BaseModel):
    """Schema for paginated service list response."""

    items: list[ServiceResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# Type alias for cleaner code (can be used instead of ServiceListResponse)
# from pazpaz.utils.pagination import PaginatedResponse
# ServiceListResponse = PaginatedResponse[ServiceResponse]
