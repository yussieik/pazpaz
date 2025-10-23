"""add tomorrow digest fields to user notification settings

Revision ID: f90e9a7e0831
Revises: 70cacacc22ab
Create Date: 2025-10-23 10:46:08.308633

Adds tomorrow's digest notification settings to user_notification_settings table.
This provides an independent digest for tomorrow's schedule, separate from the
existing today's digest functionality.

New columns:
- tomorrow_digest_enabled: BOOLEAN DEFAULT FALSE (opt-in)
- tomorrow_digest_time: TIME DEFAULT '20:00:00' (8 PM)
- tomorrow_digest_days: INTEGER[] DEFAULT ARRAY[0,1,2,3,4] (Mon-Fri)

Design rationale:
- Default OFF (opt-in) to avoid overwhelming users
- Default time 8 PM to preview tomorrow's schedule
- Default weekdays only (Mon-Fri) as most therapeutic practices operate weekdays
- Independent from today's digest - users can enable both, either, or neither

UX approved design:
1. Today's Schedule Digest - Default ON, 7 AM
2. Tomorrow's Schedule Digest - Default OFF, 8 PM, weekdays only
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f90e9a7e0831"
down_revision: str | Sequence[str] | None = "70cacacc22ab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add tomorrow's digest columns to user_notification_settings."""
    # Add tomorrow_digest_enabled column
    op.add_column(
        "user_notification_settings",
        sa.Column(
            "tomorrow_digest_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Enable tomorrow's schedule digest email (opt-in)",
        ),
    )

    # Add tomorrow_digest_time column
    op.add_column(
        "user_notification_settings",
        sa.Column(
            "tomorrow_digest_time",
            sa.String(length=5),
            nullable=True,
            server_default=sa.text("'20:00'"),
            comment="Time to send tomorrow's digest in HH:MM format (24-hour, workspace timezone)",
        ),
    )

    # Add tomorrow_digest_days column
    op.add_column(
        "user_notification_settings",
        sa.Column(
            "tomorrow_digest_days",
            postgresql.ARRAY(sa.Integer()),
            nullable=False,
            server_default=sa.text("'{0,1,2,3,4}'"),
            comment="Days of week to send tomorrow's digest (0=Sunday, 1=Monday, ..., 6=Saturday)",
        ),
    )

    # Add CHECK constraint for tomorrow_digest_time format (same pattern as digest_time)
    op.create_check_constraint(
        "ck_tomorrow_digest_time_format",
        "user_notification_settings",
        "tomorrow_digest_time IS NULL OR tomorrow_digest_time ~ '^([0-1][0-9]|2[0-3]):[0-5][0-9]$'",
    )

    # Add partial index for tomorrow's digest batch queries (background jobs)
    # Only indexes rows where email_enabled AND tomorrow_digest_enabled are true
    # This optimizes: "find all users wanting tomorrow's digest at 20:00"
    op.create_index(
        "idx_user_notification_settings_tomorrow_digest",
        "user_notification_settings",
        ["tomorrow_digest_enabled", "tomorrow_digest_time"],
        unique=False,
        postgresql_where=sa.text(
            "email_enabled = true AND tomorrow_digest_enabled = true"
        ),
    )


def downgrade() -> None:
    """Remove tomorrow's digest columns from user_notification_settings."""
    # Drop partial index first
    op.drop_index(
        "idx_user_notification_settings_tomorrow_digest",
        table_name="user_notification_settings",
    )

    # Drop CHECK constraint
    op.drop_constraint(
        "ck_tomorrow_digest_time_format",
        "user_notification_settings",
        type_="check",
    )

    # Drop columns
    op.drop_column("user_notification_settings", "tomorrow_digest_days")
    op.drop_column("user_notification_settings", "tomorrow_digest_time")
    op.drop_column("user_notification_settings", "tomorrow_digest_enabled")
