"""Pydantic schemas for Session API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError

from pazpaz.core.constants import DELETION_REASON_MAX_LENGTH, SOAP_FIELD_MAX_LENGTH


class SessionBase(BaseModel):
    """Base schema for Session CRUD operations."""

    subjective: str | None = Field(
        None,
        max_length=SOAP_FIELD_MAX_LENGTH,
        description="Patient-reported symptoms (PHI - encrypted at rest)",
    )
    objective: str | None = Field(
        None,
        max_length=SOAP_FIELD_MAX_LENGTH,
        description="Therapist observations (PHI - encrypted at rest)",
    )
    assessment: str | None = Field(
        None,
        max_length=SOAP_FIELD_MAX_LENGTH,
        description="Clinical assessment (PHI - encrypted at rest)",
    )
    plan: str | None = Field(
        None,
        max_length=SOAP_FIELD_MAX_LENGTH,
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
            raise PydanticCustomError(
                "value_error",
                "Session date cannot be in the future",
            )
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

    subjective: str | None = Field(None, max_length=SOAP_FIELD_MAX_LENGTH)
    objective: str | None = Field(None, max_length=SOAP_FIELD_MAX_LENGTH)
    assessment: str | None = Field(None, max_length=SOAP_FIELD_MAX_LENGTH)
    plan: str | None = Field(None, max_length=SOAP_FIELD_MAX_LENGTH)
    session_date: datetime | None = None
    duration_minutes: int | None = Field(None, ge=0, le=480)

    @field_validator("session_date")
    @classmethod
    def validate_session_date(cls, v: datetime | None) -> datetime | None:
        """Validate session date is not in the future."""
        if v is not None:
            from datetime import UTC

            if v > datetime.now(UTC):
                raise PydanticCustomError(
                "value_error",
                "Session date cannot be in the future",
            )
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
    amended_at: datetime | None = Field(
        None, description="When session was last amended (NULL if never amended)"
    )
    amendment_count: int = Field(
        0, description="Number of times this finalized session has been amended"
    )
    version: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = Field(
        None, description="When session was soft-deleted (NULL if active)"
    )
    deleted_reason: str | None = Field(
        None, description="Optional reason for soft deletion"
    )
    deleted_by_user_id: uuid.UUID | None = Field(
        None, description="User who soft-deleted this session"
    )
    permanent_delete_after: datetime | None = Field(
        None,
        description=(
            "Date when session will be permanently purged (deleted_at + 30 days)"
        ),
    )
    attachment_count: int = Field(
        0, description="Number of file attachments for this session (excludes deleted)"
    )

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

    subjective: str | None = Field(None, max_length=SOAP_FIELD_MAX_LENGTH)
    objective: str | None = Field(None, max_length=SOAP_FIELD_MAX_LENGTH)
    assessment: str | None = Field(None, max_length=SOAP_FIELD_MAX_LENGTH)
    plan: str | None = Field(None, max_length=SOAP_FIELD_MAX_LENGTH)
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


class SessionDeleteRequest(BaseModel):
    """Schema for deleting a session with optional reason."""

    reason: str | None = Field(
        None,
        max_length=DELETION_REASON_MAX_LENGTH,
        description="Optional reason for deletion (logged in audit trail)",
    )


class SessionVersionResponse(BaseModel):
    """
    Schema for session version history responses.

    Represents a historical snapshot of a session note at a specific point in time.
    """

    id: uuid.UUID
    session_id: uuid.UUID
    version_number: int = Field(
        ..., description="Version number (1 = original, 2+ = amendments)"
    )
    subjective: str | None = Field(
        None,
        max_length=SOAP_FIELD_MAX_LENGTH,
        description="Subjective snapshot (decrypted PHI)",
    )
    objective: str | None = Field(
        None,
        max_length=SOAP_FIELD_MAX_LENGTH,
        description="Objective snapshot (decrypted PHI)",
    )
    assessment: str | None = Field(
        None,
        max_length=SOAP_FIELD_MAX_LENGTH,
        description="Assessment snapshot (decrypted PHI)",
    )
    plan: str | None = Field(
        None,
        max_length=SOAP_FIELD_MAX_LENGTH,
        description="Plan snapshot (decrypted PHI)",
    )
    created_at: datetime = Field(
        ..., description="When this version was created (finalized or amended)"
    )
    created_by_user_id: uuid.UUID = Field(
        ..., description="User who created this version"
    )

    model_config = ConfigDict(from_attributes=True)
