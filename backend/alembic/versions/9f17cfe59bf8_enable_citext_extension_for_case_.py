"""enable citext extension for case insensitive emails

Revision ID: 9f17cfe59bf8
Revises: c289c823d8e8
Create Date: 2025-10-22 16:10:49.419776

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9f17cfe59bf8"
down_revision: str | Sequence[str] | None = "c289c823d8e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Enable CITEXT extension for case-insensitive text."""
    # Enable CITEXT extension (idempotent - won't fail if already exists)
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")


def downgrade() -> None:
    """Disable CITEXT extension."""
    # Drop extension (will fail if columns still use it - intentional safety)
    op.execute("DROP EXTENSION IF EXISTS citext CASCADE")
