"""
Abstract base classes for AI providers (embeddings, chat, etc.).

This module defines provider interfaces to decouple the AI agent from
specific provider implementations (Cohere, OpenAI, Anthropic, etc.).

Architecture:
- Provider interfaces define contracts for embeddings and chat operations
- Concrete providers implement these interfaces for specific vendors
- Factory pattern enables runtime provider selection via configuration
- All providers must handle retries, timeouts, and error reporting

Benefits:
- Multi-provider support (switch between Cohere, OpenAI, etc. via config)
- Testability (mock providers for unit tests)
- Cost optimization (use cheapest provider for each operation)
- Vendor independence (avoid lock-in)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ChatMessage:
    """
    Chat message for multi-turn conversations.

    Attributes:
        role: Message role ("system", "user", "assistant")
        content: Message text content
    """

    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class ChatResponse:
    """
    Response from chat/LLM provider.

    Attributes:
        content: Generated response text
        model: Model used for generation
        tokens_used: Token consumption (input_tokens, output_tokens)
        finish_reason: Reason generation stopped ("stop", "length", "error")
    """

    content: str
    model: str
    tokens_used: dict[str, int] | None = None  # {"input": 100, "output": 50}
    finish_reason: str = "stop"  # "stop" | "length" | "error"


class EmbeddingProvider(ABC):
    """
    Abstract interface for embedding generation providers.

    Implementing providers must:
    - Support async operations (non-blocking)
    - Handle retries and timeouts internally
    - Return consistent vector dimensions
    - Emit Prometheus metrics
    - Raise EmbeddingError on failures

    Example implementations: CohereEmbeddingProvider, OpenAIEmbeddingProvider
    """

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text string.

        Args:
            text: Text to embed (max length provider-specific)

        Returns:
            Embedding vector (dimensions = embedding_dimensions property)

        Raises:
            EmbeddingError: If embedding generation fails

        Example:
            >>> provider = CohereEmbeddingProvider()
            >>> embedding = await provider.embed_text("Patient reports pain")
            >>> len(embedding)
            1536
        """
        pass

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts in a single batch.

        This is more efficient than calling embed_text() multiple times.
        Empty strings should return zero vectors.

        Args:
            texts: List of texts to embed (max batch size provider-specific)

        Returns:
            List of embedding vectors (same length as input)

        Raises:
            EmbeddingError: If embedding generation fails
            ValueError: If batch exceeds provider limits

        Example:
            >>> provider = CohereEmbeddingProvider()
            >>> embeddings = await provider.embed_texts(["Text 1", "Text 2"])
            >>> len(embeddings)
            2
        """
        pass

    @property
    @abstractmethod
    def embedding_dimensions(self) -> int:
        """
        Vector dimensions for this provider's embeddings.

        Returns:
            Embedding vector size (e.g., 1536 for Cohere embed-v4.0)

        Example:
            >>> provider = CohereEmbeddingProvider()
            >>> provider.embedding_dimensions
            1536
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """
        Model identifier for this provider.

        Returns:
            Model name (e.g., "embed-v4.0" for Cohere)

        Example:
            >>> provider = CohereEmbeddingProvider()
            >>> provider.model_name
            "embed-v4.0"
        """
        pass


class ChatProvider(ABC):
    """
    Abstract interface for chat/LLM providers.

    Implementing providers must:
    - Support async operations (non-blocking)
    - Handle retries and timeouts internally
    - Track token usage for cost analysis
    - Emit Prometheus metrics
    - Raise ChatError on failures

    Example implementations: CohereChatProvider, OpenAIChatProvider
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 1000,
    ) -> ChatResponse:
        """
        Generate chat completion from messages.

        Args:
            messages: List of chat messages (user, assistant turns)
            system_prompt: Optional system instructions
            temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative)
            max_tokens: Maximum tokens to generate

        Returns:
            ChatResponse with generated text and metadata

        Raises:
            ChatError: If chat generation fails
            ValueError: If messages or parameters invalid

        Example:
            >>> provider = CohereChatProvider()
            >>> messages = [ChatMessage(role="user", content="What is SOAP?")]
            >>> response = await provider.chat(
            ...     messages=messages,
            ...     system_prompt="You are a clinical documentation assistant.",
            ...     temperature=0.3,
            ... )
            >>> response.content
            "SOAP is a documentation format..."
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """
        Model identifier for this provider.

        Returns:
            Model name (e.g., "command-r-plus-08-2024" for Cohere)

        Example:
            >>> provider = CohereChatProvider()
            >>> provider.model_name
            "command-r-plus-08-2024"
        """
        pass

    @property
    @abstractmethod
    def max_context_length(self) -> int:
        """
        Maximum context length (tokens) for this provider.

        Returns:
            Maximum tokens (input + output) supported by model

        Example:
            >>> provider = CohereChatProvider()
            >>> provider.max_context_length
            128000
        """
        pass
