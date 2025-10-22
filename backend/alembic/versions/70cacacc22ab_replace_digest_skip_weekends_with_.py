"""replace_digest_skip_weekends_with_digest_days

Revision ID: 70cacacc22ab
Revises: 3adf29e61586
Create Date: 2025-10-23 00:33:18.330526

This migration replaces the `digest_skip_weekends` boolean field with a more
flexible `digest_days` array field that allows users to select specific days
of the week for receiving daily digest notifications.

Migration:
    - digest_skip_weekends=True  → digest_days=[1,2,3,4,5] (Mon-Fri)
    - digest_skip_weekends=False → digest_days=[0,1,2,3,4,5,6] (All days)

Day numbering: 0=Sunday, 1=Monday, ..., 6=Saturday
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '70cacacc22ab'
down_revision: str | Sequence[str] | None = '3adf29e61586'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - replace digest_skip_weekends with digest_days."""
    # Step 1: Add digest_days column as nullable initially
    op.add_column(
        'user_notification_settings',
        sa.Column(
            'digest_days',
            postgresql.ARRAY(sa.Integer()),
            nullable=True,
            comment='Days of week to send digest (0=Sunday, 6=Saturday)',
        ),
    )

    # Step 2: Migrate existing data
    # If digest_skip_weekends = true → digest_days = [1,2,3,4,5] (Mon-Fri)
    # If digest_skip_weekends = false → digest_days = [0,1,2,3,4,5,6] (All days)
    op.execute("""
        UPDATE user_notification_settings
        SET digest_days = CASE
            WHEN digest_skip_weekends = true THEN ARRAY[1,2,3,4,5]
            ELSE ARRAY[0,1,2,3,4,5,6]
        END
    """)

    # Step 3: Make digest_days non-nullable with default
    op.alter_column(
        'user_notification_settings',
        'digest_days',
        nullable=False,
        server_default='{1,2,3,4,5}',
    )

    # Step 4: Drop old digest_skip_weekends column
    op.drop_column('user_notification_settings', 'digest_skip_weekends')


def downgrade() -> None:
    """Downgrade schema - restore digest_skip_weekends from digest_days."""
    # Step 1: Add digest_skip_weekends column back (nullable initially)
    op.add_column(
        'user_notification_settings',
        sa.Column(
            'digest_skip_weekends',
            sa.Boolean(),
            nullable=True,
            comment='Skip digest on Saturdays and Sundays',
        ),
    )

    # Step 2: Reverse migration
    # If digest_days = [1,2,3,4,5] → digest_skip_weekends = true
    # Otherwise → digest_skip_weekends = false
    op.execute("""
        UPDATE user_notification_settings
        SET digest_skip_weekends = CASE
            WHEN digest_days = ARRAY[1,2,3,4,5] THEN true
            ELSE false
        END
    """)

    # Step 3: Make digest_skip_weekends non-nullable with default
    op.alter_column(
        'user_notification_settings',
        'digest_skip_weekends',
        nullable=False,
        server_default='true',
    )

    # Step 4: Drop digest_days column
    op.drop_column('user_notification_settings', 'digest_days')
