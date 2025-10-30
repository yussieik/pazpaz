"""Unit tests for payment API endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
import respx
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.appointment import Appointment, AppointmentStatus, LocationType
from pazpaz.models.client import Client
from pazpaz.models.payment_transaction import PaymentTransaction
from pazpaz.models.user import User
from pazpaz.models.workspace import Workspace
from tests.conftest import add_csrf_to_client, get_auth_headers

pytestmark = pytest.mark.asyncio


class TestCreatePaymentRequest:
    """Test POST /api/v1/payments/create-request endpoint."""

    async def test_create_payment_request_success(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Test successful payment request creation."""
        # Setup workspace with payment provider
        workspace_1.payment_provider = "payplus"
        workspace_1.payment_provider_config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
        }
        workspace_1.vat_registered = True
        workspace_1.vat_rate = Decimal("17.00")

        test_client = Client(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            first_name="John",
            last_name="Doe",
            email="john@example.com",
        )

        appointment = Appointment(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            client_id=test_client.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=1),
            scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
            payment_price=Decimal("117.00"),
            payment_status="unpaid",
        )

        db_session.add_all([workspace_1, test_client, appointment])
        await db_session.commit()
        await db_session.refresh(workspace_1)
        await db_session.refresh(appointment)

        # Authenticate
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Mock payment provider
        with patch(
            "pazpaz.api.payments.PaymentService.create_payment_request"
        ) as mock_create:
            mock_transaction = PaymentTransaction(
                id=uuid.uuid4(),
                workspace_id=workspace_1.id,
                appointment_id=appointment.id,
                base_amount=Decimal("100.00"),
                vat_amount=Decimal("17.00"),
                total_amount=Decimal("117.00"),
                currency="ILS",
                payment_method="online_card",
                status="pending",
                provider="payplus",
                provider_transaction_id="pp_tx_test123",
                provider_payment_link="https://payplus.co.il/pay/test123",
                created_at=datetime.now(UTC),
            )
            mock_create.return_value = mock_transaction

            # Request
            response = await client.post(
                "/api/v1/payments/create-request",
                json={
                    "appointment_id": str(appointment.id),
                    "customer_email": "john@example.com",
                },
                headers=headers,
            )

            # Verify
            assert response.status_code == 200
            data = response.json()

            assert data["appointment_id"] == str(appointment.id)
            assert data["total_amount"] == "117.00"
            assert data["currency"] == "ILS"
            assert data["status"] == "pending"
            assert data["provider"] == "payplus"
            assert data["payment_link"] == "https://payplus.co.il/pay/test123"

    async def test_create_payment_request_no_price(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Test payment request fails when appointment has no price."""
        # Setup workspace
        workspace_1.payment_provider = "payplus"
        workspace_1.payment_provider_config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
        }

        test_client = Client(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            first_name="Test",
            last_name="Client",
        )

        appointment = Appointment(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            client_id=test_client.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=1),
            scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
            payment_price=None,  # No price set
        )

        db_session.add_all([workspace_1, test_client, appointment])
        await db_session.commit()

        # Authenticate
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Request
        response = await client.post(
            "/api/v1/payments/create-request",
            json={
                "appointment_id": str(appointment.id),
                "customer_email": "test@example.com",
            },
            headers=headers,
        )

        # Verify 400 Bad Request
        assert response.status_code == 400
        assert "price" in response.json()["detail"].lower()

    async def test_create_payment_request_requires_authentication(
        self,
        client: AsyncClient,
    ):
        """Test that endpoint requires authentication."""
        # Request without authentication
        response = await client.post(
            "/api/v1/payments/create-request",
            json={
                "appointment_id": str(uuid.uuid4()),
                "customer_email": "test@example.com",
            },
        )

        # Verify 403 Forbidden (CSRF protection blocks unauthenticated requests)
        assert response.status_code == 403

    async def test_create_payment_request_appointment_not_found(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """Test payment request fails when appointment doesn't exist."""
        # Authenticate
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Request with non-existent appointment
        response = await client.post(
            "/api/v1/payments/create-request",
            json={
                "appointment_id": str(uuid.uuid4()),
                "customer_email": "test@example.com",
            },
            headers=headers,
        )

        # Verify 404 Not Found
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_create_payment_request_payments_not_enabled(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Test payment request fails when payments not enabled."""
        # Ensure payments are disabled
        workspace_1.payment_provider = None

        test_client = Client(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            first_name="Test",
            last_name="Client",
        )

        appointment = Appointment(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            client_id=test_client.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=1),
            scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
            payment_price=Decimal("100.00"),
        )

        db_session.add_all([workspace_1, test_client, appointment])
        await db_session.commit()

        # Authenticate
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Request
        response = await client.post(
            "/api/v1/payments/create-request",
            json={
                "appointment_id": str(appointment.id),
                "customer_email": "test@example.com",
            },
            headers=headers,
        )

        # Verify 400 Bad Request
        assert response.status_code == 400
        assert "not enabled" in response.json()["detail"].lower()


class TestProcessPaymentWebhook:
    """Test POST /api/v1/payments/webhook/{provider} endpoint."""

    async def test_process_webhook_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        redis_client,
    ):
        """Test successful webhook processing."""
        # Setup workspace
        workspace = Workspace(
            id=uuid.uuid4(),
            name="Test Workspace",
            payment_provider="payplus",
            payment_provider_config={
                "api_key": "test_key",
                "payment_page_uid": "page_uid",
                "webhook_secret": "secret",
            },
        )

        test_client = Client(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            first_name="Test",
            last_name="Client",
        )

        appointment = Appointment(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            client_id=test_client.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=1),
            scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
            payment_status="pending",
        )

        transaction = PaymentTransaction(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            appointment_id=appointment.id,
            base_amount=Decimal("100.00"),
            vat_amount=Decimal("0.00"),
            total_amount=Decimal("100.00"),
            currency="ILS",
            payment_method="online_card",
            status="pending",
            provider="payplus",
            provider_transaction_id="pp_webhook_test",
        )

        db_session.add_all([workspace, test_client, appointment, transaction])
        await db_session.commit()

        # Webhook payload
        payload = f'{{"page_request_uid": "pp_webhook_test", "status": "completed", "custom_fields": {{"workspace_id": "{workspace.id}"}}}}'

        # Mock payment service
        with patch(
            "pazpaz.api.payments.PaymentService.process_webhook"
        ) as mock_process:
            transaction.status = "completed"
            transaction.completed_at = datetime.now(UTC)
            mock_process.return_value = transaction

            # Request (NO AUTHENTICATION for webhooks)
            response = await client.post(
                "/api/v1/payments/webhook/payplus",
                content=payload,
                headers={"X-PayPlus-Signature": "sha256=test"},
            )

            # Verify always returns 200
            assert response.status_code == 200
            assert response.json()["status"] == "ok"

    async def test_process_webhook_always_returns_200(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """Test webhook always returns 200 even on errors."""
        # Webhook with invalid JSON
        response = await client.post(
            "/api/v1/payments/webhook/payplus",
            content="invalid json {{}",
            headers={"X-PayPlus-Signature": "sha256=test"},
        )

        # Verify always returns 200 to prevent retries
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_process_webhook_missing_workspace_id(
        self,
        client: AsyncClient,
    ):
        """Test webhook returns 200 when workspace_id is missing."""
        # Webhook without workspace_id in metadata
        payload = '{"page_request_uid": "pp_test", "status": "completed"}'

        response = await client.post(
            "/api/v1/payments/webhook/payplus",
            content=payload,
            headers={"X-PayPlus-Signature": "sha256=test"},
        )

        # Verify returns 200 (logs error but doesn't fail)
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestGetPaymentTransactions:
    """Test GET /api/v1/payments/transactions endpoint."""

    async def test_get_transactions_success(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Test successful retrieval of payment transactions."""
        # Setup appointment
        test_client = Client(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            first_name="Test",
            last_name="Client",
        )

        appointment = Appointment(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            client_id=test_client.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=1),
            scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
        )

        # Create transactions
        tx1 = PaymentTransaction(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            appointment_id=appointment.id,
            base_amount=Decimal("100.00"),
            vat_amount=Decimal("0.00"),
            total_amount=Decimal("100.00"),
            currency="ILS",
            payment_method="online_card",
            status="completed",
            provider="payplus",
            provider_transaction_id="pp_tx1",
            created_at=datetime.now(UTC) - timedelta(hours=1),
        )

        tx2 = PaymentTransaction(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            appointment_id=appointment.id,
            base_amount=Decimal("100.00"),
            vat_amount=Decimal("0.00"),
            total_amount=Decimal("100.00"),
            currency="ILS",
            payment_method="online_card",
            status="pending",
            provider="payplus",
            provider_transaction_id="pp_tx2",
            created_at=datetime.now(UTC),
        )

        db_session.add_all([test_client, appointment, tx1, tx2])
        await db_session.commit()

        # Authenticate
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)

        # Request
        response = await client.get(
            f"/api/v1/payments/transactions?appointment_id={appointment.id}",
            headers=headers,
        )

        # Verify
        assert response.status_code == 200
        data = response.json()

        assert "transactions" in data
        assert len(data["transactions"]) == 2

        # Verify order (most recent first)
        assert data["transactions"][0]["id"] == str(tx2.id)
        assert data["transactions"][1]["id"] == str(tx1.id)

    async def test_get_transactions_workspace_isolation(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        workspace_2: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Test workspace isolation for transactions."""
        # Create appointment and transaction in workspace 1
        test_client1 = Client(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            first_name="Client",
            last_name="One",
        )
        appointment1 = Appointment(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            client_id=test_client1.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=1),
            scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
        )
        tx1 = PaymentTransaction(
            id=uuid.uuid4(),
            workspace_id=workspace_1.id,
            appointment_id=appointment1.id,
            base_amount=Decimal("100.00"),
            vat_amount=Decimal("0.00"),
            total_amount=Decimal("100.00"),
            currency="ILS",
            payment_method="online_card",
            status="completed",
            provider="payplus",
        )

        # Create appointment and transaction in workspace 2
        test_client2 = Client(
            id=uuid.uuid4(),
            workspace_id=workspace_2.id,
            first_name="Client",
            last_name="Two",
        )
        appointment2 = Appointment(
            id=uuid.uuid4(),
            workspace_id=workspace_2.id,
            client_id=test_client2.id,
            scheduled_start=datetime.now(UTC) + timedelta(days=1),
            scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
        )
        tx2 = PaymentTransaction(
            id=uuid.uuid4(),
            workspace_id=workspace_2.id,
            appointment_id=appointment2.id,
            base_amount=Decimal("200.00"),
            vat_amount=Decimal("0.00"),
            total_amount=Decimal("200.00"),
            currency="ILS",
            payment_method="online_card",
            status="completed",
            provider="payplus",
        )

        db_session.add_all(
            [test_client1, appointment1, tx1, test_client2, appointment2, tx2]
        )
        await db_session.commit()

        # Authenticate as workspace 1 user
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)

        # Request transactions for appointment in workspace 1
        response = await client.get(
            f"/api/v1/payments/transactions?appointment_id={appointment1.id}",
            headers=headers,
        )

        # Verify only sees workspace 1 transactions
        assert response.status_code == 200
        data = response.json()
        assert len(data["transactions"]) == 1
        assert data["transactions"][0]["id"] == str(tx1.id)

    async def test_get_transactions_requires_authentication(
        self,
        client: AsyncClient,
    ):
        """Test that endpoint requires authentication."""
        # Request without authentication
        response = await client.get(
            f"/api/v1/payments/transactions?appointment_id={uuid.uuid4()}"
        )

        # Verify 401 Unauthorized
        assert response.status_code == 401


class TestTestPaymentCredentials:
    """Test POST /api/v1/payments/test-credentials endpoint."""

    @respx.mock
    async def test_test_credentials_success(
        self,
        client: AsyncClient,
    ):
        """Test successful credentials validation."""
        # Mock successful PayPlus API response
        mock_response = {
            "success": True,
            "data": {
                "payment_page_link": "https://payplus.co.il/pay/test",
                "page_request_uid": "pp_test",
            },
        }

        respx.post(
            "https://restapi.payplus.co.il/api/v1.0/PaymentPages/generateLink"
        ).mock(return_value=Response(200, json=mock_response))

        # Request (NO AUTHENTICATION REQUIRED)
        response = await client.post(
            "/api/v1/payments/test-credentials",
            json={
                "api_key": "test_key_123",
                "payment_page_uid": "page_uid_456",
                "webhook_secret": "secret_789",
            },
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "valid" in data["message"].lower()

    @respx.mock
    async def test_test_credentials_invalid(
        self,
        client: AsyncClient,
    ):
        """Test invalid credentials validation."""
        # Mock 401 Unauthorized response
        respx.post(
            "https://restapi.payplus.co.il/api/v1.0/PaymentPages/generateLink"
        ).mock(return_value=Response(401, text="Unauthorized"))

        # Request
        response = await client.post(
            "/api/v1/payments/test-credentials",
            json={
                "api_key": "invalid_key",
                "payment_page_uid": "page_uid",
                "webhook_secret": "secret",
            },
        )

        # Verify
        assert response.status_code == 200  # Always returns 200
        data = response.json()
        assert data["success"] is False
        assert "invalid" in data["message"].lower()

    @respx.mock
    async def test_test_credentials_api_error(
        self,
        client: AsyncClient,
    ):
        """Test credentials validation with API error."""
        # Mock 500 Internal Server Error
        respx.post(
            "https://restapi.payplus.co.il/api/v1.0/PaymentPages/generateLink"
        ).mock(return_value=Response(500, text="Internal Server Error"))

        # Request
        response = await client.post(
            "/api/v1/payments/test-credentials",
            json={
                "api_key": "test_key",
                "payment_page_uid": "page_uid",
                "webhook_secret": "secret",
            },
        )

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "unable to connect" in data["message"].lower()
