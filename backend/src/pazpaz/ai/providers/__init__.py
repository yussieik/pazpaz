"""
AI provider abstractions and implementations.

This package provides:
- Abstract base classes for embedding and chat providers
- Cohere provider implementations
- Factory functions for provider selection
- Configuration-driven provider instantiation

Usage:
    >>> from pazpaz.ai.providers import get_embedding_provider, get_chat_provider
    >>> embedding_provider = get_embedding_provider()
    >>> chat_provider = get_chat_provider()

    >>> # Use providers
    >>> embedding = await embedding_provider.embed_text("Patient reports pain")
    >>> response = await chat_provider.chat(messages=[...])

Architecture:
- Provider interfaces decouple AI agent from specific vendors
- Factory pattern enables runtime provider selection via configuration
- Singleton pattern ensures single instance per provider type
- All providers handle retries, timeouts, and metrics internally
"""

from pazpaz.ai.providers.base import (
    ChatMessage,
    ChatProvider,
    ChatResponse,
    EmbeddingProvider,
)
from pazpaz.ai.providers.cohere import (
    ChatError,
    CohereChatProvider,
    CohereEmbeddingProvider,
    EmbeddingError,
)
from pazpaz.ai.providers.factory import (
    clear_provider_cache,
    get_chat_provider,
    get_embedding_provider,
)

__all__ = [
    # Abstract base classes
    "EmbeddingProvider",
    "ChatProvider",
    "ChatMessage",
    "ChatResponse",
    # Cohere implementations
    "CohereEmbeddingProvider",
    "CohereChatProvider",
    # Exceptions
    "EmbeddingError",
    "ChatError",
    # Factory functions
    "get_embedding_provider",
    "get_chat_provider",
    "clear_provider_cache",
]
