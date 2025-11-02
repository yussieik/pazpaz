"""add_bank_details_and_update_payment_methods

This migration enhances the payment system to support dual-mode payments:
- Manual tracking via bank account details (Phase 1)
- Automated provider integration (Phase 2+: Bit, PayBox, etc.)

Architecture: Keeps provider abstraction for future extensibility while
enabling simple manual tracking immediately.

Changes:
1. Add bank_account_details field to workspaces table:
   - bank_account_details (Text, nullable) - for manual payment tracking

2. Drop payment_transactions table:
   - Removes PayPlus-specific transaction tracking
   - Will be replaced with provider-agnostic tracking later

3. Update payment_method CHECK constraint on appointments table:
   - Add: 'bit', 'paybox' (Israeli payment methods)
   - Remove: 'payment_link' (deprecated)

4. Keep payment provider fields (payment_provider, payment_provider_config,
   payment_auto_send, payment_send_timing) for future automated integrations

Revision ID: 6679fc01412c
Revises: 61c48083dbeb
Create Date: 2025-11-02 12:07:31.962269

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6679fc01412c"
down_revision: str | Sequence[str] | None = "61c48083dbeb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add bank details support and update payment methods for dual-mode payments."""
    # Add bank_account_details field to workspaces for manual payment tracking
    op.add_column(
        "workspaces",
        sa.Column(
            "bank_account_details",
            sa.Text(),
            nullable=True,
            comment="Bank account details for manual payment tracking (account number, bank name, branch, etc.)",
        ),
    )

    # Drop payment_transactions table (PayPlus-specific, will be replaced with provider-agnostic tracking)
    # Use CASCADE to drop dependent views and foreign keys
    op.execute("DROP TABLE IF EXISTS payment_transactions CASCADE")

    # Update payment_method CHECK constraint on appointments
    # Drop old constraint
    op.drop_constraint("ck_appointment_payment_method", "appointments")

    # Create new constraint with updated payment methods
    op.create_check_constraint(
        "ck_appointment_payment_method",
        "appointments",
        "payment_method IS NULL OR payment_method IN ('cash', 'card', 'bank_transfer', 'bit', 'paybox', 'other')",
    )


def downgrade() -> None:
    """Rollback bank details and payment method changes.

    WARNING: Downgrade does not recreate payment_transactions table due to complexity.
    If you need to restore payment_transactions, rollback to migration 7530a2393547.
    """
    # Restore payment_method CHECK constraint (revert Bit/PayBox additions)
    op.drop_constraint("ck_appointment_payment_method", "appointments")
    op.create_check_constraint(
        "ck_appointment_payment_method",
        "appointments",
        "payment_method IS NULL OR payment_method IN ('cash', 'card', 'bank_transfer', 'payment_link', 'other')",
    )

    # NOTE: payment_transactions table NOT recreated in downgrade
    # See migration 7530a2393547 for full table definition

    # Remove bank_account_details field
    op.drop_column("workspaces", "bank_account_details")
