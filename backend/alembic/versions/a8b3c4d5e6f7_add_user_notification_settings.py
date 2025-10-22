"""add_user_notification_settings

Revision ID: a8b3c4d5e6f7
Revises: c7aa15ce5841
Create Date: 2025-10-22 18:00:00.000000

Adds user notification settings table for email notification preferences:

Phase 1: Email Notifications
- Master toggle (email_enabled)
- Event notifications (appointment booked/cancelled/rescheduled/confirmed)
- Daily digest (enabled, time, skip_weekends)
- Appointment reminders (enabled, minutes before)
- Session notes reminders (enabled, time)

Design:
- Hybrid approach: Typed columns for Phase 1 + JSONB for future extensions
- One-to-one relationship with users table
- Workspace scoping for privacy isolation
- CHECK constraints enforce data integrity (time format, reminder presets)
- Partial indexes optimize batch queries for background jobs

See: /docs/backend/database/NOTIFICATION_SETTINGS_SCHEMA.md
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8b3c4d5e6f7"
down_revision: str | Sequence[str] | None = "c7aa15ce5841"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """
    Create user_notification_settings table with defaults for existing users.

    Creates:
    - Table with typed columns for Phase 1 email settings
    - JSONB extended_settings column for future channels (SMS, push, etc.)
    - CHECK constraints for time format and reminder_minutes validation
    - Indexes for workspace scoping and batch query optimization
    - Default settings records for all existing active users

    Performance:
    - Partial indexes on digest and reminder settings (background jobs)
    - Composite index on (workspace_id, user_id) for user lookups
    - CHECK constraints prevent invalid data at database level

    Data seeding:
    - Creates default settings for all existing active users
    - Sensible defaults: event notifications enabled, digest disabled
    """
    # Create user_notification_settings table
    op.create_table(
        "user_notification_settings",
        # Primary key
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            comment="Unique identifier for notification settings",
        ),
        # Foreign keys
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="User who owns these notification settings (one-to-one)",
        ),
        sa.Column(
            "workspace_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
            comment="Workspace context for privacy isolation",
        ),
        # Master toggle
        sa.Column(
            "email_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Master toggle - disable all email notifications",
        ),
        # Event notifications (appointment lifecycle)
        sa.Column(
            "notify_appointment_booked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Send email when new appointment is booked",
        ),
        sa.Column(
            "notify_appointment_cancelled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Send email when appointment is cancelled",
        ),
        sa.Column(
            "notify_appointment_rescheduled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Send email when appointment is rescheduled",
        ),
        sa.Column(
            "notify_appointment_confirmed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Send email when client confirms appointment",
        ),
        # Daily digest settings
        sa.Column(
            "digest_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Enable daily digest email (opt-in)",
        ),
        sa.Column(
            "digest_time",
            sa.String(length=5),
            nullable=True,
            server_default=sa.text("'08:00'"),
            comment="Time to send digest in HH:MM format (24-hour, workspace timezone)",
        ),
        sa.Column(
            "digest_skip_weekends",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Skip digest on Saturdays and Sundays",
        ),
        # Appointment reminder settings
        sa.Column(
            "reminder_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Enable appointment reminder emails",
        ),
        sa.Column(
            "reminder_minutes",
            sa.Integer(),
            nullable=True,
            server_default=sa.text("60"),
            comment="Minutes before appointment to send reminder (15, 30, 60, 120, 1440)",
        ),
        # Session notes reminder settings
        sa.Column(
            "notes_reminder_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
            comment="Enable draft session notes reminders",
        ),
        sa.Column(
            "notes_reminder_time",
            sa.String(length=5),
            nullable=True,
            server_default=sa.text("'18:00'"),
            comment="Time to send notes reminder in HH:MM format (24-hour, workspace timezone)",
        ),
        # Future extensibility (JSONB)
        sa.Column(
            "extended_settings",
            JSONB,
            nullable=True,
            server_default=sa.text("'{}'"),
            comment="Future notification preferences (SMS, push, quiet hours, etc.)",
        ),
        # Audit fields
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="When settings were created",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
            comment="When settings were last modified",
        ),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Unique constraints (one-to-one with user)
        sa.UniqueConstraint(
            "user_id",
            name="uq_user_notification_settings_user_id",
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "user_id",
            name="uq_user_notification_settings_workspace_user",
        ),
        # CHECK constraints for data validation
        sa.CheckConstraint(
            "digest_time IS NULL OR digest_time ~ '^([0-1][0-9]|2[0-3]):[0-5][0-9]$'",
            name="ck_digest_time_format",
        ),
        sa.CheckConstraint(
            "notes_reminder_time IS NULL OR notes_reminder_time ~ '^([0-1][0-9]|2[0-3]):[0-5][0-9]$'",
            name="ck_notes_reminder_time_format",
        ),
        sa.CheckConstraint(
            "reminder_minutes IS NULL OR reminder_minutes IN (15, 30, 60, 120, 1440)",
            name="ck_reminder_minutes_valid",
        ),
        comment="User notification preferences with hybrid typed/JSONB approach",
    )

    # Create indexes
    # Note: In production with large tables, consider creating these CONCURRENTLY
    # to avoid table locks. For development/testing, non-concurrent is simpler.

    # Index for workspace scoping queries
    op.create_index(
        "idx_user_notification_settings_workspace_id",
        "user_notification_settings",
        ["workspace_id"],
        unique=False,
    )

    # Index on user_id for fast one-to-one lookups (already created by unique constraint)
    op.create_index(
        op.f("ix_user_notification_settings_user_id"),
        "user_notification_settings",
        ["user_id"],
        unique=False,
    )

    # Composite index for workspace-scoped user lookups (most common query)
    op.create_index(
        "idx_user_notification_settings_workspace_user",
        "user_notification_settings",
        ["workspace_id", "user_id"],
        unique=False,
    )

    # Partial index for daily digest batch queries (background jobs)
    # Only indexes rows where email_enabled AND digest_enabled are true
    # This optimizes: "find all users wanting digest at 08:00"
    op.create_index(
        "idx_user_notification_settings_digest",
        "user_notification_settings",
        ["digest_enabled", "digest_time"],
        unique=False,
        postgresql_where=sa.text("email_enabled = true AND digest_enabled = true"),
    )

    # Partial index for appointment reminder batch queries (background jobs)
    # Only indexes rows where email_enabled AND reminder_enabled are true
    # This optimizes: "find all users with 60-minute reminders"
    op.create_index(
        "idx_user_notification_settings_reminder",
        "user_notification_settings",
        ["reminder_enabled", "reminder_minutes"],
        unique=False,
        postgresql_where=sa.text("email_enabled = true AND reminder_enabled = true"),
    )

    # Seed default notification settings for all existing active users
    # This INSERT...SELECT uses server defaults where possible
    op.execute(
        """
        INSERT INTO user_notification_settings (
            user_id,
            workspace_id,
            email_enabled,
            notify_appointment_booked,
            notify_appointment_cancelled,
            notify_appointment_rescheduled,
            notify_appointment_confirmed,
            digest_enabled,
            digest_time,
            digest_skip_weekends,
            reminder_enabled,
            reminder_minutes,
            notes_reminder_enabled,
            notes_reminder_time,
            extended_settings,
            created_at,
            updated_at
        )
        SELECT
            id,                -- user_id
            workspace_id,      -- workspace_id
            true,              -- email_enabled (master toggle)
            true,              -- notify_appointment_booked
            true,              -- notify_appointment_cancelled
            true,              -- notify_appointment_rescheduled
            true,              -- notify_appointment_confirmed
            false,             -- digest_enabled (opt-in, default disabled)
            '08:00',           -- digest_time (8 AM)
            true,              -- digest_skip_weekends
            true,              -- reminder_enabled
            60,                -- reminder_minutes (1 hour)
            true,              -- notes_reminder_enabled
            '18:00',           -- notes_reminder_time (6 PM)
            '{}',              -- extended_settings (empty JSONB)
            CURRENT_TIMESTAMP, -- created_at
            CURRENT_TIMESTAMP  -- updated_at
        FROM users
        WHERE is_active = true
        """
    )


def downgrade() -> None:
    """
    Drop user_notification_settings table and all related indexes.

    WARNING: This will permanently delete all user notification preferences.
    Users will need to reconfigure their settings after upgrade.

    Drops:
    - All indexes (partial and regular)
    - Table with all data
    """
    # Drop indexes first (before dropping table they reference)
    op.drop_index(
        "idx_user_notification_settings_reminder",
        table_name="user_notification_settings",
    )
    op.drop_index(
        "idx_user_notification_settings_digest",
        table_name="user_notification_settings",
    )
    op.drop_index(
        "idx_user_notification_settings_workspace_user",
        table_name="user_notification_settings",
    )
    op.drop_index(
        op.f("ix_user_notification_settings_user_id"),
        table_name="user_notification_settings",
    )
    op.drop_index(
        "idx_user_notification_settings_workspace_id",
        table_name="user_notification_settings",
    )

    # Drop table (foreign key constraints are dropped automatically)
    op.drop_table("user_notification_settings")
