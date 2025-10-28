"""add_timezone_to_workspace

Revision ID: 3adf29e61586
Revises: b9c4d5e6f7a8
Create Date: 2025-10-22 21:33:17.039777

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3adf29e61586"
down_revision: str | Sequence[str] | None = "b9c4d5e6f7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add timezone column to workspaces table."""
    op.add_column(
        "workspaces",
        sa.Column(
            "timezone",
            sa.String(length=100),
            nullable=True,
            server_default="UTC",
            comment="IANA timezone name (e.g., 'Asia/Jerusalem', 'America/New_York') for notification scheduling",
        ),
    )
    # Backfill existing workspaces with 'UTC' timezone
    op.execute("UPDATE workspaces SET timezone = 'UTC' WHERE timezone IS NULL")


def downgrade() -> None:
    """Remove timezone column from workspaces table."""
    op.drop_column("workspaces", "timezone")
