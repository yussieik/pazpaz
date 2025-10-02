"""Client model - individual receiving treatment."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base

if TYPE_CHECKING:
    from pazpaz.models.appointment import Appointment
    from pazpaz.models.workspace import Workspace


class Client(Base):
    """
    Client represents an individual receiving treatment.

    All clients are scoped to a workspace and contain PII/PHI that must be
    protected. Fields like name, email, phone should be encrypted at rest
    in production (encryption strategy TBD - application-level or pgcrypto).
    """

    __tablename__ = "clients"

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
    first_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    last_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    date_of_birth: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )
    address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Client's physical address (PII - encrypt at rest)",
    )
    medical_history: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Relevant medical history and conditions (PHI - encrypt at rest)",
    )
    emergency_contact_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Name of emergency contact person",
    )
    emergency_contact_phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Phone number of emergency contact",
    )
    consent_status: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Client consent to store and process data",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Active status (soft delete flag)",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="General notes about the client",
    )
    tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(100)),
        nullable=True,
        comment="Tags for categorization and filtering",
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
        back_populates="clients",
    )
    appointments: Mapped[list[Appointment]] = relationship(
        "Appointment",
        back_populates="client",
        cascade="all, delete-orphan",
    )

    # Indexes for performance
    __table_args__ = (
        # Composite index for workspace scoping and search
        Index(
            "ix_clients_workspace_lastname_firstname",
            "workspace_id",
            "last_name",
            "first_name",
        ),
        # Index for email lookup within workspace
        Index(
            "ix_clients_workspace_email",
            "workspace_id",
            "email",
        ),
        # Index for recently updated clients
        Index(
            "ix_clients_workspace_updated",
            "workspace_id",
            "updated_at",
        ),
        # Partial index for active clients (most common query pattern)
        Index(
            "ix_clients_workspace_active",
            "workspace_id",
            "is_active",
            postgresql_where=sa.text("is_active = true"),
        ),
        {"comment": "Clients with PII/PHI - encryption at rest required"},
    )

    @property
    def full_name(self) -> str:
        """Return full name of the client."""
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<Client(id={self.id}, name={self.full_name})>"
