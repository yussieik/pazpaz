"""add_has_google_baa_to_google_calendar_tokens

Add has_google_baa field to google_calendar_tokens table to track
whether therapist has signed a Business Associate Agreement (BAA)
with Google Workspace. Required for HIPAA compliance when sending
client notifications via Google Calendar.

Revision ID: c8f45998f882
Revises: f5b5bdc7a7c2
Create Date: 2025-10-29 17:00:41.942983

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c8f45998f882'
down_revision: str | Sequence[str] | None = 'f5b5bdc7a7c2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add has_google_baa column with default=False
    # This ensures notify_clients cannot be enabled without BAA confirmation
    op.add_column(
        'google_calendar_tokens',
        sa.Column(
            'has_google_baa',
            sa.Boolean(),
            nullable=False,
            server_default='false',
            comment='Therapist confirms Google Workspace Business Associate Agreement (BAA) is signed (required for HIPAA compliance when notify_clients=true)',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove has_google_baa column
    op.drop_column('google_calendar_tokens', 'has_google_baa')
