"""Email blacklist model for platform admin functionality."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base

if TYPE_CHECKING:
    from pazpaz.models.user import User


class EmailBlacklist(Base):
    """
    Email blacklist for preventing specific emails from being invited.

    Platform admins can add emails to this list to prevent them from:
    - Receiving new invitations
    - Creating new accounts
    - Accessing the platform

    Use cases:
    - Blocking abusive users
    - Preventing spam signups
    - Enforcing platform policies
    """

    __tablename__ = "email_blacklist"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Email address to blacklist (case-insensitive)",
    )
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Reason for blacklisting (required for audit trail)",
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        comment="When email was added to blacklist (UTC)",
    )
    added_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Platform admin who added this entry (NULL if user deleted)",
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
    added_by_user: Mapped[User | None] = relationship(
        "User",
        foreign_keys=[added_by],
    )

    # Indexes
    __table_args__ = (
        # Index for email lookups (primary use case)
        Index("idx_email_blacklist_email", "email"),
        # Index for added_at (for sorting/filtering by date)
        Index("idx_email_blacklist_added_at", "added_at"),
        {
            "comment": "Blacklisted emails that cannot receive invitations or access platform"
        },
    )

    def __repr__(self) -> str:
        return f"<EmailBlacklist(id={self.id}, email={self.email})>"
