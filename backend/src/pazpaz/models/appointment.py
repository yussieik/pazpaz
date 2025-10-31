"""Appointment model - scheduled session."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base
from pazpaz.models.enums import PaymentStatus

if TYPE_CHECKING:
    from pazpaz.models.client import Client
    from pazpaz.models.location import Location
    from pazpaz.models.payment_transaction import PaymentTransaction
    from pazpaz.models.service import Service
    from pazpaz.models.session import Session
    from pazpaz.models.workspace import Workspace


class LocationType(str, enum.Enum):
    """Type of location for an appointment."""

    CLINIC = "clinic"
    HOME = "home"
    ONLINE = "online"


class AppointmentStatus(str, enum.Enum):
    """Status of an appointment."""

    SCHEDULED = "scheduled"
    ATTENDED = "attended"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class Appointment(Base):
    """
    Appointment represents a scheduled session with a client.

    Critical performance requirement: conflict detection queries must
    complete in <150ms p95. Indexes are carefully designed to support
    time-range queries within a workspace.
    """

    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("services.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Optional reference to predefined service type",
    )
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Optional reference to saved location (overrides embedded fields)",
    )
    scheduled_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Start time of the appointment (timezone-aware UTC)",
    )
    scheduled_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="End time of the appointment (timezone-aware UTC)",
    )
    location_type: Mapped[LocationType] = mapped_column(
        Enum(LocationType, native_enum=False, length=50),
        nullable=False,
    )
    location_details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional location details (address, room number, video link)",
    )
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus, native_enum=False, length=50),
        default=AppointmentStatus.SCHEDULED,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Therapist notes for the appointment",
    )
    google_event_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Google Calendar event ID when synced to Google Calendar",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    edited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When appointment was last edited (NULL if never edited)",
    )
    edit_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Number of times this appointment has been edited",
    )

    # Payment tracking fields
    # Independent of appointment/session status - client may pay before/during/after
    payment_price: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Actual price for this appointment (overrides service price if set)",
    )
    payment_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PaymentStatus.NOT_PAID.value,
        server_default=PaymentStatus.NOT_PAID.value,
        comment="Payment status: not_paid, paid, payment_sent, waived",
    )
    payment_method: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Payment method: cash, card, bank_transfer, payment_link, other",
    )
    payment_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Free-text notes about payment (e.g., invoice number, special terms)",
    )
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when payment was marked as paid",
    )
    payment_auto_send: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="Override workspace auto-send setting (null = use workspace default)",
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship(
        "Workspace",
        back_populates="appointments",
    )
    client: Mapped[Client] = relationship(
        "Client",
        back_populates="appointments",
    )
    service: Mapped[Service | None] = relationship(
        "Service",
        back_populates="appointments",
    )
    location: Mapped[Location | None] = relationship(
        "Location",
        back_populates="appointments",
    )
    session: Mapped[Session | None] = relationship(
        "Session",
        back_populates="appointment",
        uselist=False,
    )
    payment_transactions: Mapped[list[PaymentTransaction]] = relationship(
        "PaymentTransaction",
        back_populates="appointment",
        cascade="all, delete-orphan",
    )

    # Indexes and constraints for performance-critical queries and data integrity
    __table_args__ = (
        # Critical index for conflict detection and calendar view
        # Supports: WHERE workspace_id = ? AND scheduled_start BETWEEN ? AND ?
        Index(
            "ix_appointments_workspace_time_range",
            "workspace_id",
            "scheduled_start",
            "scheduled_end",
        ),
        # Index for client timeline view (ordered by appointment time)
        Index(
            "ix_appointments_workspace_client_time",
            "workspace_id",
            "client_id",
            "scheduled_start",
        ),
        # Index for filtering by status within workspace
        Index(
            "ix_appointments_workspace_status",
            "workspace_id",
            "status",
        ),
        # Index for filtering appointments by payment status
        Index(
            "ix_appointments_workspace_payment_status",
            "workspace_id",
            "payment_status",
        ),
        # CHECK constraints for payment data integrity
        CheckConstraint(
            "payment_status IN ('not_paid', 'paid', 'payment_sent', 'waived')",
            name="ck_appointment_payment_status",
        ),
        CheckConstraint(
            "payment_method IS NULL OR payment_method IN ('cash', 'card', 'bank_transfer', 'payment_link', 'other')",
            name="ck_appointment_payment_method",
        ),
        CheckConstraint(
            "payment_price IS NULL OR payment_price >= 0",
            name="ck_appointment_payment_price_positive",
        ),
        CheckConstraint(
            "(payment_status = 'paid' AND paid_at IS NOT NULL) OR (payment_status != 'paid')",
            name="ck_appointment_paid_at_consistency",
        ),
        {
            "comment": (
                "Appointments with time-range indexes optimized for "
                "conflict detection (<150ms p95 target)"
            )
        },
    )

    def __repr__(self) -> str:
        return (
            f"<Appointment(id={self.id}, client_id={self.client_id}, "
            f"start={self.scheduled_start}, status={self.status.value})>"
        )
