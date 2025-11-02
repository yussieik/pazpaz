"""Payment provider implementations.

This package contains concrete implementations of payment providers that
extend the PaymentProvider abstract base class. Each provider handles:
- Payment link creation via provider API
- Webhook signature verification
- Webhook payload parsing and normalization

Available Providers:
    - PayPlus: Israeli payment provider (Phase 1 implementation)
    - Future: Stripe, Meshulam, etc.

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
