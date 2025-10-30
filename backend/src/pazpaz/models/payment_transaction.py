"""PaymentTransaction model - payment tracking for appointments."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base

if TYPE_CHECKING:
    from pazpaz.models.appointment import Appointment
    from pazpaz.models.workspace import Workspace


class PaymentTransaction(Base):
    """
    PaymentTransaction represents a payment for an appointment.

    Supports both online payments (via PayPlus, Meshulam, Stripe) and manual
    payments (cash, bank transfer, check). Tracks complete payment lifecycle
    from creation to completion, including receipt generation and tax compliance.

    All monetary amounts use Decimal type for precise financial calculations.
    """

    __tablename__ = "payment_transactions"

    # Primary key and foreign keys
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Optional reference to appointment (null for standalone payments)",
    )

    # Financial details
    base_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment='Amount before VAT (מחיר לפני מע"מ)',
    )
    vat_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0"),
        server_default=text("0"),
        comment='VAT amount (מע"מ)',
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Total amount (base + VAT)",
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="ILS",
        server_default=text("'ILS'"),
        comment="Currency code (ILS, USD, EUR)",
    )

    # Payment method and status
    payment_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Payment method: online_card, cash, bank_transfer, check, paypal, apple_pay, google_pay",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default=text("'pending'"),
        comment="Status: pending, completed, failed, refunded, cancelled",
    )

    # Provider details (for online payments)
    provider: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Payment provider: payplus, meshulam, stripe, manual",
    )
    provider_transaction_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Provider transaction ID",
    )
    provider_payment_link: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Payment link sent to client",
    )

    # Receipt details
    receipt_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Sequential receipt number (e.g., 2025-001234)",
    )
    receipt_issued: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        comment="Whether receipt was issued",
    )
    receipt_issued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When receipt was issued",
    )
    receipt_pdf_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="S3/MinIO URL for receipt PDF",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        server_default=text("NOW()"),
        comment="When transaction was created",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When payment was completed",
    )
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When payment failed",
    )
    refunded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When payment was refunded",
    )

    # Additional details
    failure_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for payment failure",
    )
    refund_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for refund",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment='Manual payment notes (e.g., "Client paid cash")',
    )

    # Provider metadata (flexible JSONB for provider-specific data)
    # Note: Cannot use 'metadata' as column name - reserved by SQLAlchemy
    provider_metadata: Mapped[dict | None] = mapped_column(
        "metadata",  # Column name in database
        JSONB,
        nullable=True,
        comment="Provider-specific metadata",
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship(
        "Workspace",
        back_populates="payment_transactions",
    )
    appointment: Mapped[Appointment | None] = relationship(
        "Appointment",
        back_populates="payment_transactions",
    )

    # Indexes and constraints
    __table_args__ = (
        # Index for workspace payment queries (ordered by creation time)
        Index(
            "idx_workspace_payments",
            "workspace_id",
            "created_at",
            postgresql_ops={"created_at": "DESC"},
        ),
        # Index for appointment payments lookup
        Index("idx_appointment_payments", "appointment_id"),
        # Index for provider transaction ID lookup
        Index("idx_provider_txn", "provider_transaction_id"),
        # Index for payment status filtering
        Index("idx_payment_status", "status"),
        # Index for receipt number lookup
        Index("idx_receipt_number", "receipt_number"),
        # Index for completed_at queries
        Index("idx_completed_at", "completed_at"),
        # Index for payment method analytics
        Index("idx_payment_method", "payment_method"),
        # Composite index for workspace payment reports
        Index(
            "idx_payments_workspace_date_status",
            "workspace_id",
            "completed_at",
            "status",
            postgresql_ops={"completed_at": "DESC"},
        ),
        {
            "comment": (
                "Core payment tracking table supporting online and manual payments"
            )
        },
    )

    # Helper methods
    @property
    def is_completed(self) -> bool:
        """
        Check if payment is completed.

        Returns:
            True if status is 'completed', False otherwise

        Example:
            >>> transaction.status = "completed"
            >>> transaction.is_completed
            True
        """
        return self.status == "completed"

    @property
    def is_pending(self) -> bool:
        """
        Check if payment is pending.

        Returns:
            True if status is 'pending', False otherwise

        Example:
            >>> transaction.status = "pending"
            >>> transaction.is_pending
            True
        """
        return self.status == "pending"

    @property
    def is_failed(self) -> bool:
        """
        Check if payment failed.

        Returns:
            True if status is 'failed', False otherwise

        Example:
            >>> transaction.status = "failed"
            >>> transaction.is_failed
            True
        """
        return self.status == "failed"

    def __repr__(self) -> str:
        return (
            f"<PaymentTransaction(id={self.id}, "
            f"workspace_id={self.workspace_id}, "
            f"total_amount={self.total_amount}, "
            f"status={self.status})>"
        )
