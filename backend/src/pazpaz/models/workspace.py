"""Workspace model - therapist account context."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base

if TYPE_CHECKING:
    from pazpaz.models.appointment import Appointment
    from pazpaz.models.audit_event import AuditEvent
    from pazpaz.models.client import Client
    from pazpaz.models.location import Location
    from pazpaz.models.service import Service
    from pazpaz.models.session import Session
    from pazpaz.models.user import User
    from pazpaz.models.user_notification_settings import UserNotificationSettings


class WorkspaceStatus(str, enum.Enum):
    """Workspace status for platform admin management."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class Workspace(Base):
    """
    Workspace represents a therapist's account context.

    All data in the system is scoped to a workspace to ensure privacy
    and data isolation between different therapists/practices.
    """

    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Platform admin management fields
    status: Mapped[WorkspaceStatus] = mapped_column(
        Enum(WorkspaceStatus, native_enum=False, length=50),
        default=WorkspaceStatus.ACTIVE,
        nullable=False,
        comment="Workspace status (active, suspended, deleted)",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When workspace was soft-deleted (NULL if not deleted)",
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

    # Storage Quota Fields
    storage_used_bytes: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
        server_default="0",
        comment="Total bytes used by all files in workspace",
    )
    storage_quota_bytes: Mapped[int] = mapped_column(
        BigInteger,
        default=10 * 1024 * 1024 * 1024,  # 10 GB default
        nullable=False,
        server_default="10737418240",  # 10 GB in bytes
        comment="Maximum storage allowed for workspace in bytes",
    )

    # Timezone for notification scheduling
    timezone: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        default="UTC",
        server_default="UTC",
        comment="IANA timezone name (e.g., 'Asia/Jerusalem', 'America/New_York') for notification scheduling",
    )

    # Relationships
    users: Mapped[list[User]] = relationship(
        "User",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    clients: Mapped[list[Client]] = relationship(
        "Client",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    appointments: Mapped[list[Appointment]] = relationship(
        "Appointment",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    services: Mapped[list[Service]] = relationship(
        "Service",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    locations: Mapped[list[Location]] = relationship(
        "Location",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    audit_events: Mapped[list[AuditEvent]] = relationship(
        "AuditEvent",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list[Session]] = relationship(
        "Session",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    notification_settings: Mapped[list[UserNotificationSettings]] = relationship(
        "UserNotificationSettings",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )

    # Indexes and constraints
    __table_args__ = (
        # Index for status queries (filtering by active/suspended/deleted)
        Index("idx_workspaces_status", "status"),
        # Index for deleted_at (filtering soft-deleted workspaces)
        Index("idx_workspaces_deleted_at", "deleted_at"),
        {"comment": "Therapist account context with platform admin management"},
    )

    @property
    def storage_usage_percentage(self) -> float:
        """
        Calculate storage usage as percentage of quota.

        Returns:
            Percentage of quota used (0.0 to 100.0+)

        Example:
            >>> workspace.storage_used_bytes = 5_000_000_000  # 5 GB
            >>> workspace.storage_quota_bytes = 10_000_000_000  # 10 GB
            >>> workspace.storage_usage_percentage
            50.0
        """
        if self.storage_quota_bytes == 0:
            return 0.0
        return (self.storage_used_bytes / self.storage_quota_bytes) * 100

    @property
    def is_quota_exceeded(self) -> bool:
        """
        Check if workspace has exceeded storage quota.

        Returns:
            True if storage_used_bytes >= storage_quota_bytes

        Example:
            >>> workspace.storage_used_bytes = 11_000_000_000  # 11 GB
            >>> workspace.storage_quota_bytes = 10_000_000_000  # 10 GB
            >>> workspace.is_quota_exceeded
            True
        """
        return self.storage_used_bytes >= self.storage_quota_bytes

    @property
    def storage_remaining_bytes(self) -> int:
        """
        Calculate remaining storage quota.

        Returns:
            Bytes remaining (can be negative if quota exceeded)

        Example:
            >>> workspace.storage_used_bytes = 3_000_000_000  # 3 GB
            >>> workspace.storage_quota_bytes = 10_000_000_000  # 10 GB
            >>> workspace.storage_remaining_bytes
            7000000000  # 7 GB remaining
        """
        return self.storage_quota_bytes - self.storage_used_bytes

    def __repr__(self) -> str:
        return f"<Workspace(id={self.id}, name={self.name})>"
