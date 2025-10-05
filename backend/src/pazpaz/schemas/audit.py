"""Audit event schemas for API requests and responses."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pazpaz.models.audit_event import AuditAction, ResourceType


class AuditEventResponse(BaseModel):
    """Response schema for a single audit event."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID = Field(description="Unique identifier for the audit event")
    workspace_id: uuid.UUID = Field(description="Workspace this event belongs to")
    user_id: uuid.UUID | None = Field(
        description="User who performed the action (None for system events)"
    )
    event_type: str = Field(
        description="Event type (e.g., 'client.read', 'session.create')"
    )
    resource_type: str = Field(
        description="Type of resource (Client, Session, Appointment, etc.)"
    )
    resource_id: uuid.UUID | None = Field(
        description="ID of the resource being accessed or modified"
    )
    action: AuditAction = Field(
        description="Action performed (CREATE, READ, UPDATE, DELETE, etc.)"
    )
    ip_address: str | None = Field(description="IP address of the user")
    user_agent: str | None = Field(description="User agent string from the request")
    event_metadata: dict[str, Any] | None = Field(
        alias="metadata",
        description="Additional context (NO PII/PHI)",
    )
    created_at: datetime = Field(description="When the event occurred")


class AuditEventListResponse(BaseModel):
    """Paginated response for audit event list."""

    items: list[AuditEventResponse] = Field(description="List of audit events")
    total: int = Field(description="Total number of audit events matching filters")
    page: int = Field(description="Current page number (1-indexed)")
    page_size: int = Field(description="Number of items per page")
    total_pages: int = Field(description="Total number of pages")


class AuditEventFilters(BaseModel):
    """Filter parameters for audit event queries."""

    user_id: uuid.UUID | None = Field(
        None, description="Filter by user who performed action"
    )
    resource_type: ResourceType | None = Field(
        None, description="Filter by resource type (Client, Session, etc.)"
    )
    resource_id: uuid.UUID | None = Field(
        None, description="Filter by specific resource ID"
    )
    action: AuditAction | None = Field(
        None, description="Filter by action type (CREATE, READ, UPDATE, DELETE)"
    )
    start_date: datetime | None = Field(
        None, description="Filter events on or after this date"
    )
    end_date: datetime | None = Field(
        None, description="Filter events on or before this date"
    )
    phi_only: bool = Field(
        False,
        description=(
            "Filter to only PHI access events (Client, Session, PlanOfCare reads)"
        ),
    )
