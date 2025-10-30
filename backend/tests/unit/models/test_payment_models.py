"""
Tests for Payment models.

This test suite validates:
1. Workspace.payments_enabled property
2. PaymentTransaction model fields and validation
3. PaymentFeatureChecker utility logic
4. Model relationships (workspace → payment_transactions)
5. Helper methods (is_completed, is_pending, is_failed)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.appointment import Appointment, AppointmentStatus, LocationType
from pazpaz.models.client import Client
from pazpaz.models.payment_transaction import PaymentTransaction
from pazpaz.models.workspace import Workspace
from pazpaz.utils.payment_features import PaymentFeatureChecker

# ==============================================================================
# Workspace Payment Configuration Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_workspace_payments_disabled_by_default(db_session: AsyncSession):
    """Test that payments are disabled by default for new workspaces."""
    workspace = Workspace(
        name="Test Clinic",
        storage_quota_bytes=10 * 1024 * 1024 * 1024,
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)

    # Verify payments disabled by default
    assert workspace.payments_enabled is False
    assert workspace.payment_provider is None
    assert workspace.payment_auto_send is False
    assert workspace.payment_send_timing == "immediately"
    assert workspace.vat_registered is False


@pytest.mark.asyncio
async def test_workspace_payments_enabled_when_provider_set(db_session: AsyncSession):
    """Test that payments are enabled when payment_provider is set."""
    workspace = Workspace(
        name="Test Clinic",
        payment_provider="payplus",
        storage_quota_bytes=10 * 1024 * 1024 * 1024,
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)

    # Verify payments enabled when provider set
    assert workspace.payments_enabled is True
    assert workspace.payment_provider == "payplus"


@pytest.mark.asyncio
async def test_workspace_payment_provider_options(db_session: AsyncSession):
    """Test different payment provider values."""
    providers = ["payplus", "meshulam", "stripe", None]

    for provider in providers:
        workspace = Workspace(
            name=f"Clinic {provider}",
            payment_provider=provider,
            storage_quota_bytes=10 * 1024 * 1024 * 1024,
        )
        db_session.add(workspace)
        await db_session.commit()
        await db_session.refresh(workspace)

        # Verify payments_enabled reflects provider setting
        expected_enabled = provider is not None
        assert workspace.payments_enabled == expected_enabled, (
            f"Provider {provider} should have enabled={expected_enabled}"
        )


@pytest.mark.asyncio
async def test_workspace_payment_business_details(db_session: AsyncSession):
    """Test workspace business details for tax receipts."""
    workspace = Workspace(
        name="Professional Therapy Clinic",
        payment_provider="payplus",
        business_name="Professional Therapy Ltd",
        business_name_hebrew="טיפול מקצועי בע״מ",
        tax_id="123456789",
        business_license="BL-2025-001",
        business_address="123 Main St, Tel Aviv, Israel",
        vat_registered=True,
        vat_rate=Decimal("17.00"),
        receipt_counter=0,
        storage_quota_bytes=10 * 1024 * 1024 * 1024,
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)

    # Verify business details
    assert workspace.business_name == "Professional Therapy Ltd"
    assert workspace.business_name_hebrew == "טיפול מקצועי בע״מ"
    assert workspace.tax_id == "123456789"
    assert workspace.business_license == "BL-2025-001"
    assert workspace.business_address == "123 Main St, Tel Aviv, Israel"
    assert workspace.vat_registered is True
    assert workspace.vat_rate == Decimal("17.00")
    assert workspace.receipt_counter == 0


@pytest.mark.asyncio
async def test_workspace_payment_auto_send_settings(db_session: AsyncSession):
    """Test workspace auto-send payment settings."""
    workspace = Workspace(
        name="Test Clinic",
        payment_provider="payplus",
        payment_auto_send=True,
        payment_send_timing="end_of_day",
        storage_quota_bytes=10 * 1024 * 1024 * 1024,
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)

    # Verify auto-send settings
    assert workspace.payment_auto_send is True
    assert workspace.payment_send_timing == "end_of_day"


# ==============================================================================
# PaymentTransaction Model Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_payment_transaction_creation(
    db_session: AsyncSession, workspace_1: Workspace
):
    """Test creating a basic payment transaction."""
    transaction = PaymentTransaction(
        workspace_id=workspace_1.id,
        base_amount=Decimal("100.00"),
        vat_amount=Decimal("17.00"),
        total_amount=Decimal("117.00"),
        currency="ILS",
        payment_method="cash",
        status="completed",
    )
    db_session.add(transaction)
    await db_session.commit()
    await db_session.refresh(transaction)

    # Verify transaction created
    assert transaction.id is not None
    assert transaction.workspace_id == workspace_1.id
    assert transaction.base_amount == Decimal("100.00")
    assert transaction.vat_amount == Decimal("17.00")
    assert transaction.total_amount == Decimal("117.00")
    assert transaction.currency == "ILS"
    assert transaction.payment_method == "cash"
    assert transaction.status == "completed"
    assert transaction.created_at is not None


@pytest.mark.asyncio
async def test_payment_transaction_with_appointment(
    db_session: AsyncSession,
    workspace_1: Workspace,
    sample_client_ws1: Client,
):
    """Test payment transaction linked to appointment."""
    # Create appointment
    appointment = Appointment(
        workspace_id=workspace_1.id,
        client_id=sample_client_ws1.id,
        scheduled_start=datetime.now(UTC) + timedelta(days=1),
        scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,
        payment_price=Decimal("200.00"),
    )
    db_session.add(appointment)
    await db_session.commit()
    await db_session.refresh(appointment)

    # Create transaction for appointment
    transaction = PaymentTransaction(
        workspace_id=workspace_1.id,
        appointment_id=appointment.id,
        base_amount=Decimal("200.00"),
        vat_amount=Decimal("34.00"),
        total_amount=Decimal("234.00"),
        currency="ILS",
        payment_method="online_card",
        status="pending",
        provider="payplus",
        provider_transaction_id="PP-12345",
    )
    db_session.add(transaction)
    await db_session.commit()
    await db_session.refresh(transaction)

    # Verify relationship
    assert transaction.appointment_id == appointment.id
    assert transaction.appointment is not None
    assert transaction.appointment.id == appointment.id


@pytest.mark.asyncio
async def test_payment_transaction_default_values(
    db_session: AsyncSession, workspace_1: Workspace
):
    """Test payment transaction default values."""
    transaction = PaymentTransaction(
        workspace_id=workspace_1.id,
        base_amount=Decimal("100.00"),
        total_amount=Decimal("100.00"),  # No VAT
        payment_method="cash",
    )
    db_session.add(transaction)
    await db_session.commit()
    await db_session.refresh(transaction)

    # Verify defaults
    assert transaction.vat_amount == Decimal("0")  # Default VAT is 0
    assert transaction.currency == "ILS"  # Default currency
    assert transaction.status == "pending"  # Default status
    assert transaction.receipt_issued is False  # Default receipt not issued


@pytest.mark.asyncio
async def test_payment_transaction_helper_methods(
    db_session: AsyncSession, workspace_1: Workspace
):
    """Test is_completed, is_pending, is_failed properties."""
    # Completed transaction
    txn_completed = PaymentTransaction(
        workspace_id=workspace_1.id,
        base_amount=Decimal("100.00"),
        total_amount=Decimal("100.00"),
        payment_method="cash",
        status="completed",
        completed_at=datetime.now(UTC),
    )
    assert txn_completed.is_completed is True
    assert txn_completed.is_pending is False
    assert txn_completed.is_failed is False

    # Pending transaction
    txn_pending = PaymentTransaction(
        workspace_id=workspace_1.id,
        base_amount=Decimal("100.00"),
        total_amount=Decimal("100.00"),
        payment_method="online_card",
        status="pending",
    )
    assert txn_pending.is_completed is False
    assert txn_pending.is_pending is True
    assert txn_pending.is_failed is False

    # Failed transaction
    txn_failed = PaymentTransaction(
        workspace_id=workspace_1.id,
        base_amount=Decimal("100.00"),
        total_amount=Decimal("100.00"),
        payment_method="online_card",
        status="failed",
        failed_at=datetime.now(UTC),
        failure_reason="Card declined",
    )
    assert txn_failed.is_completed is False
    assert txn_failed.is_pending is False
    assert txn_failed.is_failed is True


@pytest.mark.asyncio
async def test_payment_transaction_receipt_details(
    db_session: AsyncSession, workspace_1: Workspace
):
    """Test payment transaction receipt details."""
    transaction = PaymentTransaction(
        workspace_id=workspace_1.id,
        base_amount=Decimal("100.00"),
        vat_amount=Decimal("17.00"),
        total_amount=Decimal("117.00"),
        payment_method="cash",
        status="completed",
        receipt_number="2025-000001",
        receipt_issued=True,
        receipt_issued_at=datetime.now(UTC),
        receipt_pdf_url="https://s3.example.com/receipts/2025-000001.pdf",
    )
    db_session.add(transaction)
    await db_session.commit()
    await db_session.refresh(transaction)

    # Verify receipt details
    assert transaction.receipt_number == "2025-000001"
    assert transaction.receipt_issued is True
    assert transaction.receipt_issued_at is not None
    assert (
        transaction.receipt_pdf_url == "https://s3.example.com/receipts/2025-000001.pdf"
    )


@pytest.mark.asyncio
async def test_payment_transaction_provider_metadata(
    db_session: AsyncSession, workspace_1: Workspace
):
    """Test payment transaction provider metadata JSONB field."""
    metadata = {
        "provider_response": {"transaction_id": "PP-12345", "status": "approved"},
        "card_last_4": "1234",
        "card_brand": "Visa",
    }

    transaction = PaymentTransaction(
        workspace_id=workspace_1.id,
        base_amount=Decimal("100.00"),
        total_amount=Decimal("100.00"),
        payment_method="online_card",
        status="completed",
        provider_metadata=metadata,
    )
    db_session.add(transaction)
    await db_session.commit()
    await db_session.refresh(transaction)

    # Verify metadata stored correctly
    assert transaction.provider_metadata is not None
    assert transaction.provider_metadata["card_last_4"] == "1234"
    assert transaction.provider_metadata["card_brand"] == "Visa"


@pytest.mark.asyncio
async def test_payment_transaction_workspace_relationship(
    db_session: AsyncSession, workspace_1: Workspace
):
    """Test payment transaction -> workspace relationship."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    # Create multiple transactions
    for _ in range(3):
        transaction = PaymentTransaction(
            workspace_id=workspace_1.id,
            base_amount=Decimal("100.00"),
            total_amount=Decimal("100.00"),
            payment_method="cash",
            status="completed",
        )
        db_session.add(transaction)
    await db_session.commit()

    # Query workspace with payment_transactions relationship loaded
    result = await db_session.execute(
        select(Workspace)
        .where(Workspace.id == workspace_1.id)
        .options(selectinload(Workspace.payment_transactions))
    )
    workspace_with_txns = result.scalar_one()

    # Verify relationship
    assert len(workspace_with_txns.payment_transactions) == 3
    for txn in workspace_with_txns.payment_transactions:
        assert txn.workspace_id == workspace_1.id


@pytest.mark.asyncio
async def test_payment_transaction_cascade_delete(
    db_session: AsyncSession, workspace_1: Workspace
):
    """Test that payment transactions are deleted when workspace is deleted."""
    # Create transaction
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

    # Delete workspace
    await db_session.delete(workspace_1)
    await db_session.commit()

    # Verify transaction deleted
    result = await db_session.execute(
        select(PaymentTransaction).where(PaymentTransaction.id == transaction_id)
    )
    deleted_txn = result.scalar_one_or_none()
    assert deleted_txn is None


@pytest.mark.asyncio
async def test_payment_transaction_indexes_exist(db_session: AsyncSession):
    """Test that payment transaction indexes exist in database."""
    # Expected indexes
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

    # Query PostgreSQL index catalog
    for index_name in expected_indexes:
        result = await db_session.execute(
            text(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = 'payment_transactions'
                  AND indexname = :index_name
                """
            ),
            {"index_name": index_name},
        )
        index_info = result.fetchone()

        # Verify index exists
        assert index_info is not None, f"Index {index_name} should exist"


# ==============================================================================
# PaymentFeatureChecker Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_payment_feature_checker_is_enabled(db_session: AsyncSession):
    """Test PaymentFeatureChecker.is_enabled() method."""
    # Disabled case - no provider
    workspace_disabled = Workspace(
        name="Disabled Clinic",
        payment_provider=None,
        storage_quota_bytes=10 * 1024 * 1024 * 1024,
    )
    assert PaymentFeatureChecker.is_enabled(workspace_disabled) is False

    # Enabled case - provider set
    workspace_enabled = Workspace(
        name="Enabled Clinic",
        payment_provider="payplus",
        storage_quota_bytes=10 * 1024 * 1024 * 1024,
    )
    assert PaymentFeatureChecker.is_enabled(workspace_enabled) is True


@pytest.mark.asyncio
async def test_payment_feature_checker_can_send_payment_request_success(
    db_session: AsyncSession,
):
    """Test successful case - all checks pass."""
    # Create workspace with payments enabled
    workspace = Workspace(
        name="Test Clinic",
        payment_provider="payplus",
        storage_quota_bytes=10 * 1024 * 1024 * 1024,
    )
    db_session.add(workspace)
    await db_session.commit()

    # Create client
    client = Client(
        workspace_id=workspace.id,
        first_name="John",
        last_name="Doe",
        email="john@example.com",
    )
    db_session.add(client)
    await db_session.commit()

    # Create completed appointment with price
    appointment = Appointment(
        workspace_id=workspace.id,
        client_id=client.id,
        scheduled_start=datetime.now(UTC),
        scheduled_end=datetime.now(UTC) + timedelta(hours=1),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.ATTENDED,  # Completed
        payment_price=Decimal("150.00"),  # Price set
        payment_status="unpaid",  # Not paid yet
    )
    appointment.workspace = workspace  # Ensure relationship loaded
    db_session.add(appointment)
    await db_session.commit()
    await db_session.refresh(appointment)

    # Test
    can_send, reason = PaymentFeatureChecker.can_send_payment_request(appointment)

    # Verify
    assert can_send is True
    assert reason == "Can send payment request"


@pytest.mark.asyncio
async def test_payment_feature_checker_payments_not_enabled(db_session: AsyncSession):
    """Test failure case - payments not enabled for workspace."""
    # Create workspace without payment provider
    workspace = Workspace(
        name="Test Clinic",
        payment_provider=None,  # Payments disabled
        storage_quota_bytes=10 * 1024 * 1024 * 1024,
    )
    db_session.add(workspace)
    await db_session.commit()

    # Create client
    client = Client(
        workspace_id=workspace.id,
        first_name="John",
        last_name="Doe",
        email="john@example.com",
    )
    db_session.add(client)
    await db_session.commit()

    # Create appointment
    appointment = Appointment(
        workspace_id=workspace.id,
        client_id=client.id,
        scheduled_start=datetime.now(UTC),
        scheduled_end=datetime.now(UTC) + timedelta(hours=1),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.ATTENDED,
        payment_price=Decimal("150.00"),
        payment_status="unpaid",
    )
    appointment.workspace = workspace
    db_session.add(appointment)
    await db_session.commit()

    # Test
    can_send, reason = PaymentFeatureChecker.can_send_payment_request(appointment)

    # Verify
    assert can_send is False
    assert reason == "Payments not enabled for workspace"


@pytest.mark.asyncio
async def test_payment_feature_checker_no_price_set(db_session: AsyncSession):
    """Test failure case - no price set for appointment."""
    workspace = Workspace(
        name="Test Clinic",
        payment_provider="payplus",
        storage_quota_bytes=10 * 1024 * 1024 * 1024,
    )
    db_session.add(workspace)
    await db_session.commit()

    client = Client(
        workspace_id=workspace.id,
        first_name="John",
        last_name="Doe",
        email="john@example.com",
    )
    db_session.add(client)
    await db_session.commit()

    appointment = Appointment(
        workspace_id=workspace.id,
        client_id=client.id,
        scheduled_start=datetime.now(UTC),
        scheduled_end=datetime.now(UTC) + timedelta(hours=1),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.ATTENDED,
        payment_price=None,  # No price set
        payment_status="unpaid",
    )
    appointment.workspace = workspace
    db_session.add(appointment)
    await db_session.commit()

    # Test
    can_send, reason = PaymentFeatureChecker.can_send_payment_request(appointment)

    # Verify
    assert can_send is False
    assert reason == "No price set for appointment"


@pytest.mark.asyncio
async def test_payment_feature_checker_appointment_not_completed(
    db_session: AsyncSession,
):
    """Test failure case - appointment not completed yet."""
    workspace = Workspace(
        name="Test Clinic",
        payment_provider="payplus",
        storage_quota_bytes=10 * 1024 * 1024 * 1024,
    )
    db_session.add(workspace)
    await db_session.commit()

    client = Client(
        workspace_id=workspace.id,
        first_name="John",
        last_name="Doe",
        email="john@example.com",
    )
    db_session.add(client)
    await db_session.commit()

    appointment = Appointment(
        workspace_id=workspace.id,
        client_id=client.id,
        scheduled_start=datetime.now(UTC) + timedelta(days=1),
        scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.SCHEDULED,  # Not completed
        payment_price=Decimal("150.00"),
        payment_status="unpaid",
    )
    appointment.workspace = workspace
    db_session.add(appointment)
    await db_session.commit()

    # Test
    can_send, reason = PaymentFeatureChecker.can_send_payment_request(appointment)

    # Verify
    assert can_send is False
    assert reason == "Appointment not completed yet"


@pytest.mark.asyncio
async def test_payment_feature_checker_already_paid(db_session: AsyncSession):
    """Test failure case - payment already completed."""
    workspace = Workspace(
        name="Test Clinic",
        payment_provider="payplus",
        storage_quota_bytes=10 * 1024 * 1024 * 1024,
    )
    db_session.add(workspace)
    await db_session.commit()

    client = Client(
        workspace_id=workspace.id,
        first_name="John",
        last_name="Doe",
        email="john@example.com",
    )
    db_session.add(client)
    await db_session.commit()

    appointment = Appointment(
        workspace_id=workspace.id,
        client_id=client.id,
        scheduled_start=datetime.now(UTC),
        scheduled_end=datetime.now(UTC) + timedelta(hours=1),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.ATTENDED,
        payment_price=Decimal("150.00"),
        payment_status="paid",  # Already paid
    )
    appointment.workspace = workspace
    db_session.add(appointment)
    await db_session.commit()

    # Test
    can_send, reason = PaymentFeatureChecker.can_send_payment_request(appointment)

    # Verify
    assert can_send is False
    assert reason == "Already paid"


@pytest.mark.asyncio
async def test_payment_feature_checker_already_pending(db_session: AsyncSession):
    """Test failure case - payment request already sent."""
    workspace = Workspace(
        name="Test Clinic",
        payment_provider="payplus",
        storage_quota_bytes=10 * 1024 * 1024 * 1024,
    )
    db_session.add(workspace)
    await db_session.commit()

    client = Client(
        workspace_id=workspace.id,
        first_name="John",
        last_name="Doe",
        email="john@example.com",
    )
    db_session.add(client)
    await db_session.commit()

    appointment = Appointment(
        workspace_id=workspace.id,
        client_id=client.id,
        scheduled_start=datetime.now(UTC),
        scheduled_end=datetime.now(UTC) + timedelta(hours=1),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.ATTENDED,
        payment_price=Decimal("150.00"),
        payment_status="pending",  # Already pending
    )
    appointment.workspace = workspace
    db_session.add(appointment)
    await db_session.commit()

    # Test
    can_send, reason = PaymentFeatureChecker.can_send_payment_request(appointment)

    # Verify
    assert can_send is False
    assert reason == "Payment request already sent"
