"""SessionAttachment model - file attachments for SOAP notes and clients."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base

if TYPE_CHECKING:
    from pazpaz.models.client import Client
    from pazpaz.models.session import Session
    from pazpaz.models.user import User
    from pazpaz.models.workspace import Workspace


class SessionAttachment(Base):
    """
    SessionAttachment represents file attachments for SOAP session notes and clients.

    Supports two types of attachments:
    1. Session-level: Attached to specific session (session_id is set)
       - Wound photos, treatment area photos, exercise form photos
    2. Client-level: Attached to client generally (session_id is NULL)
       - Intake forms, consent documents, insurance cards, baseline assessments

    Files are stored in MinIO/S3, not in the database. This model stores metadata
    and references to the files.

    Security (Week 3):
    - File storage location (s3_key) may need encryption
    - Pre-signed URLs for secure access
    - File type validation on upload
    - Size limits enforced
    - Workspace scoping on all queries
    """

    __tablename__ = "session_attachments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="NULL for client-level attachments (e.g., intake forms, consent docs)",
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Client this attachment belongs to (required for all attachments)",
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    s3_key: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="S3/MinIO object key - consider encryption in Week 3",
    )
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # Relationships
    session: Mapped[Optional[Session]] = relationship(
        "Session", back_populates="attachments"
    )
    client: Mapped[Client] = relationship("Client")
    workspace: Mapped[Workspace] = relationship("Workspace")
    uploaded_by: Mapped[User | None] = relationship("User")

    # Indexes for performance
    __table_args__ = (
        # Composite index for client queries (list all attachments for a client)
        Index(
            "ix_session_attachments_client_created",
            "client_id",
            "created_at",
        ),
        # Composite index for workspace + client queries
        Index(
            "ix_session_attachments_workspace_client",
            "workspace_id",
            "client_id",
        ),
    )

    @property
    def is_session_file(self) -> bool:
        """Return True if attached to a specific session, False if client-level."""
        return self.session_id is not None

    def __repr__(self) -> str:
        session_info = f"session_id={self.session_id}" if self.session_id else "client-level"
        return (
            f"<SessionAttachment(id={self.id}, {session_info}, "
            f"client_id={self.client_id}, file_name={self.file_name})>"
        )
