"""add_sync_tracking_fields_to_google_calendar_tokens

Revision ID: a5ac11f65d20
Revises: ad0e9ab68b84
Create Date: 2025-10-28 17:10:51.602371

This migration adds sync tracking fields to the google_calendar_tokens table
for Phase 2 (One-Way Sync) of the Google Calendar integration feature.

New fields:
- sync_client_names: Boolean flag to control whether client names are synced to Google Calendar
- last_sync_at: Timestamp of the last successful sync operation
- last_sync_status: Status of the last sync operation (success/error)
- last_sync_error: Error message from the last failed sync operation
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a5ac11f65d20"
down_revision: str | Sequence[str] | None = "ad0e9ab68b84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add sync tracking fields to google_calendar_tokens table."""
    # Add sync_client_names field
    op.add_column(
        "google_calendar_tokens",
        sa.Column(
            "sync_client_names",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Whether to sync client names to Google Calendar event titles (privacy setting)",
        ),
    )

    # Add last_sync_at field
    op.add_column(
        "google_calendar_tokens",
        sa.Column(
            "last_sync_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp of the last successful sync operation",
        ),
    )

    # Add last_sync_status field
    op.add_column(
        "google_calendar_tokens",
        sa.Column(
            "last_sync_status",
            sa.String(50),
            nullable=True,
            comment="Status of the last sync operation (success, error)",
        ),
    )

    # Add last_sync_error field
    op.add_column(
        "google_calendar_tokens",
        sa.Column(
            "last_sync_error",
            sa.Text(),
            nullable=True,
            comment="Error message from the last failed sync operation",
        ),
    )


def downgrade() -> None:
    """Remove sync tracking fields from google_calendar_tokens table."""
    op.drop_column("google_calendar_tokens", "last_sync_error")
    op.drop_column("google_calendar_tokens", "last_sync_status")
    op.drop_column("google_calendar_tokens", "last_sync_at")
    op.drop_column("google_calendar_tokens", "sync_client_names")
