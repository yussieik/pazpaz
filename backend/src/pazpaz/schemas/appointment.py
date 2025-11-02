"""Pydantic schemas for Appointment API."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from pazpaz.core.constants import DELETION_REASON_MAX_LENGTH
from pazpaz.models.appointment import AppointmentStatus, LocationType
from pazpaz.models.enums import PaymentMethod, PaymentStatus


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
    payment_price: Decimal | None = Field(
        None,
        ge=0,
        description="Actual price for this appointment (overrides service price if set)",
    )
    payment_status: PaymentStatus = Field(
        PaymentStatus.NOT_PAID,
        description="Payment status: not_paid (default), paid, payment_sent, waived",
    )
    payment_method: PaymentMethod | None = Field(
        None,
        description="Payment method: cash, card, bank_transfer, bit, paybox, other",
    )
    payment_notes: str | None = Field(
        None,
        description="Free-text notes about payment (e.g., invoice number, special terms)",
    )

    @field_validator("scheduled_end")
    @classmethod
    def validate_end_after_start(cls, end: datetime, info) -> datetime:
        """Validate that scheduled_end is after scheduled_start."""
        if "scheduled_start" in info.data:
            start = info.data["scheduled_start"]
            if end <= start:
                raise PydanticCustomError(
                    "value_error",
                    "scheduled_end must be after scheduled_start",
                )
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
            "scheduled→attended, scheduled→cancelled, scheduled→no_show, "
            "attended→no_show, cancelled→scheduled, no_show→scheduled, "
            "no_show→attended. Cannot cancel attended appointments with "
            "session notes (delete session first). Cannot revert attended "
            "appointments to scheduled."
        ),
    )
    notes: str | None = Field(None, description="Therapist notes")
    payment_price: Decimal | None = Field(
        None,
        ge=0,
        description="Actual price for this appointment (overrides service price if set)",
    )
    payment_status: PaymentStatus | None = Field(
        None,
        description="Payment status: not_paid, paid, payment_sent, waived",
    )
    payment_method: PaymentMethod | None = Field(
        None,
        description="Payment method: cash, card, bank_transfer, bit, paybox, other",
    )
    payment_notes: str | None = Field(
        None,
        description="Free-text notes about payment (e.g., invoice number, special terms)",
    )
    paid_at: datetime | None = Field(
        None,
        description="Timestamp when payment was marked as paid (auto-set if not provided when status='paid')",
    )

    @field_validator("scheduled_end")
    @classmethod
    def validate_end_after_start(cls, end: datetime | None, info) -> datetime | None:
        """Validate that scheduled_end is after scheduled_start if both provided."""
        if end is not None and "scheduled_start" in info.data:
            start = info.data.get("scheduled_start")
            if start is not None and end <= start:
                raise PydanticCustomError(
                    "value_error",
                    "scheduled_end must be after scheduled_start",
                )
        return end

    @model_validator(mode="after")
    def validate_payment_fields(self) -> AppointmentUpdate:
        """Validate payment field consistency."""
        # If payment_status is being set to PAID, ensure paid_at will be set
        # (either provided or will be auto-set in the endpoint)
        if self.payment_status == PaymentStatus.PAID:
            # This is just a note - paid_at will be auto-set in the endpoint if not provided
            pass

        return self


class AppointmentPaymentUpdate(BaseModel):
    """Schema for updating payment status on an appointment (Phase 1)."""

    payment_status: Literal["not_paid", "paid", "payment_sent", "waived"] = Field(
        ...,
        description="Payment status: not_paid, paid, payment_sent, waived",
    )
    payment_method: (
        Literal["cash", "card", "bank_transfer", "bit", "paybox", "other"] | None
    ) = Field(
        None,
        description="Payment method: cash, card, bank_transfer, bit, paybox, other",
    )
    payment_price: Decimal | None = Field(
        None,
        ge=0,
        description="Actual price for this appointment (optional update)",
    )
    payment_notes: str | None = Field(
        None,
        description="Free-text notes about payment (e.g., invoice number, special terms)",
    )
    paid_at: datetime | None = Field(
        None,
        description="Timestamp when payment was marked as paid (auto-set if not provided when status='paid')",
    )


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
    payment_price: Decimal | None = Field(
        None, description="Actual price for this appointment (null = no price set)"
    )
    payment_status: str = Field(
        "not_paid",
        description="Payment status: not_paid, paid, payment_sent, waived",
    )
    payment_method: str | None = Field(
        None,
        description="Payment method: cash, card, bank_transfer, bit, paybox, other",
    )
    payment_notes: str | None = Field(
        None,
        description="Free-text notes about payment (e.g., invoice number, special terms)",
    )
    paid_at: datetime | None = Field(
        None, description="Timestamp when payment was marked as paid"
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
                raise PydanticCustomError(
                    "value_error",
                    "scheduled_end must be after scheduled_start",
                )
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


class SendPaymentRequestBody(BaseModel):
    """Schema for sending payment request to client."""

    message: str | None = Field(
        None,
        description="Optional custom message to include in email",
    )


class SendPaymentRequestResponse(BaseModel):
    """Schema for send payment request response."""

    success: bool = Field(
        ..., description="Whether payment request was sent successfully"
    )
    payment_link: str = Field(..., description="Generated payment link")
    message: str = Field(..., description="Human-readable success message")


class PaymentLinkResponse(BaseModel):
    """Schema for payment link preview/regeneration response."""

    payment_link: str = Field(..., description="Generated payment link")
    payment_type: str = Field(
        ...,
        description="Type of payment link: bit, paybox, bank, custom",
    )
    amount: Decimal = Field(..., description="Payment amount")
    display_text: str = Field(
        ...,
        description="Human-readable description of payment method",
    )
