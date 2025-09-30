"""Service model - type of therapy offered."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base

if TYPE_CHECKING:
    from pazpaz.models.appointment import Appointment
    from pazpaz.models.workspace import Workspace


class Service(Base):
    """
    Service represents a type of therapy offered by the therapist.

    Services are reusable across appointments and include a default duration
    for quick scheduling. Examples: "Deep Tissue Massage", "Physiotherapy Session",
    "Initial Consultation".

    All services are scoped to a workspace for privacy and data isolation.
    """

    __tablename__ = "services"

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
        comment="Service name (e.g., 'Deep Tissue Massage', 'Physiotherapy Session')",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Optional description of the service",
    )
    default_duration_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Default duration in minutes for scheduling (e.g., 60, 90)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Active services appear in scheduling UI; inactive are archived",
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
        back_populates="services",
    )
    appointments: Mapped[list[Appointment]] = relationship(
        "Appointment",
        back_populates="service",
    )

    # Indexes for performance
    __table_args__ = (
        # Unique constraint: one service name per workspace
        Index(
            "uq_services_workspace_name",
            "workspace_id",
            "name",
            unique=True,
        ),
        # Partial index for active services (most common query pattern)
        Index(
            "ix_services_workspace_active",
            "workspace_id",
            "is_active",
            postgresql_where="is_active = true",
        ),
        {"comment": "Services with default durations for quick scheduling"},
    )

    def __repr__(self) -> str:
        return (
            f"<Service(id={self.id}, name={self.name}, "
            f"duration={self.default_duration_minutes}min)>"
        )
