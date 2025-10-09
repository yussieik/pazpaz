"""Pydantic schemas for Session API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SessionBase(BaseModel):
    """Base schema for Session CRUD operations."""

    subjective: str | None = Field(
        None,
        max_length=5000,
        description="Patient-reported symptoms (PHI - encrypted at rest)",
    )
    objective: str | None = Field(
        None,
        max_length=5000,
        description="Therapist observations (PHI - encrypted at rest)",
    )
    assessment: str | None = Field(
        None,
        max_length=5000,
        description="Clinical assessment (PHI - encrypted at rest)",
    )
    plan: str | None = Field(
        None,
        max_length=5000,
        description="Treatment plan (PHI - encrypted at rest)",
    )
    session_date: datetime = Field(
        ...,
        description="Date/time when session occurred (timezone-aware UTC)",
    )
    duration_minutes: int | None = Field(
        None,
        ge=0,
        le=480,
        description="Session duration in minutes (0-480 min, i.e., 0-8 hours)",
    )

    @field_validator("session_date")
    @classmethod
    def validate_session_date(cls, v: datetime) -> datetime:
        """Validate session date is not in the future."""
        from datetime import UTC

        if v > datetime.now(UTC):
            raise ValueError("Session date cannot be in the future")
        return v


class SessionCreate(SessionBase):
    """
    Schema for creating a new session.

    SECURITY: workspace_id is NOT accepted from client requests.
    It is automatically injected from the authenticated user's session.
    This prevents workspace injection vulnerabilities.
    """

    client_id: uuid.UUID = Field(
        ..., description="Client ID (must belong to same workspace)"
    )
    appointment_id: uuid.UUID | None = Field(
        None, description="Optional appointment link"
    )


class SessionUpdate(BaseModel):
    """Schema for updating a session (all fields optional for partial updates)."""

    subjective: str | None = Field(None, max_length=5000)
    objective: str | None = Field(None, max_length=5000)
    assessment: str | None = Field(None, max_length=5000)
    plan: str | None = Field(None, max_length=5000)
    session_date: datetime | None = None
    duration_minutes: int | None = Field(None, ge=0, le=480)

    @field_validator("session_date")
    @classmethod
    def validate_session_date(cls, v: datetime | None) -> datetime | None:
        """Validate session date is not in the future."""
        if v is not None:
            from datetime import UTC

            if v > datetime.now(UTC):
                raise ValueError("Session date cannot be in the future")
        return v


class SessionResponse(SessionBase):
    """Schema for session API responses."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    client_id: uuid.UUID
    appointment_id: uuid.UUID | None
    created_by_user_id: uuid.UUID
    is_draft: bool
    draft_last_saved_at: datetime | None
    finalized_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class SessionListResponse(BaseModel):
    """Schema for paginated session list response."""

    items: list[SessionResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SessionDraftUpdate(BaseModel):
    """
    Schema for draft autosave updates (relaxed validation).

    Used by PATCH /sessions/{id}/draft endpoint for frontend autosave.
    All fields are optional to allow partial updates.
    No validation on session_date (drafts can be incomplete).
    """

    subjective: str | None = Field(None, max_length=5000)
    objective: str | None = Field(None, max_length=5000)
    assessment: str | None = Field(None, max_length=5000)
    plan: str | None = Field(None, max_length=5000)
    duration_minutes: int | None = Field(None, ge=0, le=480)


class SessionAttachmentResponse(BaseModel):
    """Schema for session attachment API responses."""

    id: uuid.UUID
    session_id: uuid.UUID
    workspace_id: uuid.UUID
    file_name: str
    file_type: str
    file_size_bytes: int
    uploaded_by_user_id: uuid.UUID | None
    created_at: datetime
    deleted_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
