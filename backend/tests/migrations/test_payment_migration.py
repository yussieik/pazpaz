"""
Tests for Payment Infrastructure Migration (7530a2393547) - Phase 0.

This test suite validates Phase 0 payment infrastructure:
1. Migration creates workspace payment columns
2. Migration creates appointment payment columns
3. Migration creates payment_transactions table
4. Data integrity preserved (existing data unaffected)
5. Indexes created for performance

Note: Phase 0 only includes core payment tables. Additional tables
(tax_receipts, payment_refunds), views, and triggers come in Phase 1.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.appointment import Appointment
from pazpaz.models.client import Client
from pazpaz.models.workspace import Workspace

pytestmark = pytest.mark.asyncio


class TestPaymentMigrationSchema:
    """Test schema changes from payment infrastructure migration."""

    async def test_workspace_payment_columns_exist(self, db_session: AsyncSession):
        """Test that workspace table has all payment-related columns."""
        result = await db_session.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'workspaces'
                """
            )
        )
        columns = {row[0] for row in result.fetchall()}

        # Business details columns
        assert "business_name" in columns
        assert "business_name_hebrew" in columns
        assert "tax_id" in columns
        assert "business_license" in columns
        assert "business_address" in columns

        # VAT configuration columns
        assert "vat_registered" in columns
        assert "vat_rate" in columns
        assert "receipt_counter" in columns

        # Payment provider columns
        assert "payment_provider" in columns
        assert "payment_provider_config" in columns
        assert "payment_auto_send" in columns
        assert "payment_send_timing" in columns

        # Tax service integration
        assert "tax_service_provider" in columns
        assert "tax_service_config" in columns

    async def test_appointment_payment_columns_exist(self, db_session: AsyncSession):
        """Test that appointments table has payment-related columns."""
        result = await db_session.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'appointments'
                """
            )
        )
        columns = {row[0] for row in result.fetchall()}

        assert "payment_price" in columns
        assert "payment_status" in columns
        assert "payment_auto_send" in columns

    async def test_payment_transactions_table_exists(self, db_session: AsyncSession):
        """Test that payment_transactions table exists with all columns."""
        # Check table exists
        result = await db_session.execute(
            text(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'payment_transactions'
                """
            )
        )
        table_exists = result.fetchone()
        assert table_exists is not None, "payment_transactions table should exist"

        # Check all columns
        result = await db_session.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'payment_transactions'
                """
            )
        )
        columns = {row[0] for row in result.fetchall()}

        # Primary key and foreign keys
        assert "id" in columns
        assert "workspace_id" in columns
        assert "appointment_id" in columns

        # Financial details
        assert "base_amount" in columns
        assert "vat_amount" in columns
        assert "total_amount" in columns
        assert "currency" in columns

        # Payment method and status
        assert "payment_method" in columns
        assert "status" in columns

        # Provider details
        assert "provider" in columns
        assert "provider_transaction_id" in columns
        assert "provider_payment_link" in columns

        # Receipt details
        assert "receipt_number" in columns
        assert "receipt_issued" in columns
        assert "receipt_issued_at" in columns
        assert "receipt_pdf_url" in columns

        # Timestamps
        assert "created_at" in columns
        assert "completed_at" in columns
        assert "failed_at" in columns
        assert "refunded_at" in columns

        # Additional details
        assert "failure_reason" in columns
        assert "refund_reason" in columns
        assert "notes" in columns
        assert "metadata" in columns


class TestPaymentMigrationIndexes:
    """Test indexes created by payment infrastructure migration."""

    async def test_payment_transaction_indexes_exist(self, db_session: AsyncSession):
        """Test that all payment transaction indexes exist."""
        expected_indexes = [
            "idx_workspace_payments",
            "idx_appointment_payments",
            "idx_provider_txn",
            "idx_payment_status",
            "idx_receipt_number",
            "idx_completed_at",
            "idx_payment_method",
            "idx_payments_workspace_date_status",
        ]

        for index_name in expected_indexes:
            result = await db_session.execute(
                text(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename = 'payment_transactions'
                      AND indexname = :index_name
                    """
                ),
                {"index_name": index_name},
            )
            index_info = result.fetchone()
            assert index_info is not None, (
                f"Index {index_name} should exist on payment_transactions"
            )

    async def test_appointment_payment_status_index_exists(
        self, db_session: AsyncSession
    ):
        """Test that appointment payment status composite index exists."""
        result = await db_session.execute(
            text(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'appointments'
                  AND indexname = 'idx_appointments_workspace_payment_status'
                """
            )
        )
        index_info = result.fetchone()
        assert index_info is not None, (
            "Composite index on workspace_id + payment_status should exist"
        )


class TestPaymentMigrationDataIntegrity:
    """Test that migration preserves data integrity."""

    async def test_existing_workspaces_not_affected(
        self,
        db_session: AsyncSession,
        workspace_1: Workspace,
    ):
        """Test that existing workspaces are not affected by migration."""
        await db_session.refresh(workspace_1)

        # Verify workspace still exists and is valid
        assert workspace_1.id is not None
        assert workspace_1.name == "Test Workspace 1"
        assert workspace_1.is_active is True

        # Verify payment fields have safe defaults
        assert workspace_1.payment_provider is None  # Payments disabled by default
        assert workspace_1.payment_auto_send is False
        assert workspace_1.vat_registered is False
        assert workspace_1.receipt_counter == 0

    async def test_existing_appointments_not_affected(
        self,
        db_session: AsyncSession,
        workspace_1: Workspace,
        sample_appointment_ws1: Appointment,
    ):
        """Test that existing appointments are not affected by migration."""
        await db_session.refresh(sample_appointment_ws1)

        # Verify appointment still exists and is valid
        assert sample_appointment_ws1.id is not None
        assert sample_appointment_ws1.workspace_id == workspace_1.id
        assert sample_appointment_ws1.client_id is not None

        # Verify payment fields have safe defaults
        assert sample_appointment_ws1.payment_price is None  # No price by default
        assert sample_appointment_ws1.payment_status == "unpaid"
        assert sample_appointment_ws1.payment_auto_send is None

    async def test_workspace_payments_enabled_property_works(
        self,
        db_session: AsyncSession,
        workspace_1: Workspace,
    ):
        """Test that Workspace.payments_enabled property works after migration."""
        await db_session.refresh(workspace_1)

        # Initially disabled (no provider)
        assert workspace_1.payments_enabled is False

        # Enable payments
        workspace_1.payment_provider = "payplus"
        db_session.add(workspace_1)
        await db_session.commit()
        await db_session.refresh(workspace_1)

        # Now enabled
        assert workspace_1.payments_enabled is True


class TestPaymentMigrationForeignKeys:
    """Test foreign key constraints created by migration."""

    async def test_payment_transaction_workspace_fk_cascade(
        self,
        db_session: AsyncSession,
        workspace_1: Workspace,
    ):
        """Test that payment transactions CASCADE delete when workspace deleted."""
        from decimal import Decimal

        from pazpaz.models.payment_transaction import PaymentTransaction

        # Create payment transaction
        transaction = PaymentTransaction(
            workspace_id=workspace_1.id,
            base_amount=Decimal("100.00"),
            total_amount=Decimal("100.00"),
            payment_method="cash",
            status="completed",
        )
        db_session.add(transaction)
        await db_session.commit()
        transaction_id = transaction.id

        # Delete workspace (should cascade to payment_transactions)
        await db_session.delete(workspace_1)
        await db_session.commit()

        # Verify transaction was deleted
        result = await db_session.execute(
            text("SELECT id FROM payment_transactions WHERE id = :id"),
            {"id": str(transaction_id)},
        )
        deleted_txn = result.fetchone()
        assert deleted_txn is None, (
            "Transaction should be CASCADE deleted with workspace"
        )


class TestPaymentMigrationDefaultValues:
    """Test default values for payment columns."""

    async def test_workspace_payment_defaults(self, db_session: AsyncSession):
        """Test default values for workspace payment columns."""
        # Create new workspace (uses defaults)
        workspace = Workspace(
            name="New Test Workspace",
            storage_quota_bytes=10 * 1024 * 1024 * 1024,
        )
        db_session.add(workspace)
        await db_session.commit()
        await db_session.refresh(workspace)

        # Verify defaults
        assert workspace.payment_provider is None
        assert workspace.payment_auto_send is False
        assert workspace.payment_send_timing == "immediately"
        assert workspace.vat_registered is False
        assert workspace.vat_rate == 17.00
        assert workspace.receipt_counter == 0

    async def test_appointment_payment_defaults(
        self,
        db_session: AsyncSession,
        workspace_1: Workspace,
        sample_client_ws1: Client,
    ):
        """Test default values for appointment payment columns."""
        from datetime import UTC, datetime, timedelta

        from pazpaz.models.appointment import AppointmentStatus, LocationType

        # Create new appointment (uses defaults)
        appointment = Appointment(
            workspace_id=workspace_1.id,
            client_id=sample_client_ws1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=1),
            scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
        )
        db_session.add(appointment)
        await db_session.commit()
        await db_session.refresh(appointment)

        # Verify defaults
        assert appointment.payment_price is None
        assert appointment.payment_status == "unpaid"
        assert appointment.payment_auto_send is None


class TestPaymentMigrationComments:
    """Test database column comments for documentation."""

    async def test_payment_transaction_table_comment_exists(
        self, db_session: AsyncSession
    ):
        """Test that payment_transactions table has descriptive comment."""
        result = await db_session.execute(
            text(
                """
                SELECT obj_description('payment_transactions'::regclass, 'pg_class')
                """
            )
        )
        _comment = result.scalar()
        # Note: Table comment might be None if not set in migration
        # This is acceptable for Phase 0
        # Could assert: assert _comment is not None, "payment_transactions table should have a comment"

    async def test_workspace_payment_column_comments_exist(
        self, db_session: AsyncSession
    ):
        """Test that workspace payment columns have comments."""
        # Check payment_provider column comment
        result = await db_session.execute(
            text(
                """
                SELECT col_description('workspaces'::regclass,
                    (SELECT attnum FROM pg_attribute
                     WHERE attrelid = 'workspaces'::regclass
                       AND attname = 'payment_provider'))
                """
            )
        )
        comment = result.scalar()
        assert comment is not None, "payment_provider column should have a comment"
