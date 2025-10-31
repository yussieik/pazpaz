"""PayPlus payment provider implementation.

This module implements the PaymentProvider interface for PayPlus, an Israeli
payment gateway. PayPlus is the Phase 1 payment provider for PazPaz, supporting
ILS transactions and Israeli therapist workflows.

Provider Configuration:
    Required config keys (encrypted in workspace.payment_provider_config):
    - api_key: PayPlus API authentication key
    - payment_page_uid: PayPlus payment page identifier
    - webhook_secret: Secret for HMAC-SHA256 webhook signature verification

API Details:
    - Base URL: https://restapi.payplus.co.il/api/v1.0
    - Endpoint: POST /PaymentPages/generateLink
    - Authentication: Two headers (api-key, secret-key)
    - Webhook signature: HMAC-SHA256 (ASSUMED - verify in sandbox)

IMPORTANT - Sandbox Verification Required:
    This implementation is based on documented assumptions about the PayPlus API.
    Many field names, formats, and behaviors are ASSUMED and MUST BE VERIFIED
    during sandbox testing. See docs/payment_providers/payplus_api_notes.md
    for a complete list of assumptions requiring verification.

    Key assumptions to verify:
    1. Request/response field names
    2. Amount format (ILS vs agorot)
    3. Webhook signature algorithm and header name
    4. Status values and transitions

Usage:
    # Provider is instantiated via factory, not directly
    from pazpaz.payments.factory import get_payment_provider

    provider = get_payment_provider(workspace)  # Returns PayPlusProvider instance

    # Create payment link
    request = PaymentLinkRequest(
        amount=Decimal("150.00"),
        currency="ILS",
        description="Massage therapy appointment",
        customer_email="client@example.com",
    )
    response = await provider.create_payment_link(request)
    print(response.payment_link_url)

    # Verify webhook
    is_valid = await provider.verify_webhook(payload_bytes, headers)

    # Parse webhook
    payment_data = await provider.parse_webhook_payment(payload_dict)

Security:
    - API credentials encrypted at rest in database
    - Webhook signatures verified using constant-time comparison
    - Never log decrypted credentials or sensitive payment data
    - All API calls use HTTPS

References:
    - API Notes: docs/payment_providers/payplus_api_notes.md
    - PayPlus Docs: [URL NEEDED]
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import httpx

from pazpaz.core.logging import get_logger
from pazpaz.payments.base import (
    PaymentLinkRequest,
    PaymentLinkResponse,
    PaymentProvider,
    WebhookPaymentData,
)
from pazpaz.payments.exceptions import (
    InvalidCredentialsError,
    PaymentProviderError,
    WebhookVerificationError,
)
from pazpaz.payments.factory import register_provider

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

# PayPlus API configuration
PAYPLUS_BASE_URL = "https://restapi.payplus.co.il/api/v1.0"
PAYPLUS_SANDBOX_URL = "https://restapidev.payplus.co.il/api/v1.0"

# Timeout configuration for API calls
API_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class PayPlusProvider(PaymentProvider):
    """PayPlus payment provider implementation.

    This provider handles payment link creation and webhook processing for
    PayPlus, an Israeli payment gateway. It implements the PaymentProvider
    interface with PayPlus-specific API integration.

    Configuration Keys:
        - api_key (str): PayPlus API authentication key
        - payment_page_uid (str): PayPlus payment page identifier
        - webhook_secret (str): Secret for webhook signature verification
        - base_url (str, optional): Custom base URL for sandbox testing

    Thread Safety:
        This provider is stateless and thread-safe. Instances are created
        per-request and do not maintain mutable state.

    Example:
        >>> config = {
        ...     "api_key": "pk_live_abc123...",
        ...     "payment_page_uid": "page_xyz789...",
        ...     "webhook_secret": "whsec_def456...",
        ... }
        >>> provider = PayPlusProvider(config)
        >>> response = await provider.create_payment_link(request)
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize PayPlus provider with configuration.

        Args:
            config: Decrypted provider configuration with keys:
                   - api_key: PayPlus API key
                   - payment_page_uid: Payment page identifier
                   - webhook_secret: Webhook signature verification secret
                   - base_url (optional): Custom base URL for sandbox

        Raises:
            InvalidCredentialsError: If required config keys are missing
        """
        super().__init__(config)

        # Validate required configuration keys
        self.api_key = config.get("api_key")
        self.payment_page_uid = config.get("payment_page_uid")
        self.webhook_secret = config.get("webhook_secret")

        if not self.api_key:
            raise InvalidCredentialsError(
                "PayPlus API key is required in provider configuration",
                provider="payplus",
                details={"config_keys": list(config.keys())},
            )

        if not self.payment_page_uid:
            raise InvalidCredentialsError(
                "PayPlus payment_page_uid is required in provider configuration",
                provider="payplus",
                details={"config_keys": list(config.keys())},
            )

        if not self.webhook_secret:
            raise InvalidCredentialsError(
                "PayPlus webhook_secret is required in provider configuration",
                provider="payplus",
                details={"config_keys": list(config.keys())},
            )

        # Allow custom base URL for sandbox testing
        self.base_url = config.get("base_url", PAYPLUS_BASE_URL)

        logger.info(
            "payplus_provider_initialized",
            base_url=self.base_url,
            payment_page_uid=self.payment_page_uid,
            # Never log actual API key, only indicate it's present
            has_api_key=bool(self.api_key),
        )

    async def create_payment_link(
        self, request: PaymentLinkRequest
    ) -> PaymentLinkResponse:
        """Create payment link via PayPlus API.

        This method calls the PayPlus API to generate a payment link that
        can be sent to the customer via email. The link directs to a hosted
        payment page where the customer completes payment.

        Args:
            request: Payment link request with amount, currency, customer info

        Returns:
            PaymentLinkResponse with payment link URL and transaction ID

        Raises:
            InvalidCredentialsError: If API authentication fails (401)
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
        # Build API request payload
        # TODO: Verify field names and formats during sandbox testing
        payload = {
            "payment_page_uid": self.payment_page_uid,
            "amount": float(request.amount),  # TODO: Verify if ILS or agorot
            "currency_code": request.currency,
            "description": request.description,
            "email_address": request.customer_email,  # TODO: Verify field name
        }

        # Add optional fields if provided
        if request.customer_name:
            payload["customer_name"] = request.customer_name  # TODO: Verify field name

        if request.success_url:
            payload["success_url"] = request.success_url  # TODO: Verify field name

        if request.cancel_url:
            payload["failure_url"] = request.cancel_url  # TODO: Verify field name

        # Add custom fields (metadata) if provided
        if request.metadata:
            payload["custom_fields"] = request.metadata  # TODO: Verify structure

        # Log request (without sensitive data)
        logger.info(
            "payplus_create_payment_link_request",
            amount=str(request.amount),
            currency=request.currency,
            customer_email=request.customer_email[:3]
            + "***",  # Partial email for privacy
            has_metadata=bool(request.metadata),
        )

        # Make API request
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                # PayPlus uses two separate headers: api-key and secret-key
                # (not standard Authorization: Bearer)
                headers = {
                    "api-key": self.api_key,
                    "secret-key": self.webhook_secret,
                    "Content-Type": "application/json",
                }

                endpoint = f"{self.base_url}/PaymentPages/generateLink"

                response = await client.post(endpoint, headers=headers, json=payload)

                # Log response status
                logger.info(
                    "payplus_api_response",
                    status_code=response.status_code,
                    endpoint=endpoint,
                )

                # Handle authentication errors
                if response.status_code == 401:
                    logger.error(
                        "payplus_authentication_failed",
                        status_code=response.status_code,
                        response_text=response.text[:200],  # Truncate for logging
                    )
                    raise InvalidCredentialsError(
                        "PayPlus API authentication failed. "
                        "Check API key in workspace settings.",
                        provider="payplus",
                        details={"status_code": response.status_code},
                    )

                # Handle other HTTP errors
                if response.status_code >= 400:
                    error_text = response.text
                    logger.error(
                        "payplus_api_error",
                        status_code=response.status_code,
                        response_text=error_text[:500],  # Truncate for logging
                    )
                    raise PaymentProviderError(
                        f"PayPlus API error (status {response.status_code}): {error_text}",
                        provider="payplus",
                        details={
                            "status_code": response.status_code,
                            "response": error_text[:200],
                        },
                    )

                # Parse response
                # TODO: Verify response structure during sandbox testing
                response_data = response.json()

                # Check for API-level errors in response
                if not response_data.get("success", True):
                    error_info = response_data.get("error", {})
                    error_message = error_info.get("message", "Unknown error")
                    logger.error(
                        "payplus_api_error_response",
                        error_message=error_message,
                        error_code=error_info.get("code"),
                    )
                    raise PaymentProviderError(
                        f"PayPlus API returned error: {error_message}",
                        provider="payplus",
                        details={"error": error_info},
                    )

                # Extract payment link and transaction ID
                # TODO: Verify field names during sandbox testing
                data = response_data.get("data", {})
                payment_link_url = data.get(
                    "payment_page_link"
                )  # TODO: Verify field name
                provider_transaction_id = data.get(
                    "page_request_uid"
                )  # TODO: Verify field name

                if not payment_link_url:
                    logger.error(
                        "payplus_missing_payment_link",
                        response_data=response_data,
                    )
                    raise PaymentProviderError(
                        "PayPlus API response missing payment link URL",
                        provider="payplus",
                        details={"response": response_data},
                    )

                if not provider_transaction_id:
                    logger.error(
                        "payplus_missing_transaction_id",
                        response_data=response_data,
                    )
                    raise PaymentProviderError(
                        "PayPlus API response missing transaction ID",
                        provider="payplus",
                        details={"response": response_data},
                    )

                logger.info(
                    "payplus_payment_link_created",
                    provider_transaction_id=provider_transaction_id,
                    payment_link_url=payment_link_url[:50] + "...",  # Truncate URL
                )

                return PaymentLinkResponse(
                    payment_link_url=payment_link_url,
                    provider_transaction_id=provider_transaction_id,
                    expires_at=None,  # TODO: Check if PayPlus provides expiration
                )

        except (InvalidCredentialsError, PaymentProviderError):
            # Re-raise our own exceptions without wrapping
            raise

        except httpx.TimeoutException as e:
            logger.error(
                "payplus_api_timeout",
                error=str(e),
                timeout=API_TIMEOUT.read,
            )
            raise PaymentProviderError(
                f"PayPlus API request timed out after {API_TIMEOUT.read}s",
                provider="payplus",
                details={"error": str(e)},
            ) from e

        except httpx.HTTPError as e:
            logger.error(
                "payplus_api_http_error",
                error=str(e),
                exc_info=True,
            )
            raise PaymentProviderError(
                f"PayPlus API request failed: {e}",
                provider="payplus",
                details={"error": str(e)},
            ) from e

        except Exception as e:
            logger.error(
                "payplus_unexpected_error",
                error=str(e),
                exc_info=True,
            )
            raise PaymentProviderError(
                f"Unexpected error creating PayPlus payment link: {e}",
                provider="payplus",
                details={"error": str(e)},
            ) from e

    async def verify_webhook(self, payload: bytes, headers: dict[str, str]) -> bool:
        """Verify PayPlus webhook signature.

        This method validates the webhook came from PayPlus by verifying the
        HMAC-SHA256 signature in the webhook headers. Always verify webhooks
        before processing to prevent unauthorized requests.

        Security:
            - Uses constant-time comparison (hmac.compare_digest) to prevent
              timing attacks
            - Returns False (not exception) for invalid signatures
            - Logs failed verification attempts for security monitoring

        Args:
            payload: Raw webhook request body (bytes, not parsed JSON)
            headers: HTTP headers dict with signature header

        Returns:
            True if signature is valid, False otherwise

        Raises:
            WebhookVerificationError: If signature header is missing or malformed

        Example:
            >>> payload = b'{"page_request_uid": "abc123", "status": "completed"}'
            >>> headers = {"X-PayPlus-Signature": "sha256=abc123def456..."}
            >>> is_valid = await provider.verify_webhook(payload, headers)
            >>> if not is_valid:
            ...     raise HTTPException(401, "Invalid webhook signature")
        """
        # TODO: Verify signature header name during sandbox testing
        signature_header = headers.get("X-PayPlus-Signature")

        if not signature_header:
            logger.warning(
                "payplus_webhook_missing_signature",
                headers_present=list(headers.keys()),
            )
            raise WebhookVerificationError(
                "PayPlus webhook signature header missing",
                provider="payplus",
                details={"headers": list(headers.keys())},
            )

        # TODO: Verify signature format during sandbox testing
        # Assuming format: "sha256=<hex_signature>"
        if not signature_header.startswith("sha256="):
            logger.warning(
                "payplus_webhook_invalid_signature_format",
                signature_header=signature_header[:20] + "...",  # Truncate
            )
            raise WebhookVerificationError(
                "PayPlus webhook signature format invalid (expected 'sha256=...')",
                provider="payplus",
                details={"signature_format": signature_header[:20]},
            )

        # Extract signature (remove "sha256=" prefix)
        provided_signature = signature_header[7:]  # len("sha256=") = 7

        # Calculate expected signature using HMAC-SHA256
        # TODO: Verify signature algorithm during sandbox testing
        expected_signature = hmac.new(
            self.webhook_secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()

        # Use constant-time comparison to prevent timing attacks
        is_valid = hmac.compare_digest(provided_signature, expected_signature)

        if is_valid:
            logger.info("payplus_webhook_signature_valid")
        else:
            logger.warning(
                "payplus_webhook_signature_invalid",
                # Log truncated signatures for debugging (not full for security)
                provided_prefix=provided_signature[:8],
                expected_prefix=expected_signature[:8],
            )

        return is_valid

    async def parse_webhook_payment(
        self, payload: dict[str, Any]
    ) -> WebhookPaymentData:
        """Parse PayPlus webhook payload into normalized payment data.

        This method extracts payment information from the PayPlus webhook
        payload and converts it to the common WebhookPaymentData format
        for consistent handling in the service layer.

        Args:
            payload: Parsed webhook JSON as dict (after signature verification)

        Returns:
            WebhookPaymentData with normalized payment information

        Raises:
            PaymentProviderError: If webhook payload is missing required fields

        Example:
            >>> payload = {
            ...     "page_request_uid": "pp_abc123",
            ...     "status": "completed",
            ...     "amount": 150.00,
            ...     "currency_code": "ILS",
            ...     "completed_at": "2025-10-30T10:00:00Z",
            ... }
            >>> webhook_data = await provider.parse_webhook_payment(payload)
            >>> print(webhook_data.status)
            completed
        """
        # TODO: Verify field names during sandbox testing
        try:
            # Extract transaction ID
            provider_transaction_id = payload.get(
                "page_request_uid"
            )  # TODO: Verify field name
            if not provider_transaction_id:
                raise PaymentProviderError(
                    "PayPlus webhook missing transaction ID (page_request_uid)",
                    provider="payplus",
                    details={"payload_keys": list(payload.keys())},
                )

            # Extract and normalize status
            # TODO: Verify status values during sandbox testing
            payplus_status = payload.get("status")
            if not payplus_status:
                raise PaymentProviderError(
                    "PayPlus webhook missing status field",
                    provider="payplus",
                    details={"provider_transaction_id": provider_transaction_id},
                )

            # Map PayPlus status to internal status
            # TODO: Verify all possible status values during sandbox testing
            status_mapping = {
                "completed": "completed",
                "failed": "failed",
                "refunded": "refunded",
                "pending": "pending",
            }
            status = status_mapping.get(payplus_status.lower())
            if not status:
                logger.warning(
                    "payplus_unknown_status",
                    payplus_status=payplus_status,
                    provider_transaction_id=provider_transaction_id,
                )
                # Default to failed for unknown statuses
                status = "failed"

            # Extract amount
            amount = payload.get("amount")
            if amount is None:
                raise PaymentProviderError(
                    "PayPlus webhook missing amount field",
                    provider="payplus",
                    details={"provider_transaction_id": provider_transaction_id},
                )

            # Convert to Decimal for precision
            # TODO: Verify if amount is in ILS or agorot during sandbox testing
            amount_decimal = Decimal(str(amount))

            # Extract currency
            currency = payload.get("currency_code", "ILS")  # TODO: Verify field name

            # Extract timestamp
            completed_at = None
            completed_at_str = payload.get(
                "completed_at"
            )  # TODO: Verify field name and format
            if completed_at_str:
                try:
                    # TODO: Verify timestamp format during sandbox testing
                    # Assuming ISO 8601 format with timezone
                    completed_at = datetime.fromisoformat(
                        completed_at_str.replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError) as e:
                    logger.warning(
                        "payplus_invalid_timestamp",
                        completed_at_str=completed_at_str,
                        error=str(e),
                    )

            # Extract failure reason if present
            failure_reason = payload.get("error_message")  # TODO: Verify field name

            # Extract custom fields (metadata)
            metadata = payload.get("custom_fields")  # TODO: Verify field name

            logger.info(
                "payplus_webhook_parsed",
                provider_transaction_id=provider_transaction_id,
                status=status,
                amount=str(amount_decimal),
                currency=currency,
                has_metadata=bool(metadata),
            )

            return WebhookPaymentData(
                provider_transaction_id=provider_transaction_id,
                status=status,
                amount=amount_decimal,
                currency=currency,
                completed_at=completed_at,
                failure_reason=failure_reason,
                metadata=metadata,
            )

        except KeyError as e:
            logger.error(
                "payplus_webhook_parse_error",
                error=str(e),
                payload_keys=list(payload.keys()),
                exc_info=True,
            )
            raise PaymentProviderError(
                f"PayPlus webhook missing required field: {e}",
                provider="payplus",
                details={"payload_keys": list(payload.keys())},
            ) from e

        except Exception as e:
            logger.error(
                "payplus_webhook_unexpected_error",
                error=str(e),
                exc_info=True,
            )
            raise PaymentProviderError(
                f"Unexpected error parsing PayPlus webhook: {e}",
                provider="payplus",
                details={"error": str(e)},
            ) from e


# Register provider with factory at module import time
# This allows the factory to create PayPlusProvider instances by name
register_provider("payplus", PayPlusProvider)
