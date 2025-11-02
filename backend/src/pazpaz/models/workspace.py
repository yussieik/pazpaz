"""Workspace model - therapist account context."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
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

    # Business details for tax receipts
    business_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Legal business name",
    )
    business_name_hebrew: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Business name in Hebrew (שם העסק בעברית)",
    )
    tax_id: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Israeli Tax ID (ת.ז. or ח.פ.)",
    )
    business_license: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Business license number (מספר רישיון עסק)",
    )
    business_address: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Business address for tax receipts",
    )

    # VAT configuration
    vat_registered: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Whether workspace is VAT registered (עוסק מורשה)",
    )
    vat_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("17.00"),
        server_default="17.00",
        comment="VAT rate percentage (default 17% for Israel)",
    )
    receipt_counter: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
        comment="Auto-incrementing counter for receipt numbers",
    )

    # Payment tracking configuration
    # Manual tracking (always available) - therapist manually marks payments
    bank_account_details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Bank account details for manual payment tracking (account number, bank name, branch, etc.)",
    )

    # Phase 1.5: Smart Payment Links (no API integration)
    payment_link_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Type of payment link: bit, paybox, bank, custom, NULL (disabled)",
    )
    payment_link_template: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Template for payment links: phone number (Bit/PayBox), URL (custom), or bank details (bank)",
    )

    # Automated payment provider integration (optional future feature)
    payment_provider: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Automated payment provider: bit, paybox, payplus, null (manual only)",
    )
    payment_provider_config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Encrypted payment provider API keys and configuration",
    )
    payment_auto_send: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Automatically send payment requests when provider is configured",
    )
    payment_send_timing: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="manual",
        server_default="manual",
        comment="When to send payment requests: immediately, end_of_day, end_of_month, manual",
    )

    # Third-party tax service integration (optional)
    tax_service_provider: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Third-party tax service: greeninvoice, morning, ness, null",
    )
    tax_service_config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Tax service API configuration",
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

    @property
    def payments_enabled(self) -> bool:
        """
        Check if payment tracking is enabled for this workspace.

        Payment tracking is enabled if EITHER manual tracking is configured
        (bank_account_details) OR automated provider is configured (payment_provider).
        This supports a dual-mode payment system where therapists can use:
        - Manual tracking only (bank transfers, cash, etc.)
        - Automated provider only (Bit, PayBox, PayPlus)
        - Both manual and automated simultaneously

        Returns:
            True if any payment method is configured, False otherwise

        Examples:
            >>> # Manual tracking only
            >>> workspace.bank_account_details = "Bank Leumi, Account: 12345"
            >>> workspace.payment_provider = None
            >>> workspace.payments_enabled
            True

            >>> # Automated provider only
            >>> workspace.bank_account_details = None
            >>> workspace.payment_provider = "bit"
            >>> workspace.payments_enabled
            True

            >>> # Both configured (dual-mode)
            >>> workspace.bank_account_details = "Bank Leumi, Account: 12345"
            >>> workspace.payment_provider = "bit"
            >>> workspace.payments_enabled
            True

            >>> # Neither configured
            >>> workspace.bank_account_details = None
            >>> workspace.payment_provider = None
            >>> workspace.payments_enabled
            False
        """
        return (
            self.bank_account_details is not None
            or self.payment_link_template is not None
            or self.payment_provider is not None
        )

    @property
    def payment_mode(self) -> str | None:
        """
        Get current payment mode based on configuration priority.

        Returns payment mode in priority order:
        1. 'automated' - Phase 2+ automated provider (payment_provider set)
        2. 'smart_link' - Phase 1.5 smart links (payment_link_template set)
        3. 'manual' - Phase 1 manual tracking (bank_account_details only)
        4. None - Payments disabled

        Returns:
            str | None: Payment mode or None if payments disabled

        Examples:
            >>> # Phase 1: Manual tracking only
            >>> workspace.bank_account_details = "Bank Leumi, Account: 12345"
            >>> workspace.payment_mode
            'manual'

            >>> # Phase 1.5: Smart payment links
            >>> workspace.payment_link_type = "bit"
            >>> workspace.payment_link_template = "050-1234567"
            >>> workspace.payment_mode
            'smart_link'

            >>> # Phase 2+: Automated provider (highest priority)
            >>> workspace.payment_provider = "bit_api"
            >>> workspace.payment_mode
            'automated'

            >>> # Payments disabled
            >>> workspace.bank_account_details = None
            >>> workspace.payment_link_template = None
            >>> workspace.payment_provider = None
            >>> workspace.payment_mode
            None
        """
        if self.payment_provider:
            return "automated"  # Phase 2+ (highest priority)
        if self.payment_link_template:
            return "smart_link"  # Phase 1.5
        if self.bank_account_details:
            return "manual"  # Phase 1
        return None  # Payments disabled

    def __repr__(self) -> str:
        return f"<Workspace(id={self.id}, name={self.name})>"
