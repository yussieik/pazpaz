"""SessionAttachment model - file attachments for SOAP notes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base

if TYPE_CHECKING:
    from pazpaz.models.session import Session
    from pazpaz.models.user import User
    from pazpaz.models.workspace import Workspace


class SessionAttachment(Base):
    """
    SessionAttachment represents file attachments for SOAP session notes.

    Supports photo attachments for clinical documentation (e.g., wound photos,
    treatment area photos, exercise form photos).

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
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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
    session: Mapped[Session] = relationship("Session", back_populates="attachments")
    workspace: Mapped[Workspace] = relationship("Workspace")
    uploaded_by: Mapped[User | None] = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<SessionAttachment(id={self.id}, session_id={self.session_id}, "
            f"file_name={self.file_name})>"
        )
