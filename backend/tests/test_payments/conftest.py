"""Fixtures for payment integration tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.appointment import Appointment, AppointmentStatus, LocationType
from pazpaz.models.client import Client
from pazpaz.models.payment_transaction import PaymentTransaction
from pazpaz.models.workspace import Workspace


@pytest_asyncio.fixture
async def test_workspace_with_payments(db_session: AsyncSession) -> Workspace:
    """
    Create test workspace with payments enabled and PayPlus configured.

    This workspace has:
    - payments_enabled = True
    - payment_provider = "payplus"
    - payment_provider_config with test credentials (unencrypted for tests)
    - VAT registered with 17% rate

    Returns:
        Workspace with payments enabled
    """
    # Create PayPlus config with test credentials (plain dict for tests)
    config = {
        "api_key": "test_api_key",
        "payment_page_uid": "test_page_uid",
        "webhook_secret": "test_secret",
    }

    workspace = Workspace(
        id=uuid.uuid4(),
        name="Test Payment Workspace",
        payment_provider="payplus",  # Setting this makes payments_enabled=True
        payment_provider_config=config,  # Plain dict for tests
        vat_registered=True,
        vat_rate=Decimal("17.00"),
        business_name="Test Clinic",
        payment_auto_send=True,
        payment_send_timing="immediately",
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


@pytest_asyncio.fixture
async def workspace_payments_disabled(db_session: AsyncSession) -> Workspace:
    """
    Create test workspace with payments disabled.

    Returns:
        Workspace with payments_enabled = False
    """
    workspace = Workspace(
        id=uuid.uuid4(),
        name="Test Workspace (Payments Disabled)",
        payment_provider=None,  # Setting to None makes payments_enabled=False
        vat_registered=False,
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


@pytest_asyncio.fixture
async def test_client_entity(
    db_session: AsyncSession, test_workspace_with_payments: Workspace
) -> Client:
    """
    Create test client for payment tests.

    Returns:
        Client with email for payment requests
    """
    client = Client(
        id=uuid.uuid4(),
        workspace_id=test_workspace_with_payments.id,
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        phone="+1234567890",
        consent_status=True,
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest_asyncio.fixture
async def test_appointment_with_price(
    db_session: AsyncSession,
    test_workspace_with_payments: Workspace,
    test_client_entity: Client,
) -> Appointment:
    """
    Create test appointment with payment price set.

    Returns:
        Appointment with payment_price = 100.00 and status = unpaid
    """
    appointment = Appointment(
        id=uuid.uuid4(),
        workspace_id=test_workspace_with_payments.id,
        client_id=test_client_entity.id,
        scheduled_start=datetime.now(UTC) + timedelta(days=1),
        scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
        location_type=LocationType.CLINIC,
        location_details="Room 101",
        status=AppointmentStatus.ATTENDED,
        payment_price=Decimal("100.00"),
        payment_status="unpaid",
    )
    db_session.add(appointment)
    await db_session.commit()
    await db_session.refresh(appointment)
    return appointment


@pytest_asyncio.fixture
async def test_appointment_no_price(
    db_session: AsyncSession,
    test_workspace_with_payments: Workspace,
    test_client_entity: Client,
) -> Appointment:
    """
    Create test appointment without payment price.

    Returns:
        Appointment with payment_price = None
    """
    appointment = Appointment(
        id=uuid.uuid4(),
        workspace_id=test_workspace_with_payments.id,
        client_id=test_client_entity.id,
        scheduled_start=datetime.now(UTC) + timedelta(days=1),
        scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.ATTENDED,
        payment_price=None,  # No price set
        payment_status="unpaid",
    )
    db_session.add(appointment)
    await db_session.commit()
    await db_session.refresh(appointment)
    return appointment


@pytest_asyncio.fixture
async def existing_payment_transaction(
    db_session: AsyncSession,
    test_workspace_with_payments: Workspace,
    test_appointment_with_price: Appointment,
) -> PaymentTransaction:
    """
    Create existing payment transaction for idempotency tests.

    Returns:
        PaymentTransaction with status = pending
    """
    transaction = PaymentTransaction(
        id=uuid.uuid4(),
        workspace_id=test_workspace_with_payments.id,
        appointment_id=test_appointment_with_price.id,
        base_amount=Decimal("85.47"),
        vat_amount=Decimal("14.53"),
        total_amount=Decimal("100.00"),
        currency="ILS",
        payment_method="online_card",
        status="pending",
        provider="payplus",
        provider_transaction_id="pp_idempotency_test",
        provider_payment_link="https://payplus.co.il/pay/test123",
    )
    db_session.add(transaction)
    await db_session.commit()
    await db_session.refresh(transaction)
    return transaction


@pytest_asyncio.fixture
async def workspace_a(db_session: AsyncSession) -> Workspace:
    """
    Create workspace A for workspace isolation tests.

    Returns:
        Workspace with payments enabled
    """
    config = {
        "api_key": "workspace_a_api_key",
        "payment_page_uid": "workspace_a_page_uid",
        "webhook_secret": "workspace_a_secret",
    }

    workspace = Workspace(
        id=uuid.uuid4(),
        name="Workspace A",
        payment_provider="payplus",
        payment_provider_config=config,
        vat_registered=True,
        vat_rate=Decimal("17.00"),
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


@pytest_asyncio.fixture
async def workspace_b(db_session: AsyncSession) -> Workspace:
    """
    Create workspace B for workspace isolation tests.

    Returns:
        Workspace with payments enabled
    """
    config = {
        "api_key": "workspace_b_api_key",
        "payment_page_uid": "workspace_b_page_uid",
        "webhook_secret": "workspace_b_secret",
    }

    workspace = Workspace(
        id=uuid.uuid4(),
        name="Workspace B",
        payment_provider="payplus",
        payment_provider_config=config,
        vat_registered=True,
        vat_rate=Decimal("17.00"),
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


@pytest_asyncio.fixture
async def client_workspace_a(
    db_session: AsyncSession, workspace_a: Workspace
) -> Client:
    """Create client in workspace A."""
    client = Client(
        id=uuid.uuid4(),
        workspace_id=workspace_a.id,
        first_name="Alice",
        last_name="WorkspaceA",
        email="alice@workspacea.com",
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest_asyncio.fixture
async def client_workspace_b(
    db_session: AsyncSession, workspace_b: Workspace
) -> Client:
    """Create client in workspace B."""
    client = Client(
        id=uuid.uuid4(),
        workspace_id=workspace_b.id,
        first_name="Bob",
        last_name="WorkspaceB",
        email="bob@workspaceb.com",
    )
    db_session.add(client)
    await db_session.commit()
    await db_session.refresh(client)
    return client


@pytest_asyncio.fixture
async def appointment_workspace_a(
    db_session: AsyncSession,
    workspace_a: Workspace,
    client_workspace_a: Client,
) -> Appointment:
    """Create appointment in workspace A with price."""
    appointment = Appointment(
        id=uuid.uuid4(),
        workspace_id=workspace_a.id,
        client_id=client_workspace_a.id,
        scheduled_start=datetime.now(UTC) + timedelta(days=1),
        scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.ATTENDED,
        payment_price=Decimal("200.00"),
        payment_status="unpaid",
    )
    db_session.add(appointment)
    await db_session.commit()
    await db_session.refresh(appointment)
    return appointment


@pytest_asyncio.fixture
async def appointment_workspace_b(
    db_session: AsyncSession,
    workspace_b: Workspace,
    client_workspace_b: Client,
) -> Appointment:
    """Create appointment in workspace B with price."""
    appointment = Appointment(
        id=uuid.uuid4(),
        workspace_id=workspace_b.id,
        client_id=client_workspace_b.id,
        scheduled_start=datetime.now(UTC) + timedelta(days=1),
        scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
        location_type=LocationType.CLINIC,
        status=AppointmentStatus.ATTENDED,
        payment_price=Decimal("300.00"),
        payment_status="unpaid",
    )
    db_session.add(appointment)
    await db_session.commit()
    await db_session.refresh(appointment)
    return appointment
