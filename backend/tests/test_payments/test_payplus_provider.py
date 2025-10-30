"""Unit tests for PayPlus payment provider."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime
from decimal import Decimal

import pytest
import respx
from httpx import Response

from pazpaz.payments.base import PaymentLinkRequest
from pazpaz.payments.exceptions import (
    InvalidCredentialsError,
    PaymentProviderError,
    WebhookVerificationError,
)
from pazpaz.payments.providers.payplus import PayPlusProvider

pytestmark = pytest.mark.asyncio


class TestPayPlusProviderInit:
    """Test PayPlusProvider initialization."""

    async def test_init_with_valid_config(self):
        """Test initialization with all required configuration."""
        config = {
            "api_key": "test_api_key_123",
            "payment_page_uid": "page_uid_456",
            "webhook_secret": "webhook_secret_789",
        }

        provider = PayPlusProvider(config)

        assert provider.api_key == "test_api_key_123"
        assert provider.payment_page_uid == "page_uid_456"
        assert provider.webhook_secret == "webhook_secret_789"
        assert provider.base_url == "https://restapi.payplus.co.il/api/v1.0"

    async def test_init_with_custom_base_url(self):
        """Test initialization with custom base URL for sandbox."""
        config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
            "base_url": "https://sandbox.payplus.co.il/api/v1.0",
        }

        provider = PayPlusProvider(config)

        assert provider.base_url == "https://sandbox.payplus.co.il/api/v1.0"

    async def test_init_missing_api_key(self):
        """Test initialization fails when API key is missing."""
        config = {
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
        }

        with pytest.raises(InvalidCredentialsError) as exc_info:
            PayPlusProvider(config)

        assert "api key is required" in str(exc_info.value).lower()
        assert exc_info.value.provider == "payplus"

    async def test_init_missing_payment_page_uid(self):
        """Test initialization fails when payment_page_uid is missing."""
        config = {
            "api_key": "test_key",
            "webhook_secret": "secret",
        }

        with pytest.raises(InvalidCredentialsError) as exc_info:
            PayPlusProvider(config)

        assert "payment_page_uid is required" in str(exc_info.value).lower()
        assert exc_info.value.provider == "payplus"

    async def test_init_missing_webhook_secret(self):
        """Test initialization fails when webhook_secret is missing."""
        config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
        }

        with pytest.raises(InvalidCredentialsError) as exc_info:
            PayPlusProvider(config)

        assert "webhook_secret is required" in str(exc_info.value).lower()
        assert exc_info.value.provider == "payplus"


class TestPayPlusCreatePaymentLink:
    """Test PayPlusProvider.create_payment_link()."""

    @respx.mock
    async def test_create_payment_link_success(self):
        """Test successful payment link creation."""
        # Setup provider
        config = {
            "api_key": "test_api_key",
            "payment_page_uid": "page_123",
            "webhook_secret": "secret_123",
        }
        provider = PayPlusProvider(config)

        # Mock successful API response
        mock_response = {
            "success": True,
            "data": {
                "payment_page_link": "https://payplus.co.il/pay/abc123xyz",
                "page_request_uid": "pp_transaction_test123",
            },
        }

        respx.post(
            "https://restapi.payplus.co.il/api/v1.0/PaymentPages/generateLink"
        ).mock(return_value=Response(200, json=mock_response))

        # Create payment link request
        request = PaymentLinkRequest(
            amount=Decimal("150.00"),
            currency="ILS",
            description="Massage therapy appointment on 2025-11-15",
            customer_email="client@example.com",
            customer_name="John Doe",
            metadata={
                "workspace_id": "ws_abc123",
                "appointment_id": "apt_xyz789",
            },
        )

        # Execute
        result = await provider.create_payment_link(request)

        # Verify
        assert result.payment_link_url == "https://payplus.co.il/pay/abc123xyz"
        assert result.provider_transaction_id == "pp_transaction_test123"
        assert result.expires_at is None  # PayPlus doesn't provide expiration

    @respx.mock
    async def test_create_payment_link_minimal_request(self):
        """Test payment link creation with minimal required fields."""
        config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
        }
        provider = PayPlusProvider(config)

        # Mock API response
        mock_response = {
            "success": True,
            "data": {
                "payment_page_link": "https://payplus.co.il/pay/minimal",
                "page_request_uid": "pp_minimal_123",
            },
        }

        respx.post(
            "https://restapi.payplus.co.il/api/v1.0/PaymentPages/generateLink"
        ).mock(return_value=Response(200, json=mock_response))

        # Minimal request (no customer name, metadata, or URLs)
        request = PaymentLinkRequest(
            amount=Decimal("100.00"),
            currency="ILS",
            description="Test payment",
            customer_email="test@example.com",
        )

        # Execute
        result = await provider.create_payment_link(request)

        # Verify
        assert result.payment_link_url == "https://payplus.co.il/pay/minimal"
        assert result.provider_transaction_id == "pp_minimal_123"

    @respx.mock
    async def test_create_payment_link_authentication_failure_401(self):
        """Test payment link creation with invalid credentials (401)."""
        config = {
            "api_key": "invalid_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
        }
        provider = PayPlusProvider(config)

        # Mock 401 Unauthorized response
        respx.post(
            "https://restapi.payplus.co.il/api/v1.0/PaymentPages/generateLink"
        ).mock(return_value=Response(401, text="Unauthorized"))

        request = PaymentLinkRequest(
            amount=Decimal("100.00"),
            currency="ILS",
            description="Test payment",
            customer_email="test@example.com",
        )

        # Execute and verify
        with pytest.raises(InvalidCredentialsError) as exc_info:
            await provider.create_payment_link(request)

        assert "authentication failed" in str(exc_info.value).lower()
        assert exc_info.value.provider == "payplus"
        assert exc_info.value.details["status_code"] == 401

    @respx.mock
    async def test_create_payment_link_api_error_500(self):
        """Test payment link creation with API server error (500)."""
        config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
        }
        provider = PayPlusProvider(config)

        # Mock 500 Internal Server Error
        respx.post(
            "https://restapi.payplus.co.il/api/v1.0/PaymentPages/generateLink"
        ).mock(return_value=Response(500, text="Internal Server Error"))

        request = PaymentLinkRequest(
            amount=Decimal("100.00"),
            currency="ILS",
            description="Test payment",
            customer_email="test@example.com",
        )

        # Execute and verify
        with pytest.raises(PaymentProviderError) as exc_info:
            await provider.create_payment_link(request)

        assert "api error" in str(exc_info.value).lower()
        assert exc_info.value.provider == "payplus"
        assert exc_info.value.details["status_code"] == 500

    @respx.mock
    async def test_create_payment_link_api_error_response(self):
        """Test payment link creation when API returns error in response."""
        config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
        }
        provider = PayPlusProvider(config)

        # Mock error response (200 but success=false)
        mock_response = {
            "success": False,
            "error": {
                "message": "Invalid payment amount",
                "code": "INVALID_AMOUNT",
            },
        }

        respx.post(
            "https://restapi.payplus.co.il/api/v1.0/PaymentPages/generateLink"
        ).mock(return_value=Response(200, json=mock_response))

        request = PaymentLinkRequest(
            amount=Decimal("100.00"),
            currency="ILS",
            description="Test payment",
            customer_email="test@example.com",
        )

        # Execute and verify
        with pytest.raises(PaymentProviderError) as exc_info:
            await provider.create_payment_link(request)

        assert "invalid payment amount" in str(exc_info.value).lower()
        assert exc_info.value.provider == "payplus"

    @respx.mock
    async def test_create_payment_link_missing_payment_link_url(self):
        """Test error handling when API response missing payment link URL."""
        config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
        }
        provider = PayPlusProvider(config)

        # Mock response with missing payment_page_link
        mock_response = {
            "success": True,
            "data": {
                "page_request_uid": "pp_test123",
                # payment_page_link is missing
            },
        }

        respx.post(
            "https://restapi.payplus.co.il/api/v1.0/PaymentPages/generateLink"
        ).mock(return_value=Response(200, json=mock_response))

        request = PaymentLinkRequest(
            amount=Decimal("100.00"),
            currency="ILS",
            description="Test payment",
            customer_email="test@example.com",
        )

        # Execute and verify
        with pytest.raises(PaymentProviderError) as exc_info:
            await provider.create_payment_link(request)

        assert "missing payment link" in str(exc_info.value).lower()

    @respx.mock
    async def test_create_payment_link_missing_transaction_id(self):
        """Test error handling when API response missing transaction ID."""
        config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
        }
        provider = PayPlusProvider(config)

        # Mock response with missing page_request_uid
        mock_response = {
            "success": True,
            "data": {
                "payment_page_link": "https://payplus.co.il/pay/abc123",
                # page_request_uid is missing
            },
        }

        respx.post(
            "https://restapi.payplus.co.il/api/v1.0/PaymentPages/generateLink"
        ).mock(return_value=Response(200, json=mock_response))

        request = PaymentLinkRequest(
            amount=Decimal("100.00"),
            currency="ILS",
            description="Test payment",
            customer_email="test@example.com",
        )

        # Execute and verify
        with pytest.raises(PaymentProviderError) as exc_info:
            await provider.create_payment_link(request)

        assert "missing transaction id" in str(exc_info.value).lower()


class TestPayPlusVerifyWebhook:
    """Test PayPlusProvider.verify_webhook()."""

    async def test_verify_webhook_valid_signature(self):
        """Test webhook signature verification with valid signature."""
        config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "test_webhook_secret_123",
        }
        provider = PayPlusProvider(config)

        # Payload
        payload = b'{"page_request_uid": "pp_test123", "status": "completed"}'

        # Calculate expected signature
        expected_signature = hmac.new(
            b"test_webhook_secret_123", payload, hashlib.sha256
        ).hexdigest()

        headers = {"X-PayPlus-Signature": f"sha256={expected_signature}"}

        # Execute
        result = await provider.verify_webhook(payload, headers)

        # Verify
        assert result is True

    async def test_verify_webhook_invalid_signature(self):
        """Test webhook signature verification with invalid signature."""
        config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "test_webhook_secret_123",
        }
        provider = PayPlusProvider(config)

        payload = b'{"page_request_uid": "pp_test123", "status": "completed"}'

        # Use wrong signature
        headers = {"X-PayPlus-Signature": "sha256=invalid_signature_abc123def456"}

        # Execute
        result = await provider.verify_webhook(payload, headers)

        # Verify signature failed
        assert result is False

    async def test_verify_webhook_missing_signature_header(self):
        """Test webhook verification fails when signature header is missing."""
        config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
        }
        provider = PayPlusProvider(config)

        payload = b'{"page_request_uid": "pp_test123", "status": "completed"}'
        headers = {}  # No signature header

        # Execute and verify
        with pytest.raises(WebhookVerificationError) as exc_info:
            await provider.verify_webhook(payload, headers)

        assert "signature header missing" in str(exc_info.value).lower()
        assert exc_info.value.provider == "payplus"

    async def test_verify_webhook_invalid_signature_format(self):
        """Test webhook verification fails with malformed signature header."""
        config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
        }
        provider = PayPlusProvider(config)

        payload = b'{"page_request_uid": "pp_test123", "status": "completed"}'

        # Signature without "sha256=" prefix
        headers = {"X-PayPlus-Signature": "abc123def456"}

        # Execute and verify
        with pytest.raises(WebhookVerificationError) as exc_info:
            await provider.verify_webhook(payload, headers)

        assert "signature format invalid" in str(exc_info.value).lower()
        assert exc_info.value.provider == "payplus"

    async def test_verify_webhook_different_payloads_different_signatures(self):
        """Test different payloads produce different signatures."""
        config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
        }
        provider = PayPlusProvider(config)

        payload1 = b'{"page_request_uid": "pp_test1", "status": "completed"}'
        payload2 = b'{"page_request_uid": "pp_test2", "status": "failed"}'

        # Calculate signature for payload1
        signature1 = hmac.new(b"secret", payload1, hashlib.sha256).hexdigest()

        # Try to verify payload2 with signature1 (should fail)
        headers = {"X-PayPlus-Signature": f"sha256={signature1}"}
        result = await provider.verify_webhook(payload2, headers)

        assert result is False


class TestPayPlusParseWebhookPayment:
    """Test PayPlusProvider.parse_webhook_payment()."""

    async def test_parse_webhook_payment_completed(self):
        """Test parsing webhook with completed payment status."""
        config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
        }
        provider = PayPlusProvider(config)

        payload = {
            "page_request_uid": "pp_test123",
            "status": "completed",
            "amount": 150.50,
            "currency_code": "ILS",
            "completed_at": "2025-10-30T12:30:00Z",
        }

        # Execute
        result = await provider.parse_webhook_payment(payload)

        # Verify
        assert result.provider_transaction_id == "pp_test123"
        assert result.status == "completed"
        assert result.amount == Decimal("150.50")
        assert result.currency == "ILS"
        assert result.completed_at == datetime(2025, 10, 30, 12, 30, 0, tzinfo=UTC)
        assert result.failure_reason is None

    async def test_parse_webhook_payment_failed(self):
        """Test parsing webhook with failed payment status."""
        config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
        }
        provider = PayPlusProvider(config)

        payload = {
            "page_request_uid": "pp_failed_456",
            "status": "failed",
            "amount": 100.00,
            "currency_code": "ILS",
            "error_message": "Card declined - insufficient funds",
        }

        # Execute
        result = await provider.parse_webhook_payment(payload)

        # Verify
        assert result.provider_transaction_id == "pp_failed_456"
        assert result.status == "failed"
        assert result.amount == Decimal("100.00")
        assert result.currency == "ILS"
        assert result.failure_reason == "Card declined - insufficient funds"
        assert result.completed_at is None

    async def test_parse_webhook_payment_refunded(self):
        """Test parsing webhook with refunded payment status."""
        config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
        }
        provider = PayPlusProvider(config)

        payload = {
            "page_request_uid": "pp_refund_789",
            "status": "refunded",
            "amount": 200.00,
            "currency_code": "ILS",
        }

        # Execute
        result = await provider.parse_webhook_payment(payload)

        # Verify
        assert result.provider_transaction_id == "pp_refund_789"
        assert result.status == "refunded"
        assert result.amount == Decimal("200.00")

    async def test_parse_webhook_payment_with_metadata(self):
        """Test parsing webhook with custom fields (metadata)."""
        config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
        }
        provider = PayPlusProvider(config)

        payload = {
            "page_request_uid": "pp_meta_123",
            "status": "completed",
            "amount": 75.00,
            "currency_code": "ILS",
            "custom_fields": {
                "workspace_id": "ws_abc",
                "appointment_id": "apt_xyz",
            },
        }

        # Execute
        result = await provider.parse_webhook_payment(payload)

        # Verify
        assert result.metadata is not None
        assert result.metadata["workspace_id"] == "ws_abc"
        assert result.metadata["appointment_id"] == "apt_xyz"

    async def test_parse_webhook_payment_unknown_status(self):
        """Test parsing webhook with unknown status defaults to failed."""
        config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
        }
        provider = PayPlusProvider(config)

        payload = {
            "page_request_uid": "pp_unknown_999",
            "status": "unknown_status_xyz",
            "amount": 50.00,
            "currency_code": "ILS",
        }

        # Execute
        result = await provider.parse_webhook_payment(payload)

        # Verify unknown status defaults to "failed"
        assert result.status == "failed"
        assert result.provider_transaction_id == "pp_unknown_999"

    async def test_parse_webhook_payment_missing_transaction_id(self):
        """Test parsing webhook fails when transaction ID is missing."""
        config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
        }
        provider = PayPlusProvider(config)

        payload = {
            # page_request_uid is missing
            "status": "completed",
            "amount": 100.00,
            "currency_code": "ILS",
        }

        # Execute and verify
        with pytest.raises(PaymentProviderError) as exc_info:
            await provider.parse_webhook_payment(payload)

        assert "missing transaction id" in str(exc_info.value).lower()

    async def test_parse_webhook_payment_missing_status(self):
        """Test parsing webhook fails when status is missing."""
        config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
        }
        provider = PayPlusProvider(config)

        payload = {
            "page_request_uid": "pp_no_status",
            # status is missing
            "amount": 100.00,
            "currency_code": "ILS",
        }

        # Execute and verify
        with pytest.raises(PaymentProviderError) as exc_info:
            await provider.parse_webhook_payment(payload)

        assert "missing status" in str(exc_info.value).lower()

    async def test_parse_webhook_payment_missing_amount(self):
        """Test parsing webhook fails when amount is missing."""
        config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
        }
        provider = PayPlusProvider(config)

        payload = {
            "page_request_uid": "pp_no_amount",
            "status": "completed",
            # amount is missing
            "currency_code": "ILS",
        }

        # Execute and verify
        with pytest.raises(PaymentProviderError) as exc_info:
            await provider.parse_webhook_payment(payload)

        assert "missing amount" in str(exc_info.value).lower()

    async def test_parse_webhook_payment_invalid_timestamp(self):
        """Test parsing webhook with invalid timestamp (should log warning but not fail)."""
        config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
        }
        provider = PayPlusProvider(config)

        payload = {
            "page_request_uid": "pp_bad_timestamp",
            "status": "completed",
            "amount": 100.00,
            "currency_code": "ILS",
            "completed_at": "invalid-timestamp-format",
        }

        # Execute (should not raise exception)
        result = await provider.parse_webhook_payment(payload)

        # Verify completed_at is None due to parsing error
        assert result.completed_at is None
        assert result.provider_transaction_id == "pp_bad_timestamp"

    async def test_parse_webhook_payment_default_currency(self):
        """Test parsing webhook without currency defaults to ILS."""
        config = {
            "api_key": "test_key",
            "payment_page_uid": "page_uid",
            "webhook_secret": "secret",
        }
        provider = PayPlusProvider(config)

        payload = {
            "page_request_uid": "pp_no_currency",
            "status": "completed",
            "amount": 100.00,
            # currency_code is missing
        }

        # Execute
        result = await provider.parse_webhook_payment(payload)

        # Verify defaults to ILS
        assert result.currency == "ILS"
