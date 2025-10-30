"""Unit tests for payment service layer."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.appointment import Appointment, AppointmentStatus, LocationType
from pazpaz.models.client import Client
from pazpaz.models.payment_transaction import PaymentTransaction
from pazpaz.models.workspace import Workspace
from pazpaz.payments.base import PaymentLinkResponse, WebhookPaymentData
from pazpaz.payments.exceptions import (
    InvalidCredentialsError,
    WebhookVerificationError,
)
from pazpaz.services.payment_service import PaymentService

pytestmark = pytest.mark.asyncio


class TestCalculateVAT:
    """Test PaymentService.calculate_vat() static method."""

    def test_calculate_vat_registered_17_percent(self):
        """Test VAT calculation for VAT-registered business with 17% rate."""
        base, vat, total = PaymentService.calculate_vat(
            total_amount=Decimal("117.00"),
            vat_rate=Decimal("17.00"),
            vat_registered=True,
        )

        assert base == Decimal("100.00")
        assert vat == Decimal("17.00")
        assert total == Decimal("117.00")

    def test_calculate_vat_registered_complex_amount(self):
        """Test VAT calculation with complex total amount."""
        base, vat, total = PaymentService.calculate_vat(
            total_amount=Decimal("100.00"),
            vat_rate=Decimal("17.00"),
            vat_registered=True,
        )

        # base = 100 / 1.17 = 85.47 (rounded)
        assert base == Decimal("85.47")
        assert vat == Decimal("14.53")
        assert total == Decimal("100.00")
        # Verify base + vat = total
        assert base + vat == total

    def test_calculate_vat_not_registered(self):
        """Test VAT calculation for non-VAT-registered business."""
        base, vat, total = PaymentService.calculate_vat(
            total_amount=Decimal("100.00"),
            vat_rate=Decimal("17.00"),
            vat_registered=False,
        )

        # No VAT separation when not registered
        assert base == Decimal("100.00")
        assert vat == Decimal("0.00")
        assert total == Decimal("100.00")

    def test_calculate_vat_zero_rate(self):
        """Test VAT calculation with 0% VAT rate."""
        base, vat, total = PaymentService.calculate_vat(
            total_amount=Decimal("100.00"),
            vat_rate=Decimal("0.00"),
            vat_registered=True,
        )

        assert base == Decimal("100.00")
        assert vat == Decimal("0.00")
        assert total == Decimal("100.00")

    def test_calculate_vat_large_amount(self):
        """Test VAT calculation with large amount."""
        base, vat, total = PaymentService.calculate_vat(
            total_amount=Decimal("10000.00"),
            vat_rate=Decimal("17.00"),
            vat_registered=True,
        )

        # base = 10000 / 1.17 = 8547.01 (rounded)
        assert base == Decimal("8547.01")
        assert vat == Decimal("1452.99")
        assert total == Decimal("10000.00")

    def test_calculate_vat_small_amount(self):
        """Test VAT calculation with small amount."""
        base, vat, total = PaymentService.calculate_vat(
            total_amount=Decimal("1.17"),
            vat_rate=Decimal("17.00"),
            vat_registered=True,
        )

        assert base == Decimal("1.00")
        assert vat == Decimal("0.17")
        assert total == Decimal("1.17")

    def test_calculate_vat_negative_amount_raises_error(self):
        """Test VAT calculation with negative amount raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            PaymentService.calculate_vat(
                total_amount=Decimal("-100.00"),
                vat_rate=Decimal("17.00"),
                vat_registered=True,
            )

        assert "must be positive" in str(exc_info.value).lower()

    def test_calculate_vat_zero_amount_raises_error(self):
        """Test VAT calculation with zero amount raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            PaymentService.calculate_vat(
                total_amount=Decimal("0.00"),
                vat_rate=Decimal("17.00"),
                vat_registered=True,
            )

        assert "must be positive" in str(exc_info.value).lower()

    def test_calculate_vat_negative_rate_raises_error(self):
        """Test VAT calculation with negative rate raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            PaymentService.calculate_vat(
                total_amount=Decimal("100.00"),
                vat_rate=Decimal("-5.00"),
                vat_registered=True,
            )

        assert "cannot be negative" in str(exc_info.value).lower()

    def test_calculate_vat_rounding_precision(self):
        """Test VAT calculation always rounds to 2 decimal places."""
        base, vat, total = PaymentService.calculate_vat(
            total_amount=Decimal("99.99"),
            vat_rate=Decimal("17.00"),
            vat_registered=True,
        )

        # Verify all amounts have exactly 2 decimal places
        assert base.as_tuple().exponent == -2
        assert vat.as_tuple().exponent == -2
        assert total.as_tuple().exponent == -2


class TestCreatePaymentRequest:
    """Test PaymentService.create_payment_request()."""

    async def test_create_payment_request_success(
        self,
        db_session: AsyncSession,
        redis_client,
    ):
        """Test successful payment request creation."""
        # Setup test data
        workspace = Workspace(
            id=uuid.uuid4(),
            name="Test Workspace",
            payment_provider="payplus",
            payment_provider_config={
                "api_key": "test_key",
                "payment_page_uid": "page_uid",
                "webhook_secret": "secret",
            },
            vat_registered=True,
            vat_rate=Decimal("17.00"),
        )

        client = Client(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            first_name="John",
            last_name="Doe",
            email="john@example.com",
        )

        appointment = Appointment(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            client_id=client.id,
            client=client,
            scheduled_start=datetime.now(UTC) + timedelta(days=1),
            scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
            payment_price=Decimal("117.00"),
            payment_status="unpaid",
        )

        db_session.add_all([workspace, client, appointment])
        await db_session.commit()

        # Mock provider
        mock_link_response = PaymentLinkResponse(
            payment_link_url="https://payplus.co.il/pay/test123",
            provider_transaction_id="pp_tx_test123",
            expires_at=None,
        )

        with patch(
            "pazpaz.services.payment_service.get_payment_provider"
        ) as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.create_payment_link.return_value = mock_link_response
            mock_get_provider.return_value = mock_provider

            # Mock email service
            with patch(
                "pazpaz.services.payment_service.send_payment_request_email"
            ) as mock_email:
                mock_email.return_value = True

                # Execute
                service = PaymentService(db_session)
                transaction = await service.create_payment_request(
                    workspace=workspace,
                    appointment=appointment,
                    customer_email="john@example.com",
                )

                # Verify transaction created
                assert transaction is not None
                assert transaction.workspace_id == workspace.id
                assert transaction.appointment_id == appointment.id
                assert transaction.status == "pending"
                assert transaction.total_amount == Decimal("117.00")
                assert transaction.base_amount == Decimal("100.00")
                assert transaction.vat_amount == Decimal("17.00")
                assert transaction.provider == "payplus"
                assert transaction.provider_transaction_id == "pp_tx_test123"
                assert (
                    transaction.provider_payment_link
                    == "https://payplus.co.il/pay/test123"
                )
                assert transaction.currency == "ILS"
                assert transaction.payment_method == "online_card"

                # Verify appointment updated
                await db_session.refresh(appointment)
                assert appointment.payment_status == "pending"

                # Verify provider called correctly
                mock_provider.create_payment_link.assert_called_once()
                call_args = mock_provider.create_payment_link.call_args[0][0]
                assert call_args.amount == Decimal("117.00")
                assert call_args.currency == "ILS"
                assert call_args.customer_email == "john@example.com"

                # Verify email sent
                mock_email.assert_called_once()

    async def test_create_payment_request_no_vat(
        self,
        db_session: AsyncSession,
    ):
        """Test payment request creation for non-VAT-registered workspace."""
        workspace = Workspace(
            id=uuid.uuid4(),
            name="Test Workspace",
            payment_provider="payplus",
            payment_provider_config={
                "api_key": "test_key",
                "payment_page_uid": "page_uid",
                "webhook_secret": "secret",
            },
            vat_registered=False,
            vat_rate=Decimal("17.00"),
        )

        client = Client(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            first_name="Jane",
            last_name="Smith",
        )

        appointment = Appointment(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            client_id=client.id,
            client=client,
            scheduled_start=datetime.now(UTC) + timedelta(days=1),
            scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
            payment_price=Decimal("100.00"),
            payment_status="unpaid",
        )

        db_session.add_all([workspace, client, appointment])
        await db_session.commit()

        # Mock provider
        mock_link_response = PaymentLinkResponse(
            payment_link_url="https://payplus.co.il/pay/test456",
            provider_transaction_id="pp_tx_test456",
            expires_at=None,
        )

        with patch(
            "pazpaz.services.payment_service.get_payment_provider"
        ) as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.create_payment_link.return_value = mock_link_response
            mock_get_provider.return_value = mock_provider

            with patch(
                "pazpaz.services.payment_service.send_payment_request_email"
            ) as mock_email:
                mock_email.return_value = True

                # Execute
                service = PaymentService(db_session)
                transaction = await service.create_payment_request(
                    workspace=workspace,
                    appointment=appointment,
                    customer_email="jane@example.com",
                )

                # Verify no VAT separation
                assert transaction.base_amount == Decimal("100.00")
                assert transaction.vat_amount == Decimal("0.00")
                assert transaction.total_amount == Decimal("100.00")

    async def test_create_payment_request_no_price_raises_error(
        self,
        db_session: AsyncSession,
    ):
        """Test payment request fails when appointment has no price."""
        workspace = Workspace(
            id=uuid.uuid4(),
            name="Test Workspace",
            payment_provider="payplus",
            payment_provider_config={"api_key": "key"},
        )

        client = Client(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            first_name="Test",
            last_name="Client",
        )

        appointment = Appointment(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            client_id=client.id,
            client=client,
            scheduled_start=datetime.now(UTC) + timedelta(days=1),
            scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
            payment_price=None,  # No price set
        )

        db_session.add_all([workspace, client, appointment])
        await db_session.commit()

        # Execute and verify
        service = PaymentService(db_session)
        with pytest.raises(ValueError) as exc_info:
            await service.create_payment_request(
                workspace=workspace,
                appointment=appointment,
                customer_email="test@example.com",
            )

        assert "no price" in str(exc_info.value).lower()

    async def test_create_payment_request_email_failure_does_not_fail(
        self,
        db_session: AsyncSession,
    ):
        """Test payment request succeeds even if email sending fails."""
        workspace = Workspace(
            id=uuid.uuid4(),
            name="Test Workspace",
            payment_provider="payplus",
            payment_provider_config={
                "api_key": "test_key",
                "payment_page_uid": "page_uid",
                "webhook_secret": "secret",
            },
            vat_registered=False,
            vat_rate=Decimal("17.00"),
        )

        client = Client(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            first_name="Test",
            last_name="Client",
        )

        appointment = Appointment(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            client_id=client.id,
            client=client,
            scheduled_start=datetime.now(UTC) + timedelta(days=1),
            scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
            payment_price=Decimal("100.00"),
        )

        db_session.add_all([workspace, client, appointment])
        await db_session.commit()

        # Mock provider
        mock_link_response = PaymentLinkResponse(
            payment_link_url="https://payplus.co.il/pay/test789",
            provider_transaction_id="pp_tx_test789",
            expires_at=None,
        )

        with patch(
            "pazpaz.services.payment_service.get_payment_provider"
        ) as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.create_payment_link.return_value = mock_link_response
            mock_get_provider.return_value = mock_provider

            # Mock email to raise exception
            with patch(
                "pazpaz.services.payment_service.send_payment_request_email"
            ) as mock_email:
                mock_email.side_effect = Exception("Email server unavailable")

                # Execute (should NOT raise exception)
                service = PaymentService(db_session)
                transaction = await service.create_payment_request(
                    workspace=workspace,
                    appointment=appointment,
                    customer_email="test@example.com",
                )

                # Verify transaction still created successfully
                assert transaction is not None
                assert transaction.status == "pending"

    async def test_create_payment_request_invalid_credentials(
        self,
        db_session: AsyncSession,
    ):
        """Test payment request with invalid provider credentials."""
        workspace = Workspace(
            id=uuid.uuid4(),
            name="Test Workspace",
            payment_provider="payplus",
            payment_provider_config={
                "api_key": "invalid_key",
                "payment_page_uid": "page_uid",
                "webhook_secret": "secret",
            },
            vat_registered=False,
            vat_rate=Decimal("17.00"),
        )

        client = Client(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            first_name="Test",
            last_name="Client",
        )

        appointment = Appointment(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            client_id=client.id,
            client=client,
            scheduled_start=datetime.now(UTC) + timedelta(days=1),
            scheduled_end=datetime.now(UTC) + timedelta(days=1, hours=1),
            location_type=LocationType.CLINIC,
            status=AppointmentStatus.SCHEDULED,
            payment_price=Decimal("100.00"),
        )

        db_session.add_all([workspace, client, appointment])
        await db_session.commit()

        # Mock provider to raise InvalidCredentialsError
        with patch(
            "pazpaz.services.payment_service.get_payment_provider"
        ) as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.create_payment_link.side_effect = InvalidCredentialsError(
                "Invalid API key", provider="payplus"
            )
            mock_get_provider.return_value = mock_provider

            # Execute and verify exception raised
            service = PaymentService(db_session)
            with pytest.raises(InvalidCredentialsError):
                await service.create_payment_request(
                    workspace=workspace,
                    appointment=appointment,
                    customer_email="test@example.com",
                )

            # Verify failed transaction was created
            await db_session.refresh(appointment)
            from sqlalchemy import select

            stmt = select(PaymentTransaction).filter_by(appointment_id=appointment.id)
            result = await db_session.execute(stmt)
            failed_tx = result.scalar_one_or_none()
            assert failed_tx is not None
            assert failed_tx.status == "failed"
            assert "invalid" in failed_tx.failure_reason.lower()


class TestProcessWebhook:
    """Test PaymentService.process_webhook()."""

    async def test_process_webhook_success_completed(
        self,
        db_session: AsyncSession,
        redis_client,
    ):
        """Test successful webhook processing for completed payment."""
        # Setup test data
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

        client = Client(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            first_name="Test",
            last_name="Client",
        )

        appointment = Appointment(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            client_id=client.id,
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
            vat_amount=Decimal("17.00"),
            total_amount=Decimal("117.00"),
            currency="ILS",
            payment_method="online_card",
            status="pending",
            provider="payplus",
            provider_transaction_id="pp_webhook_test123",
            provider_payment_link="https://payplus.co.il/pay/test",
        )

        db_session.add_all([workspace, client, appointment, transaction])
        await db_session.commit()

        # Mock webhook payload
        webhook_payload = (
            '{"page_request_uid": "pp_webhook_test123", "status": "completed"}'
        )
        headers = {"X-PayPlus-Signature": "sha256=abc123"}

        # Mock provider
        mock_webhook_data = WebhookPaymentData(
            provider_transaction_id="pp_webhook_test123",
            status="completed",
            amount=Decimal("117.00"),
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

            # Execute
            service = PaymentService(db_session)
            result = await service.process_webhook(
                workspace=workspace,
                payload=webhook_payload,
                headers=headers,
            )

            # Verify transaction updated
            assert result.status == "completed"
            assert result.completed_at is not None

            # Verify appointment status updated
            await db_session.refresh(appointment)
            assert appointment.payment_status == "paid"

    async def test_process_webhook_idempotency(
        self,
        db_session: AsyncSession,
        redis_client,
    ):
        """Test webhook idempotency - duplicate webhooks don't re-process."""
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

        transaction = PaymentTransaction(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            base_amount=Decimal("100.00"),
            vat_amount=Decimal("0.00"),
            total_amount=Decimal("100.00"),
            currency="ILS",
            payment_method="online_card",
            status="completed",
            provider="payplus",
            provider_transaction_id="pp_idempotent_test",
            provider_payment_link="https://payplus.co.il/pay/test",
            completed_at=datetime.now(UTC),
        )

        db_session.add_all([workspace, transaction])
        await db_session.commit()

        # Set idempotency key in Redis (simulate already processed)
        await redis_client.setex("webhook:pp_idempotent_test", 86400, "1")

        webhook_payload = (
            '{"page_request_uid": "pp_idempotent_test", "status": "completed"}'
        )
        headers = {"X-PayPlus-Signature": "sha256=abc123"}

        # Mock provider
        mock_webhook_data = WebhookPaymentData(
            provider_transaction_id="pp_idempotent_test",
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

            # Execute
            service = PaymentService(db_session)
            result = await service.process_webhook(
                workspace=workspace,
                payload=webhook_payload,
                headers=headers,
            )

            # Verify existing transaction returned without re-processing
            assert result.id == transaction.id
            assert result.status == "completed"

            # Verify parse_webhook_payment WAS called to get transaction ID
            # (idempotency check happens AFTER parsing to get transaction ID)
            mock_provider.parse_webhook_payment.assert_called_once()

    async def test_process_webhook_invalid_signature(
        self,
        db_session: AsyncSession,
    ):
        """Test webhook processing fails with invalid signature."""
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

        db_session.add(workspace)
        await db_session.commit()

        webhook_payload = '{"page_request_uid": "pp_test", "status": "completed"}'
        headers = {"X-PayPlus-Signature": "sha256=invalid"}

        # Mock provider to return invalid signature
        with patch(
            "pazpaz.services.payment_service.get_payment_provider"
        ) as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.verify_webhook.return_value = False  # Invalid
            mock_get_provider.return_value = mock_provider

            # Execute and verify exception
            service = PaymentService(db_session)
            with pytest.raises(WebhookVerificationError):
                await service.process_webhook(
                    workspace=workspace,
                    payload=webhook_payload,
                    headers=headers,
                )

    async def test_process_webhook_transaction_not_found(
        self,
        db_session: AsyncSession,
        redis_client,
    ):
        """Test webhook processing fails when transaction not found."""
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

        db_session.add(workspace)
        await db_session.commit()

        webhook_payload = (
            '{"page_request_uid": "pp_nonexistent", "status": "completed"}'
        )
        headers = {"X-PayPlus-Signature": "sha256=abc123"}

        # Mock provider
        mock_webhook_data = WebhookPaymentData(
            provider_transaction_id="pp_nonexistent",
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

            # Execute and verify exception
            service = PaymentService(db_session)
            with pytest.raises(ValueError) as exc_info:
                await service.process_webhook(
                    workspace=workspace,
                    payload=webhook_payload,
                    headers=headers,
                )

            assert "transaction not found" in str(exc_info.value).lower()

    async def test_process_webhook_failed_payment(
        self,
        db_session: AsyncSession,
        redis_client,
    ):
        """Test webhook processing for failed payment."""
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

        client = Client(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            first_name="Test",
            last_name="Client",
        )

        appointment = Appointment(
            id=uuid.uuid4(),
            workspace_id=workspace.id,
            client_id=client.id,
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
            provider_transaction_id="pp_failed_webhook",
        )

        db_session.add_all([workspace, client, appointment, transaction])
        await db_session.commit()

        webhook_payload = (
            '{"page_request_uid": "pp_failed_webhook", "status": "failed"}'
        )
        headers = {"X-PayPlus-Signature": "sha256=abc123"}

        # Mock provider
        mock_webhook_data = WebhookPaymentData(
            provider_transaction_id="pp_failed_webhook",
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

            # Execute
            service = PaymentService(db_session)
            result = await service.process_webhook(
                workspace=workspace,
                payload=webhook_payload,
                headers=headers,
            )

            # Verify transaction updated to failed
            assert result.status == "failed"
            assert result.failed_at is not None
            assert result.failure_reason == "Card declined - insufficient funds"

            # Verify appointment status updated to unpaid
            await db_session.refresh(appointment)
            assert appointment.payment_status == "unpaid"
