"""clean_empty_payment_configurations

This migration cleans up workspaces that have empty or whitespace-only payment configurations.

Issue:
- Previous migration (0d6b572f1853) automatically migrated Phase 1 workspaces to Phase 1.5
- It set payment_link_type='bank' and payment_link_template=bank_account_details for ALL
  workspaces where bank_account_details IS NOT NULL
- This included workspaces with empty strings or whitespace, causing payments to appear enabled

Fix:
- Clear payment_link_type and payment_link_template where payment_link_template is empty/whitespace
- Clear bank_account_details where it is empty/whitespace
- This ensures payment_mode returns NULL (disabled) for workspaces without real configuration

Revision ID: 2941a42b2723
Revises: 0d6b572f1853
Create Date: 2025-11-04 13:11:32.005917

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2941a42b2723'
down_revision: str | Sequence[str] | None = '0d6b572f1853'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Clean up workspaces with empty payment configurations."""
    # Clear payment_link_type and payment_link_template where template is empty/whitespace
    op.execute(
        """
        UPDATE workspaces
        SET payment_link_type = NULL,
            payment_link_template = NULL
        WHERE payment_link_template IS NOT NULL
          AND TRIM(payment_link_template) = ''
        """
    )

    # Clear bank_account_details where it is empty/whitespace
    op.execute(
        """
        UPDATE workspaces
        SET bank_account_details = NULL
        WHERE bank_account_details IS NOT NULL
          AND TRIM(bank_account_details) = ''
        """
    )


def downgrade() -> None:
    """No downgrade needed - this is a data cleanup migration."""
    pass
