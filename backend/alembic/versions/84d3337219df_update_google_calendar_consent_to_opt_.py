"""update_google_calendar_consent_to_opt_out

Change Google Calendar consent model from opt-in to opt-out for better UX.

Legal rationale: Appointment reminders fall under "Healthcare Operations"
(HIPAA §164.506), so opt-out model is HIPAA-compliant and provides better UX.

Changes:
1. Set server default to TRUE (new clients consent by default)
2. Update existing NULL values to TRUE (assume consent for existing clients)
3. Set google_calendar_consent_date for migrated clients

Revision ID: 84d3337219df
Revises: 16631c4e036f
Create Date: 2025-10-29 18:42:10.839176

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "84d3337219df"
down_revision: str | Sequence[str] | None = "16631c4e036f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema to opt-out consent model."""
    # Set server default to true for new clients
    op.alter_column(
        "clients",
        "google_calendar_consent",
        server_default="true",
        comment="Client consent to receive Google Calendar invitations (opt-out model: True=consented by default, False=opted out)",
    )

    # Update existing NULL values to true (assume consent unless explicitly declined)
    # Also set consent_date to NOW() for these clients
    op.execute(
        """
        UPDATE clients
        SET google_calendar_consent = true,
            google_calendar_consent_date = NOW()
        WHERE google_calendar_consent IS NULL
        """
    )


def downgrade() -> None:
    """Downgrade schema back to opt-in consent model."""
    # Remove server default (revert to NULL for new clients)
    op.alter_column(
        "clients",
        "google_calendar_consent",
        server_default=None,
        comment="Client consent to receive Google Calendar invitations (None=not asked, False=declined, True=consented)",
    )

    # NOTE: We do NOT revert existing TRUE values back to NULL
    # because we cannot distinguish between:
    # 1. Clients who explicitly consented (should stay TRUE)
    # 2. Clients who were migrated from NULL to TRUE (could revert to NULL)
    #
    # Since this is a UX improvement and both models are HIPAA-compliant,
    # we preserve existing consent status on downgrade.
