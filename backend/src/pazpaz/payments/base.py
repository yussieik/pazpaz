"""Payment provider abstract base class and data transfer objects.

This module defines the payment provider interface that all payment provider
implementations must follow. The abstraction layer enables swapping payment
providers (PayPlus, Stripe, Meshulam) without changing business logic.

Architecture:
    - Abstract base class: PaymentProvider (3 abstract methods)
    - Data classes: PaymentLinkRequest, PaymentLinkResponse, WebhookPaymentData
    - Provider implementations extend PaymentProvider (see providers/ directory)
    - Factory function creates provider instances (see factory.py)

Usage:
    # Provider implementation (PayPlus example):
    from pazpaz.payments.base import (
        PaymentProvider,
        PaymentLinkRequest,
        PaymentLinkResponse,
        WebhookPaymentData,
    )

    class PayPlusProvider(PaymentProvider):
        async def create_payment_link(
            self, request: PaymentLinkRequest
        ) -> PaymentLinkResponse:
            # Implement PayPlus API call
            ...

        async def verify_webhook(self, payload: bytes, headers: dict) -> bool:
            # Implement PayPlus webhook signature verification
            ...

        async def parse_webhook_payment(
            self, payload: dict
        ) -> WebhookPaymentData:
            # Parse PayPlus webhook JSON
            ...

    # Usage in service layer:
    provider = get_payment_provider(workspace)
    link_request = PaymentLinkRequest(
        amount=Decimal("150.00"),
        currency="ILS",
        description="Appointment payment",
        customer_email="client@example.com",
    )
    link_response = await provider.create_payment_link(link_request)
    print(link_response.payment_link_url)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass
class PaymentLinkRequest:
    """Request data for creating a payment link.

    This data class encapsulates all information needed to generate a
    payment link from any payment provider. Providers may not use all
    fields (e.g., not all providers support success/cancel URLs).

    Attributes:
        amount: Payment amount (in main currency units, e.g., ILS not agorot)
        currency: ISO 4217 currency code (e.g., "ILS", "USD", "EUR")
        description: Human-readable payment description for customer
        customer_email: Customer's email address for receipts/notifications
        customer_name: Optional customer full name for display
        metadata: Optional dict with custom data (workspace_id, appointment_id)
        success_url: Optional URL to redirect after successful payment
        cancel_url: Optional URL to redirect after cancelled payment

    Example:
        >>> from decimal import Decimal
        >>> request = PaymentLinkRequest(
        ...     amount=Decimal("150.00"),
        ...     currency="ILS",
        ...     description="Massage therapy appointment on 2025-11-15",
        ...     customer_email="client@example.com",
        ...     customer_name="John Doe",
        ...     metadata={
        ...         "workspace_id": "a1b2c3d4-5678-90ab-cdef-123456789abc",
        ...         "appointment_id": "f1e2d3c4-5678-90ab-cdef-fedcba987654",
        ...     },
        ...     success_url="https://pazpaz.app/payment/success",
        ...     cancel_url="https://pazpaz.app/payment/cancelled",
        ... )
        >>> print(request.amount)
        150.00
    """

    amount: Decimal
    currency: str
    description: str
    customer_email: str
    customer_name: str | None = None
    metadata: dict[str, str] | None = None
    success_url: str | None = None
    cancel_url: str | None = None

    def __post_init__(self):
        """Validate request data after initialization.

        Raises:
            ValueError: If amount is negative or zero
            ValueError: If currency code is not 3 characters
            ValueError: If required fields are empty
        """
        if self.amount <= 0:
            raise ValueError(f"Amount must be positive, got {self.amount}")

        if not self.currency or len(self.currency) != 3:
            raise ValueError(
                f"Currency must be 3-letter ISO code, got '{self.currency}'"
            )

        if not self.description or not self.description.strip():
            raise ValueError("Description cannot be empty")

        if not self.customer_email or not self.customer_email.strip():
            raise ValueError("Customer email cannot be empty")


@dataclass
class PaymentLinkResponse:
    """Response data from payment link creation.

    This data class contains the payment link URL and provider-specific
    transaction identifier. The provider_transaction_id is used to match
    webhook callbacks to transactions in our database.

    Attributes:
        payment_link_url: Full URL to payment page (customer clicks this)
        provider_transaction_id: Provider's unique transaction identifier
        expires_at: Optional expiration timestamp (None if no expiration)

    Example:
        >>> from datetime import datetime, timezone, timedelta
        >>> response = PaymentLinkResponse(
        ...     payment_link_url="https://payplus.co.il/pay/abc123def456",
        ...     provider_transaction_id="pp_abc123def456",
        ...     expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        ... )
        >>> print(response.payment_link_url)
        https://payplus.co.il/pay/abc123def456
    """

    payment_link_url: str
    provider_transaction_id: str
    expires_at: datetime | None = None

    def __post_init__(self):
        """Validate response data after initialization.

        Raises:
            ValueError: If payment_link_url is not a valid URL
            ValueError: If provider_transaction_id is empty
        """
        if not self.payment_link_url or not self.payment_link_url.strip():
            raise ValueError("Payment link URL cannot be empty")

        if not self.payment_link_url.startswith(("http://", "https://")):
            raise ValueError(
                f"Payment link URL must be HTTP(S), got '{self.payment_link_url}'"
            )

        if not self.provider_transaction_id or not self.provider_transaction_id.strip():
            raise ValueError("Provider transaction ID cannot be empty")


@dataclass
class WebhookPaymentData:
    """Parsed payment data from provider webhook.

    This data class represents the normalized payment information extracted
    from a provider webhook. All providers must parse their webhooks into
    this common format for consistent handling in the service layer.

    Attributes:
        provider_transaction_id: Provider's unique transaction identifier
        status: Payment status ("completed", "failed", "refunded", "pending")
        amount: Payment amount (in main currency units)
        currency: ISO 4217 currency code (e.g., "ILS", "USD", "EUR")
        completed_at: Timestamp when payment completed (None if not completed)
        failure_reason: Human-readable failure reason (None if not failed)
        metadata: Optional dict with custom data from payment link request

    Status Values:
        - "completed": Payment successful, funds captured
        - "failed": Payment failed (card declined, insufficient funds, etc.)
        - "refunded": Payment was completed but later refunded
        - "pending": Payment initiated but not yet completed (rare in webhooks)

    Example:
        >>> from datetime import datetime, timezone
        >>> from decimal import Decimal
        >>> webhook_data = WebhookPaymentData(
        ...     provider_transaction_id="pp_abc123def456",
        ...     status="completed",
        ...     amount=Decimal("150.00"),
        ...     currency="ILS",
        ...     completed_at=datetime.now(timezone.utc),
        ...     failure_reason=None,
        ...     metadata={
        ...         "workspace_id": "a1b2c3d4-5678-90ab-cdef-123456789abc",
        ...         "appointment_id": "f1e2d3c4-5678-90ab-cdef-fedcba987654",
        ...     },
        ... )
        >>> print(webhook_data.status)
        completed
    """

    provider_transaction_id: str
    status: str
    amount: Decimal
    currency: str
    completed_at: datetime | None = None
    failure_reason: str | None = None
    metadata: dict[str, str] | None = None

    def __post_init__(self):
        """Validate webhook data after initialization.

        Raises:
            ValueError: If provider_transaction_id is empty
            ValueError: If status is not a valid payment status
            ValueError: If amount is negative
            ValueError: If currency code is not 3 characters
        """
        if not self.provider_transaction_id or not self.provider_transaction_id.strip():
            raise ValueError("Provider transaction ID cannot be empty")

        valid_statuses = {"completed", "failed", "refunded", "pending"}
        if self.status not in valid_statuses:
            raise ValueError(
                f"Invalid status '{self.status}'. Must be one of {valid_statuses}"
            )

        if self.amount < 0:
            raise ValueError(f"Amount cannot be negative, got {self.amount}")

        if not self.currency or len(self.currency) != 3:
            raise ValueError(
                f"Currency must be 3-letter ISO code, got '{self.currency}'"
            )


class PaymentProvider(ABC):
    """Abstract base class for payment provider implementations.

    All payment provider implementations (PayPlus, Stripe, Meshulam) must
    extend this base class and implement the three abstract methods:
    - create_payment_link(): Generate payment link from provider API
    - verify_webhook(): Verify webhook signature for security
    - parse_webhook_payment(): Parse webhook JSON into WebhookPaymentData

    Constructor:
        All provider implementations receive a config dict in __init__().
        The config contains decrypted API credentials and provider-specific
        settings from workspace.payment_provider_config.

    Thread Safety:
        Provider instances are created per-request and should not maintain
        mutable state. All methods are async to support concurrent requests.

    Example:
        # Implement a new provider:
        class PayPlusProvider(PaymentProvider):
            def __init__(self, config: dict):
                super().__init__(config)
                self.api_key = config["api_key"]
                self.payment_page_uid = config["payment_page_uid"]
                self.webhook_secret = config["webhook_secret"]

            async def create_payment_link(
                self, request: PaymentLinkRequest
            ) -> PaymentLinkResponse:
                # Call PayPlus API
                ...

            async def verify_webhook(
                self, payload: bytes, headers: dict
            ) -> bool:
                # Verify HMAC-SHA256 signature
                ...

            async def parse_webhook_payment(
                self, payload: dict
            ) -> WebhookPaymentData:
                # Parse PayPlus JSON format
                ...

        # Use provider via factory:
        from pazpaz.payments.factory import get_payment_provider
        provider = get_payment_provider(workspace)
        response = await provider.create_payment_link(request)
    """

    def __init__(self, config: dict):
        """Initialize payment provider with decrypted configuration.

        Args:
            config: Decrypted provider configuration dict with API credentials.
                   Keys and structure are provider-specific. Common keys:
                   - api_key: Provider API key
                   - webhook_secret: Secret for webhook signature verification
                   - payment_page_uid: Provider-specific page/account identifier
                   - base_url: Optional custom API base URL (for sandbox testing)

        Example:
            >>> config = {
            ...     "api_key": "pk_live_abc123...",
            ...     "webhook_secret": "whsec_def456...",
            ...     "payment_page_uid": "page_xyz789...",
            ... }
            >>> provider = PayPlusProvider(config)
        """
        self.config = config

    @abstractmethod
    async def create_payment_link(
        self, request: PaymentLinkRequest
    ) -> PaymentLinkResponse:
        """Create payment link from provider API.

        This method calls the payment provider's API to generate a payment
        link (payment page URL) that can be sent to the customer via email.

        Args:
            request: Payment link request with amount, currency, customer info

        Returns:
            PaymentLinkResponse with payment_link_url and provider_transaction_id

        Raises:
            InvalidCredentialsError: If provider API credentials are invalid
            PaymentProviderError: If API call fails or returns error

        Example:
            >>> request = PaymentLinkRequest(
            ...     amount=Decimal("150.00"),
            ...     currency="ILS",
            ...     description="Appointment payment",
            ...     customer_email="client@example.com",
            ... )
            >>> response = await provider.create_payment_link(request)
            >>> print(response.payment_link_url)
            https://payplus.co.il/pay/abc123
        """
        pass

    @abstractmethod
    async def verify_webhook(self, payload: bytes, headers: dict) -> bool:
        """Verify webhook signature for security.

        This method validates the webhook came from the payment provider
        by verifying the cryptographic signature. Always verify webhooks
        before processing to prevent unauthorized requests.

        Security Requirements:
        - Use constant-time comparison (hmac.compare_digest) to prevent timing attacks
        - Reject webhooks with missing or invalid signatures
        - Never process unverified webhooks (can lead to fraud)

        Args:
            payload: Raw webhook request body (bytes, not parsed JSON)
            headers: HTTP headers dict (must include signature header)

        Returns:
            True if signature is valid, False otherwise

        Raises:
            WebhookVerificationError: If signature verification fails

        Example:
            >>> payload = b'{"transaction_id": "abc123", "status": "completed"}'
            >>> headers = {"X-PayPlus-Signature": "sha256=abc123..."}
            >>> is_valid = await provider.verify_webhook(payload, headers)
            >>> if not is_valid:
            ...     raise HTTPException(401, "Invalid webhook signature")
        """
        pass

    @abstractmethod
    async def parse_webhook_payment(self, payload: dict) -> WebhookPaymentData:
        """Parse webhook JSON into normalized payment data.

        This method extracts payment information from the provider-specific
        webhook payload and converts it to the common WebhookPaymentData format.

        Args:
            payload: Parsed webhook JSON as dict (after signature verification)

        Returns:
            WebhookPaymentData with normalized payment information

        Raises:
            PaymentProviderError: If webhook payload is invalid or missing required fields

        Example:
            >>> # PayPlus webhook format:
            >>> payplus_payload = {
            ...     "page_request_uid": "pp_abc123",
            ...     "status": "completed",
            ...     "amount": 150.00,
            ...     "currency_code": "ILS",
            ...     "completed_at": "2025-11-15T14:30:00Z",
            ...     "custom_fields": {"workspace_id": "abc-123"},
            ... }
            >>> webhook_data = await provider.parse_webhook_payment(payplus_payload)
            >>> print(webhook_data.provider_transaction_id)
            pp_abc123
            >>> print(webhook_data.status)
            completed
        """
        pass
