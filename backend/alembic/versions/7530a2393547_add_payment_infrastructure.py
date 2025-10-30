"""add_payment_infrastructure

Revision ID: 7530a2393547
Revises: 84d3337219df
Create Date: 2025-10-30 10:22:12.454468

This migration adds payment infrastructure for Israeli tax compliance:
- Workspace payment configuration and business details
- Appointment payment fields
- Payment transactions table with full audit trail
- Tax receipts table for Israeli Tax Authority compliance
- Payment refunds tracking
- Views for financial reporting
- Indexes optimized for payment queries

All columns are nullable or have defaults to ensure zero-downtime deployment.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7530a2393547"
down_revision: str | Sequence[str] | None = "84d3337219df"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - Add payment infrastructure."""

    # ============================================================================
    # 1. WORKSPACE ENHANCEMENTS - Business/Tax Details & Payment Config
    # ============================================================================

    # Business details for tax receipts
    op.add_column(
        "workspaces",
        sa.Column(
            "business_name",
            sa.String(255),
            nullable=True,
            comment="Legal business name",
        ),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "business_name_hebrew",
            sa.String(255),
            nullable=True,
            comment="Business name in Hebrew (שם העסק בעברית)",
        ),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "tax_id",
            sa.String(20),
            nullable=True,
            comment="Israeli Tax ID (ת.ז. or ח.פ.)",
        ),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "business_license",
            sa.String(50),
            nullable=True,
            comment="Business license number (מספר רישיון עסק)",
        ),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "business_address",
            sa.Text(),
            nullable=True,
            comment="Business address for tax receipts",
        ),
    )

    # VAT configuration
    op.add_column(
        "workspaces",
        sa.Column(
            "vat_registered",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Whether workspace is VAT registered (עוסק מורשה)",
        ),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "vat_rate",
            sa.NUMERIC(5, 2),
            nullable=False,
            server_default="17.00",
            comment="VAT rate percentage (default 17% for Israel)",
        ),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "receipt_counter",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Auto-incrementing counter for receipt numbers",
        ),
    )

    # Payment provider configuration (feature flag)
    op.add_column(
        "workspaces",
        sa.Column(
            "payment_provider",
            sa.String(50),
            nullable=True,
            comment="Payment provider: payplus, meshulam, stripe, null (disabled)",
        ),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "payment_provider_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Encrypted payment provider API keys and configuration",
        ),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "payment_auto_send",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Automatically send payment requests",
        ),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "payment_send_timing",
            sa.String(20),
            nullable=False,
            server_default="immediately",
            comment="When to send payment requests: immediately, end_of_day, end_of_month, manual",
        ),
    )

    # Third-party tax service integration (optional)
    op.add_column(
        "workspaces",
        sa.Column(
            "tax_service_provider",
            sa.String(50),
            nullable=True,
            comment="Third-party tax service: greeninvoice, morning, ness, null",
        ),
    )
    op.add_column(
        "workspaces",
        sa.Column(
            "tax_service_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Tax service API configuration",
        ),
    )

    # ============================================================================
    # 2. APPOINTMENT ENHANCEMENTS - Payment Fields
    # ============================================================================

    op.add_column(
        "appointments",
        sa.Column(
            "payment_price",
            sa.NUMERIC(10, 2),
            nullable=True,
            comment="Appointment price in ILS (null = no price set)",
        ),
    )
    op.add_column(
        "appointments",
        sa.Column(
            "payment_status",
            sa.String(20),
            nullable=False,
            server_default="unpaid",
            comment="Payment status: unpaid, pending, paid, partially_paid, refunded, failed",
        ),
    )
    op.add_column(
        "appointments",
        sa.Column(
            "payment_auto_send",
            sa.Boolean(),
            nullable=True,
            comment="Override workspace auto-send setting (null = use workspace default)",
        ),
    )

    # Index for filtering appointments by payment status
    op.create_index(
        "idx_appointments_workspace_payment_status",
        "appointments",
        ["workspace_id", "payment_status"],
    )

    # ============================================================================
    # 3. PAYMENT TRANSACTIONS - Core Payment Tracking
    # ============================================================================

    op.create_table(
        "payment_transactions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "appointment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("appointments.id", ondelete="SET NULL"),
            nullable=True,
            comment="Optional reference to appointment (null for standalone payments)",
        ),
        # Financial details
        sa.Column(
            "base_amount",
            sa.NUMERIC(10, 2),
            nullable=False,
            comment='Amount before VAT (מחיר לפני מע"מ)',
        ),
        sa.Column(
            "vat_amount",
            sa.NUMERIC(10, 2),
            nullable=False,
            server_default="0",
            comment='VAT amount (מע"מ)',
        ),
        sa.Column(
            "total_amount",
            sa.NUMERIC(10, 2),
            nullable=False,
            comment="Total amount (base + VAT)",
        ),
        sa.Column(
            "currency",
            sa.String(3),
            nullable=False,
            server_default="ILS",
            comment="Currency code (ILS, USD, EUR)",
        ),
        # Payment method
        sa.Column(
            "payment_method",
            sa.String(50),
            nullable=False,
            comment="Payment method: online_card, cash, bank_transfer, check, paypal, apple_pay, google_pay",
        ),
        # Status tracking
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            comment="Status: pending, completed, failed, refunded, cancelled",
        ),
        # Provider details (for online payments)
        sa.Column(
            "provider",
            sa.String(50),
            nullable=True,
            comment="Payment provider: payplus, meshulam, stripe, manual",
        ),
        sa.Column(
            "provider_transaction_id",
            sa.String(255),
            nullable=True,
            comment="Provider transaction ID",
        ),
        sa.Column(
            "provider_payment_link",
            sa.Text(),
            nullable=True,
            comment="Payment link sent to client",
        ),
        # Receipt details
        sa.Column(
            "receipt_number",
            sa.String(50),
            nullable=True,
            comment="Sequential receipt number (e.g., 2025-001234)",
        ),
        sa.Column(
            "receipt_issued",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Whether receipt was issued",
        ),
        sa.Column(
            "receipt_issued_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When receipt was issued",
        ),
        sa.Column(
            "receipt_pdf_url",
            sa.Text(),
            nullable=True,
            comment="S3/MinIO URL for receipt PDF",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
            comment="When transaction was created",
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When payment was completed",
        ),
        sa.Column(
            "failed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When payment failed",
        ),
        sa.Column(
            "refunded_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When payment was refunded",
        ),
        # Additional details
        sa.Column(
            "failure_reason",
            sa.Text(),
            nullable=True,
            comment="Reason for payment failure",
        ),
        sa.Column(
            "refund_reason", sa.Text(), nullable=True, comment="Reason for refund"
        ),
        sa.Column(
            "notes",
            sa.Text(),
            nullable=True,
            comment='Manual payment notes (e.g., "Client paid cash")',
        ),
        # Metadata (flexible JSONB for provider-specific data)
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Provider-specific metadata",
        ),
        comment="Core payment tracking table supporting online and manual payments",
    )

    # Indexes for payment_transactions performance
    op.create_index(
        "idx_workspace_payments",
        "payment_transactions",
        ["workspace_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_appointment_payments", "payment_transactions", ["appointment_id"]
    )
    op.create_index(
        "idx_provider_txn", "payment_transactions", ["provider_transaction_id"]
    )
    op.create_index("idx_payment_status", "payment_transactions", ["status"])
    op.create_index("idx_receipt_number", "payment_transactions", ["receipt_number"])
    op.create_index("idx_completed_at", "payment_transactions", ["completed_at"])
    op.create_index("idx_payment_method", "payment_transactions", ["payment_method"])
    op.create_index(
        "idx_payments_workspace_date_status",
        "payment_transactions",
        ["workspace_id", sa.text("completed_at DESC"), "status"],
    )

    # Partial index for completed payments (reporting queries)
    op.execute("""
        CREATE INDEX idx_payments_date_range
        ON payment_transactions(workspace_id, completed_at)
        WHERE status = 'completed'
    """)

    # ============================================================================
    # 4. TAX RECEIPTS - Israeli Tax Authority Compliance
    # ============================================================================

    op.create_table(
        "tax_receipts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "payment_transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payment_transactions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Receipt identification
        sa.Column(
            "receipt_number",
            sa.String(50),
            nullable=False,
            comment="Sequential receipt number",
        ),
        sa.Column(
            "receipt_date", sa.Date(), nullable=False, comment="Date receipt was issued"
        ),
        sa.Column(
            "fiscal_year",
            sa.Integer(),
            nullable=False,
            comment="Fiscal year (e.g., 2025)",
        ),
        # Tax authority fields (Israel-specific)
        sa.Column(
            "allocation_number",
            sa.String(50),
            nullable=True,
            comment="Israel Tax Authority allocation number (מספר הקצאה)",
        ),
        sa.Column(
            "tax_authority_status",
            sa.String(20),
            nullable=False,
            server_default="not_submitted",
            comment="Status: not_submitted, pending, submitted, approved, rejected",
        ),
        sa.Column(
            "tax_authority_submitted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When submitted to tax authority",
        ),
        sa.Column(
            "tax_authority_response",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Tax authority API response",
        ),
        # Financial breakdown
        sa.Column(
            "base_amount",
            sa.NUMERIC(10, 2),
            nullable=False,
            comment="Amount before VAT",
        ),
        sa.Column(
            "vat_amount",
            sa.NUMERIC(10, 2),
            nullable=False,
            server_default="0",
            comment="VAT amount",
        ),
        sa.Column(
            "total_amount", sa.NUMERIC(10, 2), nullable=False, comment="Total amount"
        ),
        sa.Column(
            "currency",
            sa.String(3),
            nullable=False,
            server_default="ILS",
            comment="Currency code",
        ),
        # Client details (optional, anonymized if needed)
        sa.Column(
            "client_name",
            sa.String(255),
            nullable=True,
            comment='Client name (can be "Anonymous")',
        ),
        sa.Column(
            "client_tax_id",
            sa.String(20),
            nullable=True,
            comment="Client tax ID (for B2B)",
        ),
        sa.Column(
            "client_business_name",
            sa.String(255),
            nullable=True,
            comment="Client business name (B2B)",
        ),
        # Service details
        sa.Column(
            "service_description",
            sa.Text(),
            nullable=False,
            server_default="Therapy session",
            comment="Service description",
        ),
        sa.Column(
            "service_date",
            sa.Date(),
            nullable=True,
            comment="Date service was provided",
        ),
        # PDF storage
        sa.Column(
            "pdf_url", sa.Text(), nullable=False, comment="S3/MinIO URL for receipt PDF"
        ),
        sa.Column(
            "pdf_generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="When PDF was generated",
        ),
        # Third-party tax service integration
        sa.Column(
            "external_invoice_id",
            sa.String(255),
            nullable=True,
            comment="GreenInvoice/Morning invoice ID",
        ),
        sa.Column(
            "external_invoice_url",
            sa.Text(),
            nullable=True,
            comment="External service invoice URL",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        comment="Tax-compliant receipts (מס קבלה) for Israeli Tax Authority",
    )

    # Unique constraint: receipt_number per workspace
    op.create_unique_constraint(
        "uq_workspace_receipt_number",
        "tax_receipts",
        ["workspace_id", "receipt_number"],
    )

    # Indexes for tax_receipts
    op.create_index(
        "idx_workspace_receipts",
        "tax_receipts",
        ["workspace_id", sa.text("receipt_date DESC")],
    )
    op.create_index("idx_tax_receipt_number", "tax_receipts", ["receipt_number"])
    op.create_index("idx_fiscal_year", "tax_receipts", ["fiscal_year"])
    op.create_index("idx_tax_status", "tax_receipts", ["tax_authority_status"])
    op.create_index("idx_allocation_number", "tax_receipts", ["allocation_number"])
    op.create_index(
        "idx_receipts_fiscal_year",
        "tax_receipts",
        ["workspace_id", "fiscal_year", "receipt_date"],
    )

    # ============================================================================
    # 5. PAYMENT REFUNDS - Refund Tracking
    # ============================================================================

    op.create_table(
        "payment_refunds",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "original_transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("payment_transactions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Refund details
        sa.Column(
            "refund_amount", sa.NUMERIC(10, 2), nullable=False, comment="Refund amount"
        ),
        sa.Column(
            "refund_reason", sa.Text(), nullable=True, comment="Reason for refund"
        ),
        sa.Column(
            "refund_method",
            sa.String(50),
            nullable=True,
            comment="Refund method: original_payment_method, cash, bank_transfer",
        ),
        # Provider details (for online refunds)
        sa.Column("provider", sa.String(50), nullable=True, comment="Payment provider"),
        sa.Column(
            "provider_refund_id",
            sa.String(255),
            nullable=True,
            comment="Provider refund transaction ID",
        ),
        # Status
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            comment="Status: pending, completed, failed",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When refund was completed",
        ),
        # Metadata
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="Provider-specific refund metadata",
        ),
        comment="Tracks all refund transactions",
    )

    # Indexes for payment_refunds
    op.create_index(
        "idx_workspace_refunds",
        "payment_refunds",
        ["workspace_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_original_transaction", "payment_refunds", ["original_transaction_id"]
    )

    # ============================================================================
    # 6. FINANCIAL REPORTING VIEWS
    # ============================================================================

    # View: Monthly revenue summary
    op.execute("""
        CREATE VIEW monthly_revenue_summary AS
        SELECT
            workspace_id,
            DATE_TRUNC('month', completed_at) AS month,
            COUNT(*) AS payment_count,
            SUM(base_amount) AS total_base_amount,
            SUM(vat_amount) AS total_vat_amount,
            SUM(total_amount) AS total_revenue,
            SUM(CASE WHEN payment_method = 'online_card' THEN total_amount ELSE 0 END) AS online_revenue,
            SUM(CASE WHEN payment_method = 'cash' THEN total_amount ELSE 0 END) AS cash_revenue,
            SUM(CASE WHEN payment_method = 'bank_transfer' THEN total_amount ELSE 0 END) AS bank_transfer_revenue
        FROM payment_transactions
        WHERE status = 'completed'
        GROUP BY workspace_id, DATE_TRUNC('month', completed_at)
    """)

    # View: Outstanding payments
    op.execute("""
        CREATE VIEW outstanding_payments AS
        SELECT
            workspace_id,
            COUNT(*) AS outstanding_count,
            SUM(total_amount) AS outstanding_amount,
            MIN(created_at) AS oldest_request,
            MAX(created_at) AS newest_request
        FROM payment_transactions
        WHERE status = 'pending' AND provider IS NOT NULL
        GROUP BY workspace_id
    """)

    # View: Payment method breakdown
    op.execute("""
        CREATE VIEW payment_method_breakdown AS
        SELECT
            workspace_id,
            payment_method,
            COUNT(*) AS transaction_count,
            SUM(total_amount) AS total_amount,
            AVG(total_amount) AS avg_amount
        FROM payment_transactions
        WHERE status = 'completed'
        GROUP BY workspace_id, payment_method
    """)

    # ============================================================================
    # 7. TRIGGERS
    # ============================================================================

    # Trigger: Auto-update updated_at for tax_receipts
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        CREATE TRIGGER update_tax_receipts_updated_at
        BEFORE UPDATE ON tax_receipts
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column()
    """)

    # Trigger: Auto-generate receipt number when receipt is issued
    op.execute("""
        CREATE OR REPLACE FUNCTION generate_receipt_number()
        RETURNS TRIGGER AS $$
        DECLARE
            new_counter INTEGER;
            new_receipt_number VARCHAR(50);
        BEGIN
            -- Only generate if receipt_issued is being set to true
            IF NEW.receipt_issued = true AND (OLD.receipt_issued IS NULL OR OLD.receipt_issued = false) THEN
                -- Atomically increment counter
                UPDATE workspaces
                SET receipt_counter = receipt_counter + 1
                WHERE id = NEW.workspace_id
                RETURNING receipt_counter INTO new_counter;

                -- Generate receipt number: YYYY-NNNNNN
                new_receipt_number := EXTRACT(YEAR FROM NOW())::TEXT || '-' || LPAD(new_counter::TEXT, 6, '0');

                NEW.receipt_number := new_receipt_number;
                NEW.receipt_issued_at := NOW();
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)

    op.execute("""
        CREATE TRIGGER generate_payment_receipt_number
        BEFORE UPDATE ON payment_transactions
        FOR EACH ROW
        EXECUTE FUNCTION generate_receipt_number()
    """)


def downgrade() -> None:
    """Downgrade schema - Remove payment infrastructure."""

    # Drop triggers
    op.execute(
        "DROP TRIGGER IF EXISTS generate_payment_receipt_number ON payment_transactions"
    )
    op.execute("DROP TRIGGER IF EXISTS update_tax_receipts_updated_at ON tax_receipts")
    op.execute("DROP FUNCTION IF EXISTS generate_receipt_number()")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")

    # Drop views
    op.execute("DROP VIEW IF EXISTS payment_method_breakdown")
    op.execute("DROP VIEW IF EXISTS outstanding_payments")
    op.execute("DROP VIEW IF EXISTS monthly_revenue_summary")

    # Drop tables (in reverse dependency order)
    op.drop_table("payment_refunds")
    op.drop_table("tax_receipts")
    op.drop_table("payment_transactions")

    # Drop appointment payment fields
    op.drop_index(
        "idx_appointments_workspace_payment_status", table_name="appointments"
    )
    op.drop_column("appointments", "payment_auto_send")
    op.drop_column("appointments", "payment_status")
    op.drop_column("appointments", "payment_price")

    # Drop workspace payment fields (in reverse order)
    op.drop_column("workspaces", "tax_service_config")
    op.drop_column("workspaces", "tax_service_provider")
    op.drop_column("workspaces", "payment_send_timing")
    op.drop_column("workspaces", "payment_auto_send")
    op.drop_column("workspaces", "payment_provider_config")
    op.drop_column("workspaces", "payment_provider")
    op.drop_column("workspaces", "receipt_counter")
    op.drop_column("workspaces", "vat_rate")
    op.drop_column("workspaces", "vat_registered")
    op.drop_column("workspaces", "business_address")
    op.drop_column("workspaces", "business_license")
    op.drop_column("workspaces", "tax_id")
    op.drop_column("workspaces", "business_name_hebrew")
    op.drop_column("workspaces", "business_name")
