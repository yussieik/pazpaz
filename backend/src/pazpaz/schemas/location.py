"""Pydantic schemas for Location API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from pazpaz.models.appointment import LocationType


class LocationBase(BaseModel):
    """Base schema with common location fields."""

    name: str = Field(..., min_length=1, max_length=255, description="Location name")
    location_type: LocationType = Field(
        ..., description="Type: clinic, home, or online"
    )
    address: str | None = Field(
        None, description="Physical address for clinic or home visits"
    )
    details: str | None = Field(
        None,
        description="Additional details (room number, video link, parking instructions)",
    )
    is_active: bool = Field(
        default=True, description="Active locations appear in scheduling UI"
    )


class LocationCreate(LocationBase):
    """
    Schema for creating a new location.

    SECURITY: workspace_id is NOT accepted from client requests.
    It is automatically injected from the authenticated user's session.
    This prevents workspace injection vulnerabilities.
    """

    pass


class LocationUpdate(BaseModel):
    """Schema for updating an existing location."""

    name: str | None = Field(None, min_length=1, max_length=255)
    location_type: LocationType | None = Field(None)
    address: str | None = Field(None)
    details: str | None = Field(None)
    is_active: bool | None = Field(None)


class LocationResponse(LocationBase):
    """Schema for location API responses."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LocationListResponse(BaseModel):
    """Schema for paginated location list response."""

    items: list[LocationResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
