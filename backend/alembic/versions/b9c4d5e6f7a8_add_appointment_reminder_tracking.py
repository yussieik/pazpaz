"""add_appointment_reminder_tracking

Revision ID: b9c4d5e6f7a8
Revises: a8b3c4d5e6f7
Create Date: 2025-10-22 18:30:00.000000

Adds appointment reminder tracking to prevent duplicate reminder sends.

This migration creates the appointment_reminders_sent table to track which
reminders have been sent for each appointment. When the scheduler runs
multiple times within the tolerance window (±2 minutes), this table ensures
each reminder type is sent only once per appointment per user.

Table: appointment_reminders_sent
- id: UUID primary key
- appointment_id: Reference to appointment (CASCADE delete)
- user_id: Reference to user who received reminder (CASCADE delete)
- reminder_type: Type of reminder ('15min', '30min', '1hr', '2hr', '24hr')
- sent_at: When reminder was sent (for cleanup queries)
- created_at: Record creation timestamp

Constraints:
- Unique constraint on (appointment_id, user_id, reminder_type) for deduplication
- Foreign keys with CASCADE delete for automatic cleanup

Indexes:
- Primary key index on id (automatic)
- Index on appointment_id for lookups
- Index on user_id for lookups
- Index on sent_at for cleanup queries
- Composite index on (appointment_id, user_id, reminder_type) for dedup checks

Cleanup Strategy:
Records older than 30 days are periodically deleted via cleanup_old_reminders()
service function to prevent table bloat.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b9c4d5e6f7a8"
down_revision: str | Sequence[str] | None = "a8b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Create appointment_reminders_sent table for deduplication tracking.

    This table prevents duplicate appointment reminders from being sent
    when the scheduler runs multiple times within the tolerance window.
    The unique constraint on (appointment_id, user_id, reminder_type)
    enforces one reminder per type per appointment at the database level.
    """
    # Create appointment_reminders_sent table
    op.create_table(
        "appointment_reminders_sent",
        # Primary key
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
            comment="Primary key",
        ),
        # Foreign key to appointments
        sa.Column(
            "appointment_id",
            sa.UUID(),
            nullable=False,
            comment="Appointment for which reminder was sent",
        ),
        # Foreign key to users
        sa.Column(
            "user_id",
            sa.UUID(),
            nullable=False,
            comment="User who received the reminder",
        ),
        # Reminder type enum
        sa.Column(
            "reminder_type",
            sa.String(length=50),
            nullable=False,
            comment="Type of reminder sent (15min, 30min, 1hr, 2hr, 24hr)",
        ),
        # Timestamp when reminder was sent
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When the reminder was sent (for cleanup queries)",
        ),
        # Record creation timestamp
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When this record was created",
        ),
        # Primary key constraint
        sa.PrimaryKeyConstraint("id", name=op.f("pk_appointment_reminders_sent")),
        # Foreign key constraints with CASCADE delete
        sa.ForeignKeyConstraint(
            ["appointment_id"],
            ["appointments.id"],
            name=op.f("fk_appointment_reminders_sent_appointment_id_appointments"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_appointment_reminders_sent_user_id_users"),
            ondelete="CASCADE",
        ),
        # Unique constraint for deduplication
        sa.UniqueConstraint(
            "appointment_id",
            "user_id",
            "reminder_type",
            name="uq_appointment_reminders_deduplication",
        ),
        # Table comment
        comment=(
            "Tracks sent appointment reminders to prevent duplicates. "
            "Records are cleaned up after 30 days."
        ),
    )

    # Create index on id (primary key - automatic, but explicit for clarity)
    op.create_index(
        op.f("ix_appointment_reminders_sent_id"),
        "appointment_reminders_sent",
        ["id"],
        unique=False,
    )

    # Create index on appointment_id for lookups
    op.create_index(
        op.f("ix_appointment_reminders_sent_appointment_id"),
        "appointment_reminders_sent",
        ["appointment_id"],
        unique=False,
    )

    # Create index on user_id for lookups
    op.create_index(
        op.f("ix_appointment_reminders_sent_user_id"),
        "appointment_reminders_sent",
        ["user_id"],
        unique=False,
    )

    # Create index on sent_at for cleanup queries
    op.create_index(
        "ix_appointment_reminders_cleanup",
        "appointment_reminders_sent",
        ["sent_at"],
        unique=False,
    )

    # Create composite index for deduplication lookups
    # This supports the query: WHERE appointment_id = ? AND user_id = ? AND reminder_type = ?
    op.create_index(
        "ix_appointment_reminders_lookup",
        "appointment_reminders_sent",
        ["appointment_id", "user_id", "reminder_type"],
        unique=False,
    )


def downgrade() -> None:
    """
    Drop appointment_reminders_sent table.

    WARNING: This will permanently delete all reminder tracking data.
    After downgrade, duplicate reminders may be sent until the table
    is recreated.
    """
    # Drop indexes first (before dropping table)
    op.drop_index(
        "ix_appointment_reminders_lookup",
        table_name="appointment_reminders_sent",
    )
    op.drop_index(
        "ix_appointment_reminders_cleanup",
        table_name="appointment_reminders_sent",
    )
    op.drop_index(
        op.f("ix_appointment_reminders_sent_user_id"),
        table_name="appointment_reminders_sent",
    )
    op.drop_index(
        op.f("ix_appointment_reminders_sent_appointment_id"),
        table_name="appointment_reminders_sent",
    )
    op.drop_index(
        op.f("ix_appointment_reminders_sent_id"),
        table_name="appointment_reminders_sent",
    )

    # Drop table (foreign keys and constraints are dropped automatically)
    op.drop_table("appointment_reminders_sent")
