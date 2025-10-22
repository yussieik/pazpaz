"""Appointment reminder tracking model - prevents duplicate reminder sends."""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base

if TYPE_CHECKING:
    from pazpaz.models.appointment import Appointment
    from pazpaz.models.user import User


class ReminderType(str, enum.Enum):
    """Type of appointment reminder sent."""

    MIN_15 = "15min"
    MIN_30 = "30min"
    HOUR_1 = "1hr"
    HOUR_2 = "2hr"
    HOUR_24 = "24hr"


class AppointmentReminderSent(Base):
    """
    Tracks sent appointment reminders to prevent duplicates.

    This table ensures that each reminder type is sent only once per
    appointment per user. The unique constraint on (appointment_id,
    user_id, reminder_type) enforces deduplication at the database level.

    When the scheduler runs multiple times within a tolerance window
    (e.g., every 5 minutes with ±2 minute tolerance), this table prevents
    sending the same reminder multiple times.

    Cleanup:
        Records older than 30 days are periodically deleted to prevent
        table bloat, since reminder tracking is only needed until the
        appointment occurs.
    """

    __tablename__ = "appointment_reminders_sent"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    appointment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Appointment for which reminder was sent",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who received the reminder",
    )
    reminder_type: Mapped[ReminderType] = mapped_column(
        Enum(ReminderType, native_enum=False, length=50),
        nullable=False,
        comment="Type of reminder sent (15min, 30min, 1hr, 2hr, 24hr)",
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
        index=True,
        comment="When the reminder was sent (for cleanup queries)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    appointment: Mapped[Appointment] = relationship(
        "Appointment",
        foreign_keys=[appointment_id],
    )
    user: Mapped[User] = relationship(
        "User",
        foreign_keys=[user_id],
    )

    # Constraints and indexes
    __table_args__ = (
        # Unique constraint ensures one reminder per type per appointment per user
        UniqueConstraint(
            "appointment_id",
            "user_id",
            "reminder_type",
            name="uq_appointment_reminders_deduplication",
        ),
        # Index for fast lookup during reminder sending
        Index(
            "ix_appointment_reminders_lookup",
            "appointment_id",
            "user_id",
            "reminder_type",
        ),
        # Index for cleanup queries (find old records)
        Index(
            "ix_appointment_reminders_cleanup",
            "sent_at",
        ),
        {
            "comment": (
                "Tracks sent appointment reminders to prevent duplicates. "
                "Records are cleaned up after 30 days."
            )
        },
    )

    def __repr__(self) -> str:
        return (
            f"<AppointmentReminderSent(id={self.id}, "
            f"appointment_id={self.appointment_id}, "
            f"user_id={self.user_id}, "
            f"reminder_type={self.reminder_type.value})>"
        )
