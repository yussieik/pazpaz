"""Pydantic schemas for Client API."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_validator,
)


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
    address: str | None = Field(None, description="Client's physical address")
    medical_history: str | None = Field(
        None, description="Relevant medical history and conditions (PHI)"
    )
    emergency_contact_name: str | None = Field(
        None, max_length=255, description="Emergency contact person's name"
    )
    emergency_contact_phone: str | None = Field(
        None, max_length=50, description="Emergency contact phone number"
    )
    is_active: bool = Field(
        default=True, description="Active status (false = archived/soft deleted)"
    )
    consent_status: bool = Field(
        default=False, description="Client consent to store and process data"
    )
    google_calendar_consent: bool | None = Field(
        True,
        description="Client consent to receive Google Calendar invitations (opt-out model: True=consented by default, False=opted out)",
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
    address: str | None = Field(None)
    medical_history: str | None = Field(None)
    emergency_contact_name: str | None = Field(None, max_length=255)
    emergency_contact_phone: str | None = Field(None, max_length=50)
    is_active: bool | None = Field(None)
    consent_status: bool | None = Field(None)
    google_calendar_consent: bool | None = Field(None)
    notes: str | None = Field(None)
    tags: list[str] | None = Field(None)


class ClientResponse(ClientBase):
    """Schema for client API responses."""

    id: uuid.UUID
    workspace_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    google_calendar_consent_date: datetime | None = Field(
        None, description="Date when client consented to Google Calendar invitations"
    )

    # Computed appointment fields (populated by API endpoint)
    next_appointment: datetime | None = Field(
        None, description="Next scheduled appointment after now"
    )
    last_appointment: datetime | None = Field(
        None, description="Most recent completed appointment"
    )
    appointment_count: int = Field(
        default=0, description="Total number of appointments"
    )

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def parse_date_of_birth(cls, value: str | date | None) -> date | None:
        """
        Convert encrypted date_of_birth string to date object.

        The database stores date_of_birth as an encrypted ISO format string
        (YYYY-MM-DD). This validator handles conversion from string to date
        for API responses.

        Args:
            value: Either ISO format string from database or date object

        Returns:
            date object or None
        """
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            # Parse ISO format string (YYYY-MM-DD)
            return datetime.fromisoformat(value).date()
        return value

    @computed_field  # type: ignore[misc]
    @property
    def full_name(self) -> str:
        """Full name of the client."""
        return f"{self.first_name} {self.last_name}"

    model_config = ConfigDict(from_attributes=True)


class ClientListResponse(BaseModel):
    """Schema for paginated client list response."""

    items: list[ClientResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
