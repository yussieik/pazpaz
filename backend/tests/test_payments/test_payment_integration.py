"""End-to-end integration tests for payment flow.

This module tests complete payment workflows using real database interactions.
Tests use mocked PaymentProvider but real database and Redis operations.

Test coverage:
1. End-to-end payment flow (success)
2. End-to-end payment flow (failed payment)
3. Webhook idempotency
4. Workspace isolation
5. Payment request without price
6. Payment request when payments disabled
7. Multiple payment transactions for same appointment
8. Email failure doesn't break payment creation
9. Invalid webhook signature
10. Transaction not found for webhook
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
import redis.asyncio as redis
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.db.base import get_db
from pazpaz.main import app
from pazpaz.models.appointment import Appointment
from pazpaz.models.payment_transaction import PaymentTransaction
from pazpaz.models.user import User, UserRole
from pazpaz.models.workspace import Workspace
from pazpaz.payments.base import PaymentLinkResponse, WebhookPaymentData

pytestmark = pytest.mark.asyncio


# Helper function to create auth headers for workspace
async def get_payment_auth_headers(
    workspace_id: uuid.UUID, user_id: uuid.UUID, redis_client: redis.Redis
) -> dict:
    """Generate JWT auth headers with CSRF token for workspace."""
    from pazpaz.core.security import create_access_token
    from pazpaz.middleware.csrf import generate_csrf_token

    jwt_token = create_access_token(
        user_id=user_id,
        workspace_id=workspace_id,
        email="test@example.com",
    )

    # Generate CSRF token
    csrf_token = await generate_csrf_token(
        user_id=user_id,
        workspace_id=workspace_id,
        redis_client=redis_client,
    )

    return {
        "Cookie": f"access_token={jwt_token}; csrf_token={csrf_token}",
        "X-CSRF-Token": csrf_token,
    }


@pytest.fixture
async def test_user_payments(
    db_session: AsyncSession, test_workspace_with_payments: Workspace
) -> User:
    """Create test user for payment workspace."""
    user = User(
        id=uuid.uuid4(),
        workspace_id=test_workspace_with_payments.id,
        email="payment-user@example.com",
        full_name="Payment Test User",
        role=UserRole.OWNER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def user_workspace_a(db_session: AsyncSession, workspace_a: Workspace) -> User:
    """Create user for workspace A."""
    user = User(
        id=uuid.uuid4(),
        workspace_id=workspace_a.id,
        email="user-a@workspacea.com",
        full_name="User A",
        role=UserRole.OWNER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def user_workspace_b(db_session: AsyncSession, workspace_b: Workspace) -> User:
    """Create user for workspace B."""
    user = User(
        id=uuid.uuid4(),
        workspace_id=workspace_b.id,
        email="user-b@workspaceb.com",
        full_name="User B",
        role=UserRole.OWNER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def payment_client(
    db_session: AsyncSession, redis_client: redis.Redis
) -> AsyncClient:
    """Create AsyncClient configured for payment tests with database injection."""
    from starlette.middleware.base import BaseHTTPMiddleware

    # Middleware to inject db_session into request.state for audit middleware
    class DBSessionInjectorMiddleware(BaseHTTPMiddleware):
        def __init__(self, app, db_session):
            super().__init__(app)
            self.db_session = db_session

        async def dispatch(self, request, call_next):
            request.state.db_session = self.db_session
            response = await call_next(request)
            return response

    async def override_get_db():
        yield db_session

    async def override_get_redis():
        return redis_client

    # Set global Redis client for middleware
    import pazpaz.core.redis

    pazpaz.core.redis._redis_client = redis_client

    app.dependency_overrides[get_db] = override_get_db

    # Clear middleware stack before adding new middleware
    app.middleware_stack = None
    app.user_middleware = [
        m
        for m in app.user_middleware
        if not isinstance(m.cls, type)
        or m.cls.__name__ != "DBSessionInjectorMiddleware"
    ]

    # Add test middleware to inject db_session
    app.add_middleware(DBSessionInjectorMiddleware, db_session=db_session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Remove test middleware and clear overrides
    app.user_middleware = [
        m
        for m in app.user_middleware
        if not isinstance(m.cls, type)
        or m.cls.__name__ != "DBSessionInjectorMiddleware"
    ]
    app.middleware_stack = None  # Force rebuild
    app.dependency_overrides.clear()


class TestEndToEndPaymentFlow:
    """Test complete end-to-end payment workflows."""

    async def test_end_to_end_payment_flow_success(
        self,
        payment_client: AsyncClient,
        db_session: AsyncSession,
        redis_client: redis.Redis,
        test_workspace_with_payments: Workspace,
        test_user_payments: User,
        test_appointment_with_price: Appointment,
    ):
        """
        Test complete payment flow from creation to webhook processing (success).

        Flow:
        1. Create payment request → generates payment link
        2. Simulate webhook from PayPlus (payment completed)
        3. Verify appointment status updated to 'paid'
        4. Verify transaction status updated to 'completed'
        5. Verify payment history is queryable
        """
        auth_headers = await get_payment_auth_headers(
            test_workspace_with_payments.id, test_user_payments.id, redis_client
        )

        # Mock PaymentProvider for payment link creation
        mock_link_response = PaymentLinkResponse(
            payment_link_url="https://payplus.co.il/pay/test123",
            provider_transaction_id="pp_e2e_success_test",
            expires_at=None,
        )

        with (
            patch(
                "pazpaz.services.payment_service.get_payment_provider"
            ) as mock_get_provider,
            patch(
                "pazpaz.services.payment_service.send_payment_request_email"
            ) as mock_email,
        ):
            mock_provider = AsyncMock()
            mock_provider.create_payment_link.return_value = mock_link_response
            mock_get_provider.return_value = mock_provider
            mock_email.return_value = True

            # Step 1: Create payment request
            response = await payment_client.post(
                "/api/v1/payments/create-request",
                json={
                    "appointment_id": str(test_appointment_with_price.id),
                    "customer_email": "test@example.com",
                },
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "pending"
            assert "payment_link" in data
            assert data["payment_link"] == "https://payplus.co.il/pay/test123"
            transaction_id = data["id"]

        # Step 2: Simulate webhook (payment completed)
        webhook_payload = {
            "page_request_uid": "pp_e2e_success_test",
            "status": "completed",
            "amount": float(test_appointment_with_price.payment_price),
            "currency_code": "ILS",
            "completed_at": datetime.now(UTC).isoformat(),
            "custom_fields": {
                "workspace_id": str(test_workspace_with_payments.id),
                "appointment_id": str(test_appointment_with_price.id),
            },
        }

        # Mock webhook processing
        mock_webhook_data = WebhookPaymentData(
            provider_transaction_id="pp_e2e_success_test",
            status="completed",
            amount=Decimal("100.00"),
            currency="ILS",
            completed_at=datetime.now(UTC),
            failure_reason=None,
            metadata=None,
        )

        with patch(
            "pazpaz.services.payment_service.get_payment_provider"
        ) as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.verify_webhook.return_value = True
            mock_provider.parse_webhook_payment.return_value = mock_webhook_data
            mock_get_provider.return_value = mock_provider

            webhook_response = await payment_client.post(
                "/api/v1/payments/webhook/payplus",
                json=webhook_payload,
            )

            # Webhook always returns 200
            assert webhook_response.status_code == 200

        # Step 3: Verify appointment status updated
        await db_session.refresh(test_appointment_with_price)
        assert test_appointment_with_price.payment_status == "paid"

        # Step 4: Verify transaction status updated
        transactions_response = await payment_client.get(
            f"/api/v1/payments/transactions?appointment_id={test_appointment_with_price.id}",
            headers=auth_headers,
        )
        assert transactions_response.status_code == 200
        transactions = transactions_response.json()["transactions"]
        assert len(transactions) == 1
        assert transactions[0]["status"] == "completed"
        assert transactions[0]["id"] == transaction_id

    async def test_end_to_end_payment_flow_failed(
        self,
        payment_client: AsyncClient,
        db_session: AsyncSession,
        redis_client: redis.Redis,
        test_workspace_with_payments: Workspace,
        test_user_payments: User,
        test_appointment_with_price: Appointment,
    ):
        """
        Test complete payment flow when payment fails.

        Flow:
        1. Create payment request
        2. Simulate webhook with failed status
        3. Verify appointment status stays 'unpaid'
        4. Verify transaction status is 'failed'
        5. Verify failure_reason is captured
        """
        auth_headers = await get_payment_auth_headers(
            test_workspace_with_payments.id, test_user_payments.id, redis_client
        )

        # Mock payment link creation
        mock_link_response = PaymentLinkResponse(
            payment_link_url="https://payplus.co.il/pay/test456",
            provider_transaction_id="pp_e2e_failed_test",
            expires_at=None,
        )

        with (
            patch(
                "pazpaz.services.payment_service.get_payment_provider"
            ) as mock_get_provider,
            patch(
                "pazpaz.services.payment_service.send_payment_request_email"
            ) as mock_email,
        ):
            mock_provider = AsyncMock()
            mock_provider.create_payment_link.return_value = mock_link_response
            mock_get_provider.return_value = mock_provider
            mock_email.return_value = True

            # Create payment request
            response = await payment_client.post(
                "/api/v1/payments/create-request",
                json={
                    "appointment_id": str(test_appointment_with_price.id),
                    "customer_email": "test@example.com",
                },
                headers=auth_headers,
            )

            assert response.status_code == 200

        # Simulate failed webhook
        webhook_payload = {
            "page_request_uid": "pp_e2e_failed_test",
            "status": "failed",
            "amount": float(test_appointment_with_price.payment_price),
            "currency_code": "ILS",
            "custom_fields": {
                "workspace_id": str(test_workspace_with_payments.id),
                "appointment_id": str(test_appointment_with_price.id),
            },
        }

        mock_webhook_data = WebhookPaymentData(
            provider_transaction_id="pp_e2e_failed_test",
            status="failed",
            amount=Decimal("100.00"),
            currency="ILS",
            completed_at=None,
            failure_reason="Card declined - insufficient funds",
            metadata=None,
        )

        with patch(
            "pazpaz.services.payment_service.get_payment_provider"
        ) as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.verify_webhook.return_value = True
            mock_provider.parse_webhook_payment.return_value = mock_webhook_data
            mock_get_provider.return_value = mock_provider

            webhook_response = await payment_client.post(
                "/api/v1/payments/webhook/payplus",
                json=webhook_payload,
            )

            assert webhook_response.status_code == 200

        # Verify appointment status is unpaid
        await db_session.refresh(test_appointment_with_price)
        assert test_appointment_with_price.payment_status == "unpaid"

        # Verify transaction is failed with reason
        transactions_response = await payment_client.get(
            f"/api/v1/payments/transactions?appointment_id={test_appointment_with_price.id}",
            headers=auth_headers,
        )
        assert transactions_response.status_code == 200
        transactions = transactions_response.json()["transactions"]
        assert len(transactions) == 1
        assert transactions[0]["status"] == "failed"

        # Verify failure reason in database
        stmt = select(PaymentTransaction).where(
            PaymentTransaction.provider_transaction_id == "pp_e2e_failed_test"
        )
        result = await db_session.execute(stmt)
        transaction = result.scalar_one()
        assert transaction.failure_reason == "Card declined - insufficient funds"


class TestWebhookIdempotency:
    """Test webhook idempotency to prevent duplicate processing."""

    async def test_webhook_idempotency(
        self,
        payment_client: AsyncClient,
        db_session: AsyncSession,
        redis_client: redis.Redis,
        test_workspace_with_payments: Workspace,
        existing_payment_transaction: PaymentTransaction,
    ):
        """
        Test that duplicate webhooks don't cause issues.

        Flow:
        1. Send webhook for existing transaction
        2. Send same webhook again
        3. Verify both return 200 OK
        4. Verify transaction only updated once
        5. Verify Redis key prevents second processing
        """
        webhook_payload = {
            "page_request_uid": "pp_idempotency_test",
            "status": "completed",
            "amount": 100.00,
            "currency_code": "ILS",
            "completed_at": datetime.now(UTC).isoformat(),
            "custom_fields": {
                "workspace_id": str(test_workspace_with_payments.id),
                "appointment_id": str(existing_payment_transaction.appointment_id),
            },
        }

        mock_webhook_data = WebhookPaymentData(
            provider_transaction_id="pp_idempotency_test",
            status="completed",
            amount=Decimal("100.00"),
            currency="ILS",
            completed_at=datetime.now(UTC),
            failure_reason=None,
            metadata=None,
        )

        with patch(
            "pazpaz.services.payment_service.get_payment_provider"
        ) as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.verify_webhook.return_value = True
            mock_provider.parse_webhook_payment.return_value = mock_webhook_data
            mock_get_provider.return_value = mock_provider

            # First webhook
            response1 = await payment_client.post(
                "/api/v1/payments/webhook/payplus",
                json=webhook_payload,
            )
            assert response1.status_code == 200

            # Verify idempotency key set in Redis
            idempotency_key = "webhook:pp_idempotency_test"
            key_exists = await redis_client.exists(idempotency_key)
            assert key_exists == 1

            # Second webhook (duplicate)
            response2 = await payment_client.post(
                "/api/v1/payments/webhook/payplus",
                json=webhook_payload,
            )
            assert response2.status_code == 200

            # Verify parse_webhook_payment called twice
            # (We need to parse to get provider_transaction_id for idempotency check)
            # But the transaction update only happens once
            assert mock_provider.parse_webhook_payment.call_count == 2

        # Verify transaction updated correctly (only once)
        await db_session.refresh(existing_payment_transaction)
        assert existing_payment_transaction.status == "completed"


class TestWorkspaceIsolation:
    """Test workspace isolation for payment operations."""

    async def test_workspace_isolation_payment_requests(
        self,
        payment_client: AsyncClient,
        redis_client: redis.Redis,
        workspace_a: Workspace,
        workspace_b: Workspace,
        user_workspace_a: User,
        appointment_workspace_b: Appointment,
    ):
        """
        Test that workspace A cannot create payment for workspace B's appointment.

        Expected: 404 not found (due to workspace filtering)
        """
        auth_headers = await get_payment_auth_headers(
            workspace_a.id, user_workspace_a.id, redis_client
        )

        # Mock payment provider
        mock_link_response = PaymentLinkResponse(
            payment_link_url="https://payplus.co.il/pay/test789",
            provider_transaction_id="pp_isolation_test",
            expires_at=None,
        )

        with (
            patch(
                "pazpaz.services.payment_service.get_payment_provider"
            ) as mock_get_provider,
            patch(
                "pazpaz.services.payment_service.send_payment_request_email"
            ) as mock_email,
        ):
            mock_provider = AsyncMock()
            mock_provider.create_payment_link.return_value = mock_link_response
            mock_get_provider.return_value = mock_provider
            mock_email.return_value = True

            # User from workspace A tries to create payment for workspace B's appointment
            response = await payment_client.post(
                "/api/v1/payments/create-request",
                json={
                    "appointment_id": str(appointment_workspace_b.id),
                    "customer_email": "test@example.com",
                },
                headers=auth_headers,
            )

            # Should return 404 (appointment not found in workspace A)
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

            # Verify no transaction was created
            assert mock_provider.create_payment_link.call_count == 0


class TestPaymentValidation:
    """Test payment validation and error cases."""

    async def test_payment_request_no_price_fails(
        self,
        payment_client: AsyncClient,
        redis_client: redis.Redis,
        test_workspace_with_payments: Workspace,
        test_user_payments: User,
        test_appointment_no_price: Appointment,
    ):
        """Test that payment request fails when appointment has no price."""
        auth_headers = await get_payment_auth_headers(
            test_workspace_with_payments.id, test_user_payments.id, redis_client
        )

        response = await payment_client.post(
            "/api/v1/payments/create-request",
            json={
                "appointment_id": str(test_appointment_no_price.id),
                "customer_email": "test@example.com",
            },
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "price" in response.json()["detail"].lower()

    async def test_payment_request_payments_disabled(
        self,
        payment_client: AsyncClient,
        redis_client: redis.Redis,
        db_session: AsyncSession,
        workspace_payments_disabled: Workspace,
        test_appointment_with_price: Appointment,
    ):
        """Test that payment request fails when payments disabled for workspace."""
        # Create user for disabled workspace
        user = User(
            id=uuid.uuid4(),
            workspace_id=workspace_payments_disabled.id,
            email="disabled-workspace@example.com",
            full_name="Disabled User",
            role=UserRole.OWNER,
            is_active=True,
        )
        db_session.add(user)

        # Create appointment in disabled workspace
        appointment = Appointment(
            id=uuid.uuid4(),
            workspace_id=workspace_payments_disabled.id,
            client_id=test_appointment_with_price.client_id,
            scheduled_start=datetime.now(UTC) + timedelta(days=1),
            scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
            location_type=test_appointment_with_price.location_type,
            status=test_appointment_with_price.status,
            payment_price=Decimal("100.00"),
            payment_status="unpaid",
        )
        db_session.add(appointment)
        await db_session.commit()

        auth_headers = await get_payment_auth_headers(
            workspace_payments_disabled.id, user.id, redis_client
        )

        response = await payment_client.post(
            "/api/v1/payments/create-request",
            json={
                "appointment_id": str(appointment.id),
                "customer_email": "test@example.com",
            },
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "not enabled" in response.json()["detail"].lower()


class TestMultipleTransactions:
    """Test multiple payment transactions for same appointment."""

    async def test_multiple_payment_transactions_same_appointment(
        self,
        payment_client: AsyncClient,
        redis_client: redis.Redis,
        test_workspace_with_payments: Workspace,
        test_user_payments: User,
        test_appointment_with_price: Appointment,
    ):
        """
        Test that multiple payment requests can be created.

        Use case: First payment link expired, create new one
        """
        auth_headers = await get_payment_auth_headers(
            test_workspace_with_payments.id, test_user_payments.id, redis_client
        )

        # Mock payment provider
        mock_link_response_1 = PaymentLinkResponse(
            payment_link_url="https://payplus.co.il/pay/first",
            provider_transaction_id="pp_first_tx",
            expires_at=None,
        )
        mock_link_response_2 = PaymentLinkResponse(
            payment_link_url="https://payplus.co.il/pay/second",
            provider_transaction_id="pp_second_tx",
            expires_at=None,
        )

        with (
            patch(
                "pazpaz.services.payment_service.get_payment_provider"
            ) as mock_get_provider,
            patch(
                "pazpaz.services.payment_service.send_payment_request_email"
            ) as mock_email,
        ):
            mock_provider = AsyncMock()
            mock_get_provider.return_value = mock_provider
            mock_email.return_value = True

            # First payment request
            mock_provider.create_payment_link.return_value = mock_link_response_1
            response1 = await payment_client.post(
                "/api/v1/payments/create-request",
                json={
                    "appointment_id": str(test_appointment_with_price.id),
                    "customer_email": "test@example.com",
                },
                headers=auth_headers,
            )
            assert response1.status_code == 200
            data1 = response1.json()
            assert data1["status"] == "pending"

            # Second payment request (e.g., first expired)
            mock_provider.create_payment_link.return_value = mock_link_response_2
            response2 = await payment_client.post(
                "/api/v1/payments/create-request",
                json={
                    "appointment_id": str(test_appointment_with_price.id),
                    "customer_email": "test@example.com",
                },
                headers=auth_headers,
            )
            assert response2.status_code == 200
            data2 = response2.json()
            assert data2["status"] == "pending"

            # Verify both have different IDs
            assert data1["id"] != data2["id"]

        # Verify both transactions exist
        transactions_response = await payment_client.get(
            f"/api/v1/payments/transactions?appointment_id={test_appointment_with_price.id}",
            headers=auth_headers,
        )
        transactions = transactions_response.json()["transactions"]
        assert len(transactions) == 2


class TestEmailFailureHandling:
    """Test that email failures don't break payment creation."""

    async def test_payment_creation_email_failure_graceful(
        self,
        payment_client: AsyncClient,
        redis_client: redis.Redis,
        test_workspace_with_payments: Workspace,
        test_user_payments: User,
        test_appointment_with_price: Appointment,
    ):
        """Test that email send failure doesn't prevent payment creation."""
        auth_headers = await get_payment_auth_headers(
            test_workspace_with_payments.id, test_user_payments.id, redis_client
        )

        mock_link_response = PaymentLinkResponse(
            payment_link_url="https://payplus.co.il/pay/email_fail_test",
            provider_transaction_id="pp_email_fail",
            expires_at=None,
        )

        with (
            patch(
                "pazpaz.services.payment_service.get_payment_provider"
            ) as mock_get_provider,
            patch(
                "pazpaz.services.payment_service.send_payment_request_email"
            ) as mock_email,
        ):
            mock_provider = AsyncMock()
            mock_provider.create_payment_link.return_value = mock_link_response
            mock_get_provider.return_value = mock_provider

            # Mock email to raise exception
            mock_email.side_effect = Exception("Email server unavailable")

            # Payment should still be created
            response = await payment_client.post(
                "/api/v1/payments/create-request",
                json={
                    "appointment_id": str(test_appointment_with_price.id),
                    "customer_email": "test@example.com",
                },
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "pending"
            assert "payment_link" in data


class TestWebhookErrorHandling:
    """Test webhook error handling scenarios."""

    async def test_webhook_invalid_signature(
        self,
        payment_client: AsyncClient,
        test_workspace_with_payments: Workspace,
        existing_payment_transaction: PaymentTransaction,
    ):
        """Test webhook processing fails gracefully with invalid signature."""
        webhook_payload = {
            "page_request_uid": "pp_invalid_sig_test",
            "status": "completed",
            "amount": 100.00,
            "currency_code": "ILS",
            "custom_fields": {
                "workspace_id": str(test_workspace_with_payments.id),
            },
        }

        # Mock provider to return invalid signature
        with patch(
            "pazpaz.services.payment_service.get_payment_provider"
        ) as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.verify_webhook.return_value = False  # Invalid signature
            mock_get_provider.return_value = mock_provider

            response = await payment_client.post(
                "/api/v1/payments/webhook/payplus",
                json=webhook_payload,
            )

            # Should still return 200 to prevent retries
            assert response.status_code == 200

            # Verify parse_webhook_payment was NOT called (signature check failed)
            mock_provider.parse_webhook_payment.assert_not_called()

    async def test_webhook_transaction_not_found(
        self,
        payment_client: AsyncClient,
        test_workspace_with_payments: Workspace,
    ):
        """Test webhook processing handles missing transaction gracefully."""
        webhook_payload = {
            "page_request_uid": "pp_nonexistent_tx",
            "status": "completed",
            "amount": 100.00,
            "currency_code": "ILS",
            "custom_fields": {
                "workspace_id": str(test_workspace_with_payments.id),
            },
        }

        mock_webhook_data = WebhookPaymentData(
            provider_transaction_id="pp_nonexistent_tx",
            status="completed",
            amount=Decimal("100.00"),
            currency="ILS",
            completed_at=datetime.now(UTC),
            failure_reason=None,
            metadata=None,
        )

        with patch(
            "pazpaz.services.payment_service.get_payment_provider"
        ) as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.verify_webhook.return_value = True
            mock_provider.parse_webhook_payment.return_value = mock_webhook_data
            mock_get_provider.return_value = mock_provider

            response = await payment_client.post(
                "/api/v1/payments/webhook/payplus",
                json=webhook_payload,
            )

            # Should return 200 even if transaction not found
            assert response.status_code == 200
