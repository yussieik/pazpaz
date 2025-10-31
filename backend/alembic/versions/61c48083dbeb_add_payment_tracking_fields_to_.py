"""add_payment_tracking_fields_to_appointments

This migration adds enhanced payment tracking to appointments:
- payment_method: How the payment was collected (cash, card, etc.)
- payment_notes: Free-text notes about payment
- paid_at: Timestamp when payment was marked as paid
- Updates payment_status values to new schema (not_paid, paid, payment_sent, waived)
- Adds CHECK constraints for data integrity
- Updates composite index for payment status filtering

The migration is designed for zero-downtime deployment:
- New columns are nullable or have defaults
- Index created with CONCURRENTLY (requires connection with autocommit)
- Old payment_status values migrated to new values

Revision ID: 61c48083dbeb
Revises: 7530a2393547
Create Date: 2025-10-31 16:05:53.530386

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "61c48083dbeb"
down_revision: str | Sequence[str] | None = "7530a2393547"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add payment tracking fields to appointments table."""
    # Add new columns
    op.add_column(
        "appointments",
        sa.Column(
            "payment_method",
            sa.String(length=20),
            nullable=True,
            comment="Payment method: cash, card, bank_transfer, payment_link, other",
        ),
    )
    op.add_column(
        "appointments",
        sa.Column(
            "payment_notes",
            sa.Text(),
            nullable=True,
            comment="Free-text notes about payment (e.g., invoice number, special terms)",
        ),
    )
    op.add_column(
        "appointments",
        sa.Column(
            "paid_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp when payment was marked as paid",
        ),
    )

    # Migrate existing payment_status values to new schema
    # Old values: unpaid, pending, paid, partially_paid, refunded, failed
    # New values: not_paid, paid, payment_sent, waived
    op.execute(
        """
        UPDATE appointments
        SET payment_status = CASE
            WHEN payment_status = 'unpaid' THEN 'not_paid'
            WHEN payment_status = 'pending' THEN 'payment_sent'
            WHEN payment_status = 'paid' THEN 'paid'
            WHEN payment_status = 'partially_paid' THEN 'not_paid'
            WHEN payment_status = 'refunded' THEN 'waived'
            WHEN payment_status = 'failed' THEN 'not_paid'
            ELSE 'not_paid'
        END
        WHERE payment_status NOT IN ('not_paid', 'paid', 'payment_sent', 'waived')
        """
    )

    # Update default value for payment_status
    op.alter_column(
        "appointments",
        "payment_status",
        server_default="not_paid",
        comment="Payment status: not_paid, paid, payment_sent, waived",
    )

    # Add CHECK constraints for data integrity
    op.create_check_constraint(
        "ck_appointment_payment_status",
        "appointments",
        "payment_status IN ('not_paid', 'paid', 'payment_sent', 'waived')",
    )
    op.create_check_constraint(
        "ck_appointment_payment_method",
        "appointments",
        "payment_method IS NULL OR payment_method IN ('cash', 'card', 'bank_transfer', 'payment_link', 'other')",
    )
    op.create_check_constraint(
        "ck_appointment_payment_price_positive",
        "appointments",
        "payment_price IS NULL OR payment_price >= 0",
    )
    op.create_check_constraint(
        "ck_appointment_paid_at_consistency",
        "appointments",
        "(payment_status = 'paid' AND paid_at IS NOT NULL) OR (payment_status != 'paid')",
    )

    # Drop old index and create new one
    # Note: The old index was idx_appointments_workspace_payment_status
    # We're replacing it with ix_appointments_workspace_payment_status
    op.drop_index(
        "idx_appointments_workspace_payment_status",
        table_name="appointments",
        postgresql_using="btree",
    )

    # Create index CONCURRENTLY for zero-downtime deployment
    # Note: This requires a connection with autocommit enabled
    # If migration fails here, manually create index with:
    # CREATE INDEX CONCURRENTLY ix_appointments_workspace_payment_status
    # ON appointments (workspace_id, payment_status);
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_appointments_workspace_payment_status",
            "appointments",
            ["workspace_id", "payment_status"],
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    """Remove payment tracking fields from appointments table."""
    # Drop index
    op.drop_index(
        "ix_appointments_workspace_payment_status",
        table_name="appointments",
        postgresql_using="btree",
    )

    # Recreate old index
    op.create_index(
        "idx_appointments_workspace_payment_status",
        "appointments",
        ["workspace_id", "payment_status"],
    )

    # Drop CHECK constraints
    op.drop_constraint("ck_appointment_paid_at_consistency", "appointments")
    op.drop_constraint("ck_appointment_payment_price_positive", "appointments")
    op.drop_constraint("ck_appointment_payment_method", "appointments")
    op.drop_constraint("ck_appointment_payment_status", "appointments")

    # Revert payment_status values to old schema
    op.execute(
        """
        UPDATE appointments
        SET payment_status = CASE
            WHEN payment_status = 'not_paid' THEN 'unpaid'
            WHEN payment_status = 'payment_sent' THEN 'pending'
            WHEN payment_status = 'paid' THEN 'paid'
            WHEN payment_status = 'waived' THEN 'refunded'
            ELSE 'unpaid'
        END
        """
    )

    # Revert default value
    op.alter_column(
        "appointments",
        "payment_status",
        server_default="unpaid",
        comment="Payment status: unpaid, pending, paid, partially_paid, refunded, failed",
    )

    # Drop new columns
    op.drop_column("appointments", "paid_at")
    op.drop_column("appointments", "payment_notes")
    op.drop_column("appointments", "payment_method")
