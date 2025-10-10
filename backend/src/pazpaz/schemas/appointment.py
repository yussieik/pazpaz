"""Pydantic schemas for Appointment API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from pazpaz.core.constants import DELETION_REASON_MAX_LENGTH
from pazpaz.models.appointment import AppointmentStatus, LocationType


class AppointmentBase(BaseModel):
    """Base schema with common appointment fields."""

    client_id: uuid.UUID = Field(
        ..., description="ID of the client for this appointment"
    )
    scheduled_start: datetime = Field(
        ..., description="Start time (timezone-aware UTC)"
    )
    scheduled_end: datetime = Field(..., description="End time (timezone-aware UTC)")
    location_type: LocationType = Field(
        ..., description="Type of location (clinic/home/online)"
    )
    location_details: str | None = Field(
        None, description="Additional location details"
    )
    notes: str | None = Field(None, description="Therapist notes for the appointment")

    @field_validator("scheduled_end")
    @classmethod
    def validate_end_after_start(cls, end: datetime, info) -> datetime:
        """Validate that scheduled_end is after scheduled_start."""
        if "scheduled_start" in info.data:
            start = info.data["scheduled_start"]
            if end <= start:
                raise ValueError("scheduled_end must be after scheduled_start")
        return end


class AppointmentCreate(AppointmentBase):
    """
    Schema for creating a new appointment.

    SECURITY: workspace_id is NOT accepted from client requests.
    It is automatically injected from the authenticated user's session.
    This prevents workspace injection vulnerabilities.
    """

    pass


class AppointmentUpdate(BaseModel):
    """Schema for updating an existing appointment."""

    client_id: uuid.UUID | None = Field(
        None, description="ID of the client for this appointment"
    )
    scheduled_start: datetime | None = Field(
        None, description="Start time (timezone-aware UTC)"
    )
    scheduled_end: datetime | None = Field(
        None, description="End time (timezone-aware UTC)"
    )
    location_type: LocationType | None = Field(None, description="Type of location")
    location_details: str | None = Field(
        None, description="Additional location details"
    )
    status: AppointmentStatus | None = Field(
        None,
        description=(
            "Appointment status. Valid transitions: "
            "scheduled→completed, scheduled→cancelled, scheduled→no_show, "
            "completed→no_show, cancelled→scheduled, no_show→scheduled, "
            "no_show→completed. Cannot cancel completed appointments with "
            "session notes (delete session first). Cannot revert completed "
            "appointments to scheduled."
        ),
    )
    notes: str | None = Field(None, description="Therapist notes")

    @field_validator("scheduled_end")
    @classmethod
    def validate_end_after_start(cls, end: datetime | None, info) -> datetime | None:
        """Validate that scheduled_end is after scheduled_start if both provided."""
        if end is not None and "scheduled_start" in info.data:
            start = info.data.get("scheduled_start")
            if start is not None and end <= start:
                raise ValueError("scheduled_end must be after scheduled_start")
        return end


class AppointmentDeleteRequest(BaseModel):
    """
    Schema for deleting an appointment with optional reason and session note action.
    """

    reason: str | None = Field(
        None,
        max_length=DELETION_REASON_MAX_LENGTH,
        description="Optional reason for deletion (logged in audit trail)",
    )
    session_note_action: Literal["delete", "keep"] | None = Field(
        None,
        description=(
            "Action to take with session notes attached to this appointment. "
            "'delete' = soft delete the session note with 30-day grace period, "
            "'keep' = leave the session note unchanged (default if not specified). "
            "Required if appointment has session notes and you want to delete them."
        ),
    )
    deletion_reason: str | None = Field(
        None,
        max_length=DELETION_REASON_MAX_LENGTH,
        description=(
            "Optional reason for deleting the session note (only used if "
            "session_note_action='delete'). This is separate from the appointment "
            "deletion reason and is stored with the soft-deleted session note."
        ),
    )


class ClientSummary(BaseModel):
    """Summary of client information for appointment responses."""

    id: uuid.UUID
    first_name: str
    last_name: str
    full_name: str

    model_config = ConfigDict(from_attributes=True)


class AppointmentResponse(BaseModel):
    """Schema for appointment API responses."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    client_id: uuid.UUID
    scheduled_start: datetime
    scheduled_end: datetime
    location_type: LocationType
    location_details: str | None
    status: AppointmentStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime
    edited_at: datetime | None = Field(
        None, description="When appointment was last edited (NULL if never edited)"
    )
    edit_count: int = Field(
        0, description="Number of times this appointment has been edited"
    )
    client: ClientSummary | None = Field(
        None, description="Client information (included when requested)"
    )

    model_config = ConfigDict(from_attributes=True)


class AppointmentListResponse(BaseModel):
    """Schema for paginated appointment list response."""

    items: list[AppointmentResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ConflictCheckRequest(BaseModel):
    """Schema for checking appointment conflicts."""

    scheduled_start: datetime = Field(..., description="Start time to check")
    scheduled_end: datetime = Field(..., description="End time to check")
    exclude_appointment_id: uuid.UUID | None = Field(
        None,
        description="Appointment ID to exclude from conflict check (for updates)",
    )

    @field_validator("scheduled_end")
    @classmethod
    def validate_end_after_start(cls, end: datetime, info) -> datetime:
        """Validate that scheduled_end is after scheduled_start."""
        if "scheduled_start" in info.data:
            start = info.data["scheduled_start"]
            if end <= start:
                raise ValueError("scheduled_end must be after scheduled_start")
        return end


class ConflictingAppointmentDetail(BaseModel):
    """Privacy-preserving details of a conflicting appointment."""

    id: uuid.UUID = Field(..., description="Appointment ID")
    scheduled_start: datetime = Field(..., description="Start time")
    scheduled_end: datetime = Field(..., description="End time")
    client_initials: str = Field(
        ..., description="Client initials for privacy (e.g., 'J.D.')"
    )
    location_type: LocationType = Field(..., description="Location type")
    status: AppointmentStatus = Field(..., description="Appointment status")

    model_config = ConfigDict(from_attributes=True)


class ConflictCheckResponse(BaseModel):
    """Schema for conflict check response."""

    has_conflict: bool = Field(..., description="Whether a conflict exists")
    conflicting_appointments: list[ConflictingAppointmentDetail] = Field(
        default_factory=list,
        description="List of conflicting appointments with privacy-preserving details",
    )
