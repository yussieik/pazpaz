"""Payment provider exception classes (Phase 2+ - NOT USED IN PHASE 1).

⚠️  THIS MODULE IS NOT IMPORTED OR USED IN PHASE 1 (Manual Payment Tracking).
    It is reserved for Phase 2+ automated payment provider integration.

This module defines the exception hierarchy for payment provider operations.
These exceptions are raised by payment provider implementations when errors
occur during payment processing, webhook verification, or provider configuration.

Exception Hierarchy:
    PaymentProviderError (base exception)
    ├── InvalidCredentialsError (authentication failures)
    ├── WebhookVerificationError (webhook signature validation failures)
    └── ProviderNotConfiguredError (missing or invalid provider configuration)

Usage:
    from pazpaz.payments.exceptions import (
        PaymentProviderError,
        InvalidCredentialsError,
        WebhookVerificationError,
        ProviderNotConfiguredError,
    )

    # In provider implementation:
    if not api_key:
        raise InvalidCredentialsError("API key is required")

    # In webhook handler:
    if not signature_valid:
        raise WebhookVerificationError("Invalid webhook signature")

    # In factory:
    if workspace.payment_provider is None:
        raise ProviderNotConfiguredError("No payment provider configured")
"""

from __future__ import annotations


class PaymentProviderError(Exception):
    """Base exception for all payment provider errors.

    All payment provider-related exceptions inherit from this base class.
    Catch this exception to handle any payment provider error generically.

    Args:
        message: Human-readable error message
        provider: Optional provider name (e.g., "payplus", "stripe")
        details: Optional dict with additional error context

    Example:
        >>> try:
        ...     await provider.create_payment_link(request)
        ... except PaymentProviderError as e:
        ...     logger.error("Payment provider error", error=str(e))
        ...     raise HTTPException(400, "Payment processing failed")
    """

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        details: dict[str, str] | None = None,
    ):
        """Initialize payment provider error.

        Args:
            message: Human-readable error message
            provider: Optional provider name (e.g., "payplus", "stripe")
            details: Optional dict with additional error context
        """
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.details = details or {}

    def __str__(self) -> str:
        """Return string representation of error.

        Returns:
            Error message with optional provider context

        Example:
            >>> error = PaymentProviderError("API error", provider="payplus")
            >>> str(error)
            '[payplus] API error'
        """
        if self.provider:
            return f"[{self.provider}] {self.message}"
        return self.message

    def __repr__(self) -> str:
        """Return detailed representation of error.

        Returns:
            Full error representation with all attributes

        Example:
            >>> error = PaymentProviderError("API error", provider="payplus")
            >>> repr(error)
            "PaymentProviderError(message='API error', provider='payplus')"
        """
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"provider={self.provider!r}, "
            f"details={self.details!r})"
        )


class InvalidCredentialsError(PaymentProviderError):
    """Exception raised when provider credentials are invalid or missing.

    This exception is raised when:
    - API keys are missing or malformed
    - Authentication fails with the payment provider
    - Credentials are expired or revoked
    - Provider account is not properly configured

    Args:
        message: Human-readable error message
        provider: Optional provider name (e.g., "payplus", "stripe")
        details: Optional dict with additional error context

    Example:
        >>> # In provider implementation:
        >>> api_key = self.config.get("api_key")
        >>> if not api_key:
        ...     raise InvalidCredentialsError(
        ...         "API key is required",
        ...         provider="payplus",
        ...         details={"config_keys": list(self.config.keys())}
        ...     )
        >>>
        >>> # In API endpoint:
        >>> try:
        ...     provider = get_payment_provider(workspace)
        ... except InvalidCredentialsError as e:
        ...     raise HTTPException(401, "Invalid payment provider credentials")
    """

    pass


class WebhookVerificationError(PaymentProviderError):
    """Exception raised when webhook signature verification fails.

    This exception is raised when:
    - Webhook signature is missing or malformed
    - Signature verification fails (wrong secret or tampered data)
    - Webhook payload is invalid or corrupted
    - Webhook timestamp is outside acceptable range (replay attack prevention)

    Security Implications:
        This exception indicates a potential security issue. Always log
        these errors for security monitoring. Never process webhooks that
        fail verification.

    Args:
        message: Human-readable error message
        provider: Optional provider name (e.g., "payplus", "stripe")
        details: Optional dict with additional error context

    Example:
        >>> # In webhook verification:
        >>> expected_signature = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        >>> if not hmac.compare_digest(signature, expected_signature):
        ...     raise WebhookVerificationError(
        ...         "Invalid webhook signature",
        ...         provider="payplus",
        ...         details={"signature_present": bool(signature)}
        ...     )
        >>>
        >>> # In webhook handler:
        >>> try:
        ...     is_valid = await provider.verify_webhook(payload, headers)
        ... except WebhookVerificationError as e:
        ...     logger.warning(
        ...         "webhook_verification_failed",
        ...         provider=e.provider,
        ...         error=str(e)
        ...     )
        ...     raise HTTPException(401, "Invalid webhook signature")
    """

    pass


class ProviderNotConfiguredError(PaymentProviderError):
    """Exception raised when payment provider is not configured for workspace.

    This exception is raised when:
    - workspace.payment_provider is None (payments disabled)
    - Requested provider name is unknown or not supported
    - Provider configuration data is missing or invalid
    - Provider credentials are not encrypted in database

    Args:
        message: Human-readable error message
        provider: Optional provider name (e.g., "payplus", "stripe")
        details: Optional dict with additional error context

    Example:
        >>> # In factory function:
        >>> if workspace.payment_provider is None:
        ...     raise ProviderNotConfiguredError(
        ...         "No payment provider configured for workspace",
        ...         details={"workspace_id": str(workspace.id)}
        ...     )
        >>>
        >>> if workspace.payment_provider not in SUPPORTED_PROVIDERS:
        ...     raise ProviderNotConfiguredError(
        ...         f"Unsupported payment provider: {workspace.payment_provider}",
        ...         provider=workspace.payment_provider,
        ...         details={"supported": list(SUPPORTED_PROVIDERS.keys())}
        ...     )
        >>>
        >>> # In API endpoint:
        >>> try:
        ...     provider = get_payment_provider(workspace)
        ... except ProviderNotConfiguredError as e:
        ...     raise HTTPException(400, "Payment provider not configured")
    """

    pass
