"""User model - therapist or assistant."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base
from pazpaz.db.types import EncryptedString

if TYPE_CHECKING:
    from pazpaz.models.audit_event import AuditEvent
    from pazpaz.models.workspace import Workspace


class UserRole(str, enum.Enum):
    """User role within a workspace."""

    OWNER = "owner"
    ASSISTANT = "assistant"


class User(Base):
    """
    User represents a therapist or assistant within a workspace.

    Each user belongs to exactly one workspace and has a specific role.
    """

    __tablename__ = "users"

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
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=50),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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

    # Platform Admin Access
    is_platform_admin: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="True if user can access platform admin panel",
    )

    # 2FA/TOTP fields
    totp_secret: Mapped[str | None] = mapped_column(
        EncryptedString(255),
        nullable=True,
        comment="TOTP secret key (encrypted, base32-encoded)",
    )
    totp_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="Whether 2FA is enabled for this user",
    )
    totp_backup_codes: Mapped[str | None] = mapped_column(
        EncryptedString(1000),
        nullable=True,
        comment="JSON array of hashed backup codes (encrypted)",
    )
    totp_enrolled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when 2FA was enabled",
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship(
        "Workspace",
        back_populates="users",
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(
        "AuditEvent",
        back_populates="user",
    )

    # Constraints
    __table_args__ = (
        # Email must be unique per workspace
        UniqueConstraint(
            "workspace_id",
            "email",
            name="uq_users_workspace_email",
        ),
        # Index for platform admin queries (fast lookup of platform admins)
        Index("idx_users_platform_admin", "is_platform_admin"),
        # Index for workspace scoping and email lookups
        {"comment": "Users within workspaces with role-based access"},
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, role={self.role.value})>"
