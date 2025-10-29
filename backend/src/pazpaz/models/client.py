"""Client model - individual receiving treatment."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base
from pazpaz.db.types import EncryptedString

if TYPE_CHECKING:
    from pazpaz.models.appointment import Appointment
    from pazpaz.models.session import Session
    from pazpaz.models.workspace import Workspace


class Client(Base):
    """
    Client represents an individual receiving treatment.

    All clients are scoped to a workspace and contain PII/PHI fields that are
    encrypted at rest using AES-256-GCM with versioned keys for zero-downtime
    key rotation. Encryption is transparent to application code.

    Encrypted PII/PHI fields:
    - first_name, last_name (PII - identity)
    - email, phone (PII - contact information)
    - date_of_birth (PHI - date of birth, stored as ISO format YYYY-MM-DD string)
    - address (PII - location data)
    - medical_history (PHI - protected health information)
    - emergency_contact_name, emergency_contact_phone (PII - contact information)

    HIPAA Compliance: §164.312(a)(2)(iv) - Encryption and Decryption
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

    # PII - Encrypted at rest (AES-256-GCM with versioned keys)
    first_name: Mapped[str] = mapped_column(
        EncryptedString(255),
        nullable=False,
        comment="Client first name (encrypted PII)",
    )
    last_name: Mapped[str] = mapped_column(
        EncryptedString(255),
        nullable=False,
        comment="Client last name (encrypted PII)",
    )
    email: Mapped[str | None] = mapped_column(
        EncryptedString(255),
        nullable=True,
        comment="Client email address (encrypted PII)",
    )
    phone: Mapped[str | None] = mapped_column(
        EncryptedString(50),
        nullable=True,
        comment="Client phone number (encrypted PII)",
    )
    date_of_birth: Mapped[str | None] = mapped_column(
        EncryptedString(50),
        nullable=True,
        comment="Client date of birth (encrypted PHI, ISO format YYYY-MM-DD)",
    )
    address: Mapped[str | None] = mapped_column(
        EncryptedString(1000),
        nullable=True,
        comment="Client physical address (encrypted PII)",
    )

    # PHI - Encrypted at rest (AES-256-GCM with versioned keys)
    medical_history: Mapped[str | None] = mapped_column(
        EncryptedString(5000),
        nullable=True,
        comment="Relevant medical history and conditions (encrypted PHI)",
    )

    # Emergency Contact - Encrypted PII
    emergency_contact_name: Mapped[str | None] = mapped_column(
        EncryptedString(255),
        nullable=True,
        comment="Emergency contact name (encrypted PII)",
    )
    emergency_contact_phone: Mapped[str | None] = mapped_column(
        EncryptedString(50),
        nullable=True,
        comment="Emergency contact phone (encrypted PII)",
    )
    consent_status: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Client consent to store and process data",
    )
    google_calendar_consent: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        default=True,
        server_default='true',
        comment="Client consent to receive Google Calendar invitations (opt-out model: True=consented by default, False=opted out)",
    )
    google_calendar_consent_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Date when client consented to Google Calendar invitations",
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
    sessions: Mapped[list[Session]] = relationship(
        "Session",
        back_populates="client",
        cascade="all, delete-orphan",
    )

    # Indexes for performance
    __table_args__ = (
        # NOTE: Indexes on encrypted fields (first_name, last_name, email)
        # are removed because EncryptedString stores binary data (BYTEA) which
        # cannot be efficiently indexed for name/email searches. Client search
        # must be implemented as:
        # 1. Fetch all clients for workspace (filtered by workspace_id)
        # 2. Decrypt and filter in application layer
        # 3. Alternative: Use separate search index (e.g., Elasticsearch)
        #    with encrypted-at-rest storage
        #
        # Performance impact: Client listing queries will fetch all clients
        # in workspace. For typical therapist practice (< 500 clients), this
        # is acceptable (<200ms). For larger workspaces, implement caching
        # or search index.
        # Index for recently updated clients (most useful for "recent clients" view)
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
        {"comment": "Clients with encrypted PII/PHI fields (HIPAA §164.312(a)(2)(iv))"},
    )

    @property
    def full_name(self) -> str:
        """Return full name of the client."""
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return f"<Client(id={self.id}, name={self.full_name})>"
