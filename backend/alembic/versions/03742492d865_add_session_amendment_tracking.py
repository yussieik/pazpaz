"""add_session_amendment_tracking

Adds amendment tracking fields to sessions table to track modifications
to finalized session notes for audit purposes.

Revision ID: 03742492d865
Revises: 0131df2d459b
Create Date: 2025-10-10 13:03:16.946259

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "03742492d865"
down_revision: str | Sequence[str] | None = "0131df2d459b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add amendment tracking columns to sessions table."""
    # Add amended_at column (nullable timestamp)
    op.add_column(
        "sessions",
        sa.Column(
            "amended_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
            comment="When session was last amended (NULL if never amended)",
        ),
    )

    # Add amendment_count column (default 0)
    op.add_column(
        "sessions",
        sa.Column(
            "amendment_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Number of times this finalized session has been amended",
        ),
    )

    # Update existing finalized_at column comment
    op.alter_column(
        "sessions",
        "finalized_at",
        comment="When session was first finalized (immutable after set)",
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Remove amendment tracking columns from sessions table."""
    # Restore original finalized_at comment
    op.alter_column(
        "sessions",
        "finalized_at",
        comment=None,
        existing_type=sa.TIMESTAMP(timezone=True),
        existing_nullable=True,
    )

    op.drop_column("sessions", "amendment_count")
    op.drop_column("sessions", "amended_at")
