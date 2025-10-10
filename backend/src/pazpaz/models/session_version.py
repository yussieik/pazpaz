"""SessionVersion model - version history for session note amendments."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base
from pazpaz.db.types import EncryptedString

if TYPE_CHECKING:
    from pazpaz.models.session import Session
    from pazpaz.models.user import User


class SessionVersion(Base):
    """
    SessionVersion represents a historical snapshot of a session note.

    This table stores versioned SOAP notes to track amendments to finalized
    session notes. Each version represents the state of the session note at
    a specific point in time.

    Version History:
    - Version 1: Created when session is finalized (original snapshot)
    - Version 2+: Created before each amendment (preserves previous state)

    Security:
    - All SOAP fields encrypted with AES-256-GCM (same as Session table)
    - Workspace scoping inherited through session relationship
    - Audit logging tracks all version creation
    - Immutable: versions cannot be updated or deleted (append-only)

    Use Cases:
    - Legal requirement: maintain complete amendment history
    - Audit trail: show what changed and when
    - Recovery: restore previous version if needed
    - Compliance: demonstrate therapist's evolving clinical understanding
    """

    __tablename__ = "session_versions"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign keys
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Session this version belongs to",
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
        comment="User who created this version (who finalized or amended)",
    )

    # Version metadata
    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Version number (1 = original, 2+ = amendments)",
    )

    # ENCRYPTED PHI FIELDS (SOAP Notes)
    # These store the snapshot of the session at this version
    subjective: Mapped[str | None] = mapped_column(
        EncryptedString(5000),
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

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="When this version was created (finalized or amended)",
    )

    # Relationships
    session: Mapped[Session] = relationship(
        "Session",
        back_populates="versions",
    )
    created_by: Mapped[User] = relationship(
        "User",
        foreign_keys=[created_by_user_id],
    )

    # Table configuration
    __table_args__ = (
        # Ensure unique version numbers per session
        UniqueConstraint(
            "session_id",
            "version_number",
            name="uq_session_version_number",
        ),
        # Index for fetching version history (ordered by version number DESC)
        Index(
            "ix_session_versions_session_version",
            "session_id",
            "version_number",
        ),
        {
            "comment": (
                "Version history for session notes - tracks amendments "
                "with encrypted PHI snapshots"
            )
        },
    )

    def __repr__(self) -> str:
        return (
            f"<SessionVersion(id={self.id}, session_id={self.session_id}, "
            f"version={self.version_number}, created_at={self.created_at})>"
        )
