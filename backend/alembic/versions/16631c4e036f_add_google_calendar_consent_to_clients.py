"""add_google_calendar_consent_to_clients

Add google_calendar_consent and google_calendar_consent_date fields
to clients table to track which clients have consented to receive
Google Calendar appointment invitations. Required for HIPAA compliance.

Consent States:
- NULL (None): Client has not been asked for consent
- False: Client declined consent
- True: Client granted consent

Revision ID: 16631c4e036f
Revises: c8f45998f882
Create Date: 2025-10-29 17:03:48.230930

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "16631c4e036f"
down_revision: str | Sequence[str] | None = "c8f45998f882"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add google_calendar_consent column (nullable, default NULL)
    op.add_column(
        "clients",
        sa.Column(
            "google_calendar_consent",
            sa.Boolean(),
            nullable=True,
            comment="Client consent to receive Google Calendar invitations (None=not asked, False=declined, True=consented)",
        ),
    )

    # Add google_calendar_consent_date column
    op.add_column(
        "clients",
        sa.Column(
            "google_calendar_consent_date",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Date when client consented to Google Calendar invitations",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove consent tracking columns
    op.drop_column("clients", "google_calendar_consent_date")
    op.drop_column("clients", "google_calendar_consent")
