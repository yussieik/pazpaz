"""Session model - SOAP-based clinical documentation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import Boolean, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base
from pazpaz.db.types import EncryptedString

if TYPE_CHECKING:
    from pazpaz.models.appointment import Appointment
    from pazpaz.models.client import Client
    from pazpaz.models.session_attachment import SessionAttachment
    from pazpaz.models.user import User
    from pazpaz.models.workspace import Workspace


class Session(Base):
    """
    Session represents SOAP-based clinical documentation for a client encounter.

    SOAP Format:
    - Subjective: Patient-reported symptoms and concerns (PHI)
    - Objective: Therapist observations and measurements (PHI)
    - Assessment: Clinical evaluation and diagnosis (PHI)
    - Plan: Treatment plan and recommendations (PHI)

    All SOAP fields are encrypted at rest using AES-256-GCM encryption via
    the EncryptedString type. Encryption/decryption is transparent to application code.

    Security:
    - All SOAP fields encrypted with AES-256-GCM
    - Workspace scoping enforced on all queries
    - Audit logging via middleware tracks all access
    - Draft autosave support with version tracking
    """

    __tablename__ = "sessions"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign keys
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
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ENCRYPTED PHI FIELDS (SOAP Notes)
    # CRITICAL: Use EncryptedString type for transparent encryption
    subjective: Mapped[str | None] = mapped_column(
        EncryptedString(5000),  # ~5KB plaintext limit
        nullable=True,
        comment="ENCRYPTED: Subjective (patient-reported symptoms) - AES-256-GCM",
    )
    objective: Mapped[str | None] = mapped_column(
        EncryptedString(5000),
        nullable=True,
        comment="ENCRYPTED: Objective (therapist observations) - AES-256-GCM",
    )
    assessment: Mapped[str | None] = mapped_column(
        EncryptedString(5000),
        nullable=True,
        comment="ENCRYPTED: Assessment (diagnosis/evaluation) - AES-256-GCM",
    )
    plan: Mapped[str | None] = mapped_column(
        EncryptedString(5000),
        nullable=True,
        comment="ENCRYPTED: Plan (treatment plan) - AES-256-GCM",
    )

    # Metadata
    session_date: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        index=True,
    )
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_draft: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    draft_last_saved_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    finalized_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)

    # Audit columns
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, index=True
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship(
        "Workspace", back_populates="sessions"
    )
    client: Mapped[Client] = relationship("Client", back_populates="sessions")
    appointment: Mapped[Appointment | None] = relationship(
        "Appointment", back_populates="session"
    )
    created_by: Mapped[User | None] = relationship(
        "User", foreign_keys=[created_by_user_id]
    )
    attachments: Mapped[list[SessionAttachment]] = relationship(
        "SessionAttachment",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    # Indexes for performance (must match migration exactly)
    __table_args__ = (
        # Index 1: Client timeline query (workspace + client + date DESC)
        Index(
            "ix_sessions_workspace_client_date",
            "workspace_id",
            "client_id",
            sa.text("session_date DESC"),
        ),
        # Index 2: Draft list query (workspace + is_draft + draft_last_saved_at DESC, WHERE is_draft = true)
        Index(
            "ix_sessions_workspace_draft",
            "workspace_id",
            "is_draft",
            sa.text("draft_last_saved_at DESC"),
            postgresql_where=sa.text("is_draft = true"),
        ),
        # Index 3: Appointment linkage (appointment_id, WHERE appointment_id IS NOT NULL)
        Index(
            "ix_sessions_appointment",
            "appointment_id",
            postgresql_where=sa.text("appointment_id IS NOT NULL"),
        ),
        # Index 4: Active sessions (workspace + date DESC, WHERE deleted_at IS NULL)
        Index(
            "ix_sessions_workspace_active",
            "workspace_id",
            sa.text("session_date DESC"),
            postgresql_where=sa.text("deleted_at IS NULL"),
        ),
        {"comment": "SOAP session notes with encrypted PHI fields"},
    )

    def __repr__(self) -> str:
        return (
            f"<Session(id={self.id}, client_id={self.client_id}, "
            f"date={self.session_date}, is_draft={self.is_draft})>"
        )
