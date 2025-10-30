"""Payment provider factory for creating provider instances.

This module provides the factory function that instantiates the appropriate
payment provider implementation based on workspace configuration. The factory
handles decryption of provider credentials and validates provider configuration.

Architecture:
    1. Factory reads workspace.payment_provider (e.g., "payplus", "stripe")
    2. Factory decrypts workspace.payment_provider_config using PHI encryption
    3. Factory instantiates appropriate provider class with decrypted config
    4. Factory returns provider instance implementing PaymentProvider interface

Security:
    - Provider credentials are encrypted at rest in database (JSONB field)
    - Factory decrypts credentials using encryption_key from AWS Secrets Manager
    - Decrypted credentials exist only in memory during request processing
    - Provider instances are created per-request (no credential caching)

Usage:
    from pazpaz.payments.factory import get_payment_provider
    from pazpaz.models import Workspace

    # Get provider for workspace
    provider = get_payment_provider(workspace)

    # Create payment link
    response = await provider.create_payment_link(request)

    # Verify webhook
    is_valid = await provider.verify_webhook(payload, headers)
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from pazpaz.core.logging import get_logger
from pazpaz.payments.base import PaymentProvider
from pazpaz.payments.exceptions import (
    InvalidCredentialsError,
    ProviderNotConfiguredError,
)
from pazpaz.utils.encryption import decrypt_field_versioned

if TYPE_CHECKING:
    from pazpaz.models.workspace import Workspace

logger = get_logger(__name__)

# Registry of supported payment providers
# Format: {provider_name: provider_class}
# Provider implementations register themselves here
_PROVIDER_REGISTRY: dict[str, type[PaymentProvider]] = {}


def register_provider(name: str, provider_class: type[PaymentProvider]) -> None:
    """Register a payment provider implementation.

    This function adds a provider implementation to the global registry.
    Provider modules should call this at import time to register themselves.

    Args:
        name: Provider identifier (e.g., "payplus", "stripe", "meshulam")
        provider_class: Provider class extending PaymentProvider

    Raises:
        ValueError: If provider name already registered
        TypeError: If provider_class doesn't extend PaymentProvider

    Example:
        >>> from pazpaz.payments.base import PaymentProvider
        >>> from pazpaz.payments.factory import register_provider
        >>>
        >>> class PayPlusProvider(PaymentProvider):
        ...     # Implementation
        ...     pass
        >>>
        >>> register_provider("payplus", PayPlusProvider)
    """
    if not issubclass(provider_class, PaymentProvider):
        raise TypeError(
            f"Provider class {provider_class.__name__} must extend PaymentProvider"
        )

    if name in _PROVIDER_REGISTRY:
        logger.warning(
            "provider_already_registered",
            provider_name=name,
            existing_class=_PROVIDER_REGISTRY[name].__name__,
            new_class=provider_class.__name__,
            message="Overwriting existing provider registration",
        )

    _PROVIDER_REGISTRY[name] = provider_class
    logger.info(
        "provider_registered",
        provider_name=name,
        provider_class=provider_class.__name__,
    )


def get_registered_providers() -> dict[str, type[PaymentProvider]]:
    """Get all registered payment provider implementations.

    Returns:
        Dictionary mapping provider name to provider class

    Example:
        >>> providers = get_registered_providers()
        >>> print(providers.keys())
        dict_keys(['payplus', 'stripe', 'meshulam'])
    """
    return _PROVIDER_REGISTRY.copy()


def get_payment_provider(workspace: Workspace) -> PaymentProvider:
    """Create payment provider instance for workspace.

    This factory function:
    1. Validates workspace has payment provider configured
    2. Decrypts provider credentials from workspace.payment_provider_config
    3. Instantiates appropriate provider class with decrypted config
    4. Returns provider instance ready for use

    Args:
        workspace: Workspace model with payment_provider and payment_provider_config

    Returns:
        Payment provider instance implementing PaymentProvider interface

    Raises:
        ProviderNotConfiguredError: If payments not enabled or provider unknown
        InvalidCredentialsError: If credentials missing or decryption fails
        ValueError: If decryption fails or config format invalid

    Example:
        >>> from pazpaz.models import Workspace
        >>> from pazpaz.payments.factory import get_payment_provider
        >>>
        >>> # Workspace with PayPlus configured
        >>> workspace = Workspace(
        ...     id=uuid.uuid4(),
        ...     payment_provider="payplus",
        ...     payment_provider_config={
        ...         "data": "v1:base64_encrypted_credentials..."
        ...     }
        ... )
        >>>
        >>> provider = get_payment_provider(workspace)
        >>> print(type(provider).__name__)
        PayPlusProvider
        >>>
        >>> # Create payment link
        >>> response = await provider.create_payment_link(request)
    """
    # Validate payment provider configured
    if workspace.payment_provider is None:
        logger.warning(
            "payment_provider_not_configured",
            workspace_id=str(workspace.id),
            message="Workspace has no payment provider configured",
        )
        raise ProviderNotConfiguredError(
            "Payment provider not enabled for workspace. "
            "Configure payment provider in workspace settings.",
            details={"workspace_id": str(workspace.id)},
        )

    provider_name = workspace.payment_provider.lower()

    # Validate provider is supported
    if provider_name not in _PROVIDER_REGISTRY:
        logger.error(
            "unknown_payment_provider",
            provider_name=provider_name,
            workspace_id=str(workspace.id),
            available_providers=list(_PROVIDER_REGISTRY.keys()),
        )
        raise ProviderNotConfiguredError(
            f"Unknown payment provider: {provider_name}. "
            f"Supported providers: {', '.join(_PROVIDER_REGISTRY.keys())}",
            provider=provider_name,
            details={
                "workspace_id": str(workspace.id),
                "available_providers": list(_PROVIDER_REGISTRY.keys()),
            },
        )

    # Validate provider config exists
    if not workspace.payment_provider_config:
        logger.error(
            "payment_provider_config_missing",
            provider_name=provider_name,
            workspace_id=str(workspace.id),
        )
        raise InvalidCredentialsError(
            f"Payment provider configuration missing for {provider_name}. "
            "Configure API credentials in workspace settings.",
            provider=provider_name,
            details={"workspace_id": str(workspace.id)},
        )

    # Decrypt provider config
    try:
        # workspace.payment_provider_config is a JSONB field with format:
        # {"data": "v1:base64_encrypted_json_string"}
        encrypted_data = workspace.payment_provider_config.get("data")
        if not encrypted_data:
            raise InvalidCredentialsError(
                "Payment provider config missing 'data' field. "
                "Re-configure API credentials in workspace settings.",
                provider=provider_name,
                details={"workspace_id": str(workspace.id)},
            )

        # Decrypt using versioned encryption (supports key rotation)
        # decrypt_field_versioned auto-selects correct key from version prefix
        decrypted_json = decrypt_field_versioned(encrypted_data)

        if decrypted_json is None:
            raise InvalidCredentialsError(
                "Failed to decrypt payment provider credentials. "
                "Re-configure API credentials in workspace settings.",
                provider=provider_name,
                details={"workspace_id": str(workspace.id)},
            )

        # Parse decrypted JSON
        config = json.loads(decrypted_json)

        logger.info(
            "payment_provider_config_decrypted",
            provider_name=provider_name,
            workspace_id=str(workspace.id),
            config_keys=list(config.keys()),
        )

    except json.JSONDecodeError as e:
        logger.error(
            "payment_provider_config_invalid_json",
            provider_name=provider_name,
            workspace_id=str(workspace.id),
            error=str(e),
        )
        raise InvalidCredentialsError(
            "Payment provider configuration is corrupted. "
            "Re-configure API credentials in workspace settings.",
            provider=provider_name,
            details={"workspace_id": str(workspace.id), "error": str(e)},
        ) from e

    except Exception as e:
        logger.error(
            "payment_provider_config_decryption_failed",
            provider_name=provider_name,
            workspace_id=str(workspace.id),
            error=str(e),
            exc_info=True,
        )
        raise InvalidCredentialsError(
            f"Failed to decrypt payment provider credentials: {e}",
            provider=provider_name,
            details={"workspace_id": str(workspace.id), "error": str(e)},
        ) from e

    # Instantiate provider
    try:
        provider_class = _PROVIDER_REGISTRY[provider_name]
        provider = provider_class(config)

        logger.info(
            "payment_provider_instantiated",
            provider_name=provider_name,
            provider_class=provider_class.__name__,
            workspace_id=str(workspace.id),
        )

        return provider

    except Exception as e:
        logger.error(
            "payment_provider_instantiation_failed",
            provider_name=provider_name,
            workspace_id=str(workspace.id),
            error=str(e),
            exc_info=True,
        )
        raise InvalidCredentialsError(
            f"Failed to initialize payment provider: {e}",
            provider=provider_name,
            details={"workspace_id": str(workspace.id), "error": str(e)},
        ) from e
