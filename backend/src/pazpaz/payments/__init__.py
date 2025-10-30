"""Payment provider abstraction layer for PazPaz.

This package provides the infrastructure for integrating payment providers
(PayPlus, Stripe, Meshulam) into PazPaz's practice management workflow.

Architecture Overview:
    - base.py: Abstract base class (PaymentProvider) and data transfer objects
    - exceptions.py: Payment provider exception hierarchy
    - factory.py: Factory function for creating provider instances
    - providers/: Payment provider implementations (payplus.py, stripe.py, etc.)

Key Components:
    1. PaymentProvider (ABC):
       - create_payment_link(): Generate payment link from provider API
       - verify_webhook(): Verify webhook signature for security
       - parse_webhook_payment(): Parse webhook data into common format

    2. Data Classes:
       - PaymentLinkRequest: Input for creating payment links
       - PaymentLinkResponse: Output with payment URL and transaction ID
       - WebhookPaymentData: Normalized payment data from webhooks

    3. Exceptions:
       - PaymentProviderError: Base exception
       - InvalidCredentialsError: Authentication failures
       - WebhookVerificationError: Webhook signature verification failures
       - ProviderNotConfiguredError: Missing/invalid provider configuration

    4. Factory:
       - get_payment_provider(workspace): Create provider instance
       - register_provider(name, class): Register provider implementation

Usage Example:
    # Service layer usage:
    from pazpaz.payments import (
        get_payment_provider,
        PaymentLinkRequest,
        PaymentProviderError,
    )
    from decimal import Decimal

    # Get provider for workspace
    try:
        provider = get_payment_provider(workspace)
    except ProviderNotConfiguredError:
        raise HTTPException(400, "Payments not enabled")

    # Create payment link
    request = PaymentLinkRequest(
        amount=Decimal("150.00"),
        currency="ILS",
        description="Appointment payment",
        customer_email="client@example.com",
        metadata={
            "workspace_id": str(workspace.id),
            "appointment_id": str(appointment.id),
        },
    )

    try:
        response = await provider.create_payment_link(request)
        print(response.payment_link_url)
    except InvalidCredentialsError:
        raise HTTPException(401, "Invalid payment provider credentials")
    except PaymentProviderError as e:
        logger.error("payment_provider_error", error=str(e))
        raise HTTPException(400, "Payment processing failed")

    # Verify webhook
    is_valid = await provider.verify_webhook(payload, headers)
    if not is_valid:
        raise HTTPException(401, "Invalid webhook signature")

    # Parse webhook data
    webhook_data = await provider.parse_webhook_payment(json.loads(payload))
    print(webhook_data.status)  # "completed", "failed", etc.

Provider Implementation:
    # Create new provider (e.g., providers/payplus.py):
    from pazpaz.payments import PaymentProvider, register_provider

    class PayPlusProvider(PaymentProvider):
        async def create_payment_link(self, request):
            # Call PayPlus API
            ...

        async def verify_webhook(self, payload, headers):
            # Verify HMAC-SHA256 signature
            ...

        async def parse_webhook_payment(self, payload):
            # Parse PayPlus JSON format
            ...

    # Register provider at module level
    register_provider("payplus", PayPlusProvider)

Security Notes:
    - Provider credentials are encrypted at rest in database
    - Factory decrypts credentials using encryption_key from AWS Secrets Manager
    - Always verify webhook signatures before processing
    - Never log decrypted credentials or sensitive payment data
    - Use constant-time comparison for signature verification (hmac.compare_digest)

Phase 1 Implementation:
    Phase 1 (current) implements:
    - PayPlus provider for Israeli market
    - Payment request creation and email sending
    - Webhook processing and status updates
    - Basic VAT calculation

    Future phases will add:
    - Phase 2: Tax compliance (receipts, manual payments, financial reports)
    - Phase 3: Multi-provider support (Stripe for US, Meshulam alternative)
"""

# Import providers to trigger registration
# This ensures provider classes register themselves with the factory
from pazpaz.payments import providers  # noqa: F401
from pazpaz.payments.base import (
    PaymentLinkRequest,
    PaymentLinkResponse,
    PaymentProvider,
    WebhookPaymentData,
)
from pazpaz.payments.exceptions import (
    InvalidCredentialsError,
    PaymentProviderError,
    ProviderNotConfiguredError,
    WebhookVerificationError,
)
from pazpaz.payments.factory import (
    get_payment_provider,
    get_registered_providers,
    register_provider,
)

__all__ = [
    # Base classes and data transfer objects
    "PaymentProvider",
    "PaymentLinkRequest",
    "PaymentLinkResponse",
    "WebhookPaymentData",
    # Exceptions
    "PaymentProviderError",
    "InvalidCredentialsError",
    "WebhookVerificationError",
    "ProviderNotConfiguredError",
    # Factory functions
    "get_payment_provider",
    "register_provider",
    "get_registered_providers",
]
