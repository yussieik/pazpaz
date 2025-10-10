"""Appointment model - scheduled session."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base

if TYPE_CHECKING:
    from pazpaz.models.client import Client
    from pazpaz.models.location import Location
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
    COMPLETED = "completed"
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

    # Indexes for performance-critical queries
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
