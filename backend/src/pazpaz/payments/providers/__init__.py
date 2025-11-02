"""Payment provider implementations (Phase 2+ - NOT USED IN PHASE 1).

⚠️  THIS MODULE IS NOT IMPORTED OR USED IN PHASE 1 (Manual Payment Tracking).
    It is reserved for Phase 2+ automated payment provider integration.

This package contains concrete implementations of payment providers that
extend the PaymentProvider abstract base class. Each provider handles:
- Payment link creation via provider API
- Webhook signature verification
- Webhook payload parsing and normalization

Phase 2+ Providers (future implementation):
    - Bit API: Israeli mobile payment provider
    - PayBox API: Israeli payment provider
    - Stripe: International payment processor

Provider Registration:
    Providers automatically register themselves with the factory when imported.
    The factory uses the registry to instantiate providers by name.

Example:
    >>> from pazpaz.payments.factory import get_payment_provider
    >>> from pazpaz.models import Workspace
    >>>
    >>> # Get provider for workspace
    >>> workspace = Workspace(payment_provider="payplus", ...)
    >>> provider = get_payment_provider(workspace)
    >>> print(type(provider).__name__)
    PayPlusProvider
"""

# Import providers to trigger registration
# When new providers are added, import them here
# PayPlus removed in Phase 1 - will add Bit/PayBox in Phase 2+

__all__ = []
