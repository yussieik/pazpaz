"""add_payment_link_fields

This migration implements Phase 1.5 Smart Payment Links by adding fields to support
smart payment link generation without API integration.

Phase 1.5 Features:
- Generate smart links for Israeli payment apps (Bit, PayBox)
- Generate bank transfer request messages
- Store custom payment link templates

New Fields:
1. payment_link_type: Type of payment link (bit, paybox, bank, custom, NULL)
2. payment_link_template: Template for generating payment links (phone/URL/bank details)

Data Migration:
- Workspaces with existing bank_account_details automatically get:
  * payment_link_type = 'bank'
  * payment_link_template = bank_account_details (copied)
- This ensures Phase 1 workspaces seamlessly upgrade to Phase 1.5

Backwards Compatibility:
- Keeps bank_account_details field (Phase 1 compatibility)
- Keeps payment_provider/payment_provider_config (Phase 2+ future use)
- All new fields nullable (opt-in)

Revision ID: 0d6b572f1853
Revises: 6679fc01412c
Create Date: 2025-11-02 15:30:39.050445

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0d6b572f1853"
down_revision: str | Sequence[str] | None = "6679fc01412c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add payment link fields to workspaces table and migrate existing data."""
    # Add payment_link_type field
    op.add_column(
        "workspaces",
        sa.Column(
            "payment_link_type",
            sa.String(length=50),
            nullable=True,
            comment="Type of payment link: bit, paybox, bank, custom, NULL (disabled)",
        ),
    )

    # Add payment_link_template field
    op.add_column(
        "workspaces",
        sa.Column(
            "payment_link_template",
            sa.String(length=500),
            nullable=True,
            comment="Template for payment links: phone number (Bit/PayBox), URL (custom), or bank details (bank)",
        ),
    )

    # Data Migration: Upgrade Phase 1 workspaces to Phase 1.5
    # If workspace has bank_account_details, set payment_link_type='bank'
    # and copy bank_account_details to payment_link_template
    op.execute(
        """
        UPDATE workspaces
        SET payment_link_type = 'bank',
            payment_link_template = bank_account_details
        WHERE bank_account_details IS NOT NULL
        """
    )

    # Add CHECK constraint for payment_link_type (valid values only)
    op.create_check_constraint(
        "ck_workspace_payment_link_type",
        "workspaces",
        "payment_link_type IS NULL OR payment_link_type IN ('bit', 'paybox', 'bank', 'custom')",
    )


def downgrade() -> None:
    """Remove payment link fields from workspaces table.

    WARNING: This downgrade removes payment_link_type and payment_link_template
    but does NOT delete the data. If you re-run upgrade, workspaces with
    bank_account_details will be re-migrated to payment_link_type='bank'.
    """
    # Drop CHECK constraint first
    op.drop_constraint("ck_workspace_payment_link_type", "workspaces", type_="check")

    # Drop columns (data will be lost)
    op.drop_column("workspaces", "payment_link_template")
    op.drop_column("workspaces", "payment_link_type")
