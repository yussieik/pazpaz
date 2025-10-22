"""convert email blacklist email to citext

Revision ID: c7aa15ce5841
Revises: 9f17cfe59bf8
Create Date: 2025-10-22 16:11:14.520431

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import CITEXT

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7aa15ce5841"
down_revision: str | Sequence[str] | None = "9f17cfe59bf8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Convert email_blacklist.email to CITEXT type."""
    # Convert VARCHAR to CITEXT (preserves data, adds case-insensitive behavior)
    op.alter_column(
        "email_blacklist",
        "email",
        type_=CITEXT(),  # Use CITEXT type directly
        postgresql_using="email::citext",  # Cast to citext
        existing_nullable=False,
        existing_server_default=None,
    )

    # Update column comment
    op.execute("""
        COMMENT ON COLUMN email_blacklist.email IS
        'Email address (case-insensitive via CITEXT)'
    """)


def downgrade() -> None:
    """Convert email_blacklist.email back to VARCHAR."""
    # Convert back to VARCHAR (lowercase all values first for consistency)
    op.execute("UPDATE email_blacklist SET email = LOWER(email)")

    op.alter_column(
        "email_blacklist",
        "email",
        type_=sa.String(255),
        postgresql_using="email::varchar(255)",
        existing_nullable=False,
        existing_server_default=None,
    )
