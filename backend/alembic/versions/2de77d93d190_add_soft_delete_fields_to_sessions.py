"""add_soft_delete_fields_to_sessions

Adds enhanced soft delete fields to sessions table for maximum flexibility.

This migration adds:
1. deleted_reason (TEXT) - Optional reason for deletion
2. deleted_by_user_id (UUID) - Who deleted the session
3. permanent_delete_after (TIMESTAMP) - 30-day grace period before permanent purge

Note: deleted_at already exists from initial schema migration (430584776d5b).

Revision ID: 2de77d93d190
Revises: 9262695391b3
Create Date: 2025-10-10 13:40:46.413773

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2de77d93d190"
down_revision: str | Sequence[str] | None = "9262695391b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add soft delete enhancement fields to sessions table."""
    # Add deleted_reason column
    op.add_column(
        "sessions",
        sa.Column(
            "deleted_reason",
            sa.Text(),
            nullable=True,
            comment="Optional reason for soft deletion (for audit trail)",
        ),
    )

    # Add deleted_by_user_id column
    op.add_column(
        "sessions",
        sa.Column(
            "deleted_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="User who soft-deleted this session (SET NULL to preserve record)",
        ),
    )

    # Add permanent_delete_after column
    op.add_column(
        "sessions",
        sa.Column(
            "permanent_delete_after",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="Date when session will be permanently purged (deleted_at + 30 days)",
        ),
    )

    # Create index on permanent_delete_after for efficient purge job queries
    op.create_index(
        "ix_sessions_permanent_delete_after",
        "sessions",
        ["permanent_delete_after"],
        unique=False,
        postgresql_where=sa.text("permanent_delete_after IS NOT NULL"),
    )


def downgrade() -> None:
    """Remove soft delete enhancement fields from sessions table."""
    # Drop index first
    op.drop_index("ix_sessions_permanent_delete_after", table_name="sessions")

    # Drop columns
    op.drop_column("sessions", "permanent_delete_after")
    op.drop_column("sessions", "deleted_by_user_id")
    op.drop_column("sessions", "deleted_reason")
