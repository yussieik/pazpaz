"""Location model - saved places for appointments."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base
from pazpaz.models.appointment import LocationType

if TYPE_CHECKING:
    from pazpaz.models.appointment import Appointment
    from pazpaz.models.workspace import Workspace


class Location(Base):
    """
    Location represents a saved place where appointments occur.

    Locations are reusable across appointments to avoid duplicate entry.
    Examples: "Main Clinic", "Home Visits", "Online Sessions".

    Previously embedded in Appointment as location_type + location_details,
    now normalized to separate table for better reusability and consistency.

    All locations are scoped to a workspace for privacy and data isolation.
    """

    __tablename__ = "locations"

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
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Location name (e.g., 'Main Clinic', 'Home Visits')",
    )
    location_type: Mapped[LocationType] = mapped_column(
        Enum(LocationType, native_enum=False, length=50),
        nullable=False,
        comment="Type: clinic, home, or online",
    )
    address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Physical address for clinic or home visits",
    )
    details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional details (room number, video link, parking instructions)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Active locations appear in scheduling UI; inactive are archived",
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

    # Relationships
    workspace: Mapped[Workspace] = relationship(
        "Workspace",
        back_populates="locations",
    )
    appointments: Mapped[list[Appointment]] = relationship(
        "Appointment",
        back_populates="location",
    )

    # Indexes for performance
    __table_args__ = (
        # Unique constraint: one location name per workspace
        Index(
            "uq_locations_workspace_name",
            "workspace_id",
            "name",
            unique=True,
        ),
        # Partial index for active locations (most common query pattern)
        Index(
            "ix_locations_workspace_active",
            "workspace_id",
            "is_active",
            postgresql_where="is_active = true",
        ),
        # Index for filtering by location type within workspace
        Index(
            "ix_locations_workspace_type",
            "workspace_id",
            "location_type",
        ),
        {"comment": "Saved locations for appointment scheduling"},
    )

    def __repr__(self) -> str:
        return (
            f"<Location(id={self.id}, name={self.name}, "
            f"type={self.location_type.value})>"
        )
