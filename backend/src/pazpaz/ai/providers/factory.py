"""
Provider factory for AI services.

This module provides factory functions to create provider instances
based on configuration settings.

Architecture:
- Factory pattern for runtime provider selection
- Configuration-driven instantiation (no code changes to switch providers)
- Singleton pattern for provider instances (reuse across requests)
- Lazy initialization (providers created on first use)

Benefits:
- Single source of truth for provider selection
- Easy to add new providers
- Testable with mock providers
- Thread-safe singleton implementation
"""

from functools import lru_cache

from pazpaz.ai.providers.base import ChatProvider, EmbeddingProvider
from pazpaz.ai.providers.cohere import CohereChatProvider, CohereEmbeddingProvider
from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    """
    Get embedding provider instance (singleton).

    Returns the configured embedding provider based on settings.
    Uses lru_cache to ensure only one instance is created.

    Returns:
        EmbeddingProvider instance

    Raises:
        ValueError: If provider is not configured or unsupported

    Example:
        >>> provider = get_embedding_provider()
        >>> embedding = await provider.embed_text("Patient reports pain")
    """
    provider_name = settings.ai_embedding_provider

    if provider_name == "cohere":
        logger.info(
            "embedding_provider_initialized",
            provider="cohere",
            model=settings.cohere_embed_model,
        )
        return CohereEmbeddingProvider()

    # Future providers can be added here:
    # elif provider_name == "openai":
    #     return OpenAIEmbeddingProvider()
    # elif provider_name == "azure":
    #     return AzureEmbeddingProvider()

    raise ValueError(
        f"Unsupported embedding provider: {provider_name}. Supported providers: cohere"
    )


@lru_cache(maxsize=1)
def get_chat_provider() -> ChatProvider:
    """
    Get chat/LLM provider instance (singleton).

    Returns the configured chat provider based on settings.
    Uses lru_cache to ensure only one instance is created.

    Returns:
        ChatProvider instance

    Raises:
        ValueError: If provider is not configured or unsupported

    Example:
        >>> provider = get_chat_provider()
        >>> messages = [ChatMessage(role="user", content="What is SOAP?")]
        >>> response = await provider.chat(messages)
    """
    provider_name = settings.ai_chat_provider

    if provider_name == "cohere":
        logger.info(
            "chat_provider_initialized",
            provider="cohere",
            model=settings.cohere_chat_model,
        )
        return CohereChatProvider()

    # Future providers can be added here:
    # elif provider_name == "openai":
    #     return OpenAIChatProvider()
    # elif provider_name == "anthropic":
    #     return AnthropicChatProvider()

    raise ValueError(
        f"Unsupported chat provider: {provider_name}. Supported providers: cohere"
    )


def clear_provider_cache():
    """
    Clear provider cache (for testing).

    This forces new provider instances to be created on next call.
    Useful for testing different provider configurations.

    Example:
        >>> clear_provider_cache()
        >>> # Next call to get_embedding_provider() creates new instance
    """
    get_embedding_provider.cache_clear()
    get_chat_provider.cache_clear()
    logger.info("provider_cache_cleared", message="Provider cache cleared")
