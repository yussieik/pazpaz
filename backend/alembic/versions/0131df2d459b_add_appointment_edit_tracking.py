"""add_appointment_edit_tracking

Adds edit tracking fields to appointments table to track modifications
to completed appointments for audit purposes.

Revision ID: 0131df2d459b
Revises: 430584776d5b
Create Date: 2025-10-10 13:02:54.334718

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0131df2d459b"
down_revision: str | Sequence[str] | None = "430584776d5b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add edit tracking columns to appointments table."""
    # Add edited_at column (nullable timestamp)
    op.add_column(
        "appointments",
        sa.Column(
            "edited_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When appointment was last edited (NULL if never edited)",
        ),
    )

    # Add edit_count column (default 0)
    op.add_column(
        "appointments",
        sa.Column(
            "edit_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Number of times this appointment has been edited",
        ),
    )


def downgrade() -> None:
    """Remove edit tracking columns from appointments table."""
    op.drop_column("appointments", "edit_count")
    op.drop_column("appointments", "edited_at")
