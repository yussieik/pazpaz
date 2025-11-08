"""
Cohere AI provider implementations.

This module implements the provider interfaces for Cohere's APIs:
- CohereEmbeddingProvider: Wraps Cohere embed-v4.0 model
- CohereChatProvider: Wraps Cohere command-r-plus model

Architecture:
- Implements EmbeddingProvider and ChatProvider abstract interfaces
- Handles retries, timeouts, and circuit breakers internally
- Emits Prometheus metrics for monitoring
- Raises provider-specific errors with context

Benefits:
- Encapsulates all Cohere-specific logic
- Can be swapped for other providers via factory
- Consistent error handling and retry behavior
"""

import time

import cohere
import httpx
from cohere.core.api_error import ApiError

from pazpaz.ai.metrics import (
    ai_agent_embedding_duration_seconds,
    ai_agent_embedding_errors_total,
    ai_agent_llm_duration_seconds,
    ai_agent_llm_errors_total,
    ai_agent_llm_tokens_total,
)
from pazpaz.ai.providers.base import (
    ChatMessage,
    ChatProvider,
    ChatResponse,
    EmbeddingProvider,
)
from pazpaz.ai.retry_policy import retry_with_backoff
from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingError(Exception):
    """Exception raised when embedding generation fails."""

    pass


class ChatError(Exception):
    """Exception raised when chat generation fails."""

    pass


class CohereEmbeddingProvider(EmbeddingProvider):
    """
    Cohere embedding provider using embed-v4.0 model.

    Features:
    - 1536-dimensional embeddings
    - Multilingual support (100+ languages including Hebrew)
    - Optimized for semantic search and RAG
    - Batch embedding support (up to 96 texts)
    - Automatic retry with exponential backoff
    - Circuit breaker for fault tolerance

    Example:
        >>> provider = CohereEmbeddingProvider()
        >>> embedding = await provider.embed_text("Patient reports back pain")
        >>> len(embedding)
        1536
    """

    def __init__(self, api_key: str | None = None):
        """
        Initialize Cohere embedding provider.

        Args:
            api_key: Cohere API key (defaults to settings.cohere_api_key)

        Raises:
            ValueError: If API key is not provided and not in settings
        """
        api_key = api_key or settings.cohere_api_key
        if not api_key:
            raise ValueError(
                "Cohere API key not configured. Set COHERE_API_KEY environment variable."
            )

        # Configure timeout for Cohere API calls
        timeout = httpx.Timeout(
            connect=5.0,
            read=settings.cohere_embed_timeout_seconds,
            write=5.0,
            pool=5.0,
        )

        # Use Cohere v2 API client (async)
        self.client = cohere.AsyncClientV2(api_key=api_key, timeout=timeout)
        self._model = settings.cohere_embed_model
        self.input_type = "search_document"  # For indexing documents

    @property
    def embedding_dimensions(self) -> int:
        """Return embedding dimensions for Cohere embed-v4.0 (1536)."""
        return 1536

    @property
    def model_name(self) -> str:
        """Return Cohere model name."""
        return self._model

    @retry_with_backoff(
        max_retries=3,
        base_delay=1.0,
        max_delay=32.0,
        exponential_base=2,
        jitter_factor=0.1,
        retryable_exceptions=(
            ApiError,
            httpx.HTTPStatusError,
            httpx.TimeoutException,
        ),
        circuit_breaker_name="cohere_embed",
        circuit_breaker_threshold=5,
        circuit_breaker_timeout=60.0,
    )
    async def _embed_with_retry(self, texts: list[str]) -> list[list[float]]:
        """
        Internal method: Call Cohere API with retry logic.

        Args:
            texts: Non-empty texts to embed (already filtered)

        Returns:
            List of embedding vectors (1536 dimensions each)

        Raises:
            ApiError: If Cohere API returns an error
            httpx.HTTPStatusError: If HTTP request fails
            httpx.TimeoutException: If request times out
        """
        start_time = time.time()

        response = await self.client.embed(
            texts=texts,
            model=self._model,
            input_type=self.input_type,
            embedding_types=["float"],
        )

        # Extract embeddings from response
        embeddings = response.embeddings.float

        # Emit timing metric
        duration = time.time() - start_time
        ai_agent_embedding_duration_seconds.labels(model=self._model).observe(duration)

        logger.info(
            "embeddings_generated",
            texts_count=len(texts),
            embedding_dim=len(embeddings[0]) if embeddings else 0,
            model=self._model,
            duration_seconds=duration,
        )

        return embeddings

    async def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text string.

        Args:
            text: Text to embed

        Returns:
            Embedding vector (1536 dimensions)

        Raises:
            EmbeddingError: If embedding generation fails
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            logger.warning(
                "empty_text_embedding",
                message="Embedding empty text, returning zero vector",
            )
            return [0.0] * self.embedding_dimensions

        try:
            embeddings = await self._embed_with_retry([text])
            return embeddings[0]

        except ApiError as e:
            # Emit error metric
            ai_agent_embedding_errors_total.labels(
                error_type="api_error",
                model=self._model,
            ).inc()

            logger.error(
                "cohere_api_error",
                error=str(e),
                status_code=getattr(e, "status_code", None),
                message="Cohere API returned an error",
            )
            raise EmbeddingError(f"Cohere API error: {e}") from e

        except Exception as e:
            # Emit error metric
            ai_agent_embedding_errors_total.labels(
                error_type=type(e).__name__,
                model=self._model,
            ).inc()

            logger.error(
                "embedding_generation_error",
                error=str(e),
                error_type=type(e).__name__,
                message="Unexpected error during embedding generation",
            )
            raise EmbeddingError(f"Failed to generate embedding: {e}") from e

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts in a single batch.

        Args:
            texts: List of texts to embed (max 96 texts)

        Returns:
            List of embedding vectors (1536 dimensions each)

        Raises:
            EmbeddingError: If embedding generation fails
            ValueError: If batch exceeds 96 texts
        """
        if not texts:
            logger.warning(
                "empty_texts_list", message="embed_texts called with empty list"
            )
            return []

        # Filter out empty strings and track original indices
        non_empty_texts = []
        non_empty_indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                non_empty_texts.append(text)
                non_empty_indices.append(i)

        # If all texts are empty, return zero vectors
        if not non_empty_texts:
            logger.warning(
                "all_texts_empty",
                count=len(texts),
                message="All texts are empty, returning zero vectors",
            )
            return [[0.0] * self.embedding_dimensions for _ in texts]

        # Cohere API limit is 96 texts per call
        if len(non_empty_texts) > 96:
            raise ValueError(
                f"Cohere API supports max 96 texts per call, got {len(non_empty_texts)}"
            )

        try:
            embeddings_result = await self._embed_with_retry(non_empty_texts)

            # Reconstruct full embeddings list with zero vectors for empty texts
            full_embeddings = []
            non_empty_idx = 0

            for i in range(len(texts)):
                if i in non_empty_indices:
                    full_embeddings.append(embeddings_result[non_empty_idx])
                    non_empty_idx += 1
                else:
                    # Empty text → zero vector
                    full_embeddings.append([0.0] * self.embedding_dimensions)

            return full_embeddings

        except ApiError as e:
            # Emit error metric
            ai_agent_embedding_errors_total.labels(
                error_type="api_error",
                model=self._model,
            ).inc()

            logger.error(
                "cohere_api_error_batch",
                error=str(e),
                status_code=getattr(e, "status_code", None),
                texts_count=len(non_empty_texts),
                message="Cohere API returned an error for batch embedding",
            )
            raise EmbeddingError(f"Cohere API error: {e}") from e

        except Exception as e:
            # Emit error metric
            ai_agent_embedding_errors_total.labels(
                error_type=type(e).__name__,
                model=self._model,
            ).inc()

            logger.error(
                "batch_embedding_error",
                error=str(e),
                error_type=type(e).__name__,
                texts_count=len(texts),
                message="Unexpected error during batch embedding generation",
            )
            raise EmbeddingError(f"Failed to generate batch embeddings: {e}") from e


class CohereChatProvider(ChatProvider):
    """
    Cohere chat provider using command-r-plus model.

    Features:
    - 128K context window
    - Multilingual support (Hebrew, English, etc.)
    - Optimized for RAG and structured output
    - Automatic retry with exponential backoff
    - Circuit breaker for fault tolerance
    - Token usage tracking for cost analysis

    Example:
        >>> provider = CohereChatProvider()
        >>> messages = [ChatMessage(role="user", content="What is SOAP?")]
        >>> response = await provider.chat(
        ...     messages=messages,
        ...     system_prompt="You are a clinical documentation assistant.",
        ... )
        >>> response.content
        "SOAP is a documentation format..."
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        """
        Initialize Cohere chat provider.

        Args:
            api_key: Cohere API key (defaults to settings.cohere_api_key)
            model: Model name (defaults to settings.cohere_chat_model)

        Raises:
            ValueError: If API key is not provided and not in settings
        """
        api_key = api_key or settings.cohere_api_key
        if not api_key:
            raise ValueError(
                "Cohere API key not configured. Set COHERE_API_KEY environment variable."
            )

        # Configure timeout for Cohere chat API calls
        timeout = httpx.Timeout(
            connect=5.0,
            read=settings.cohere_chat_timeout_seconds,
            write=5.0,
            pool=5.0,
        )

        # Use Cohere v2 API client (async)
        self.client = cohere.AsyncClientV2(api_key=api_key, timeout=timeout)
        self._model = model or settings.cohere_chat_model

    @property
    def model_name(self) -> str:
        """Return Cohere model name."""
        return self._model

    @property
    def max_context_length(self) -> int:
        """Return maximum context length for command-r-plus (128K tokens)."""
        return 128000

    @retry_with_backoff(
        max_retries=2,
        base_delay=1.0,
        max_delay=16.0,
        exponential_base=2,
        jitter_factor=0.1,
        retryable_exceptions=(
            ApiError,
            httpx.HTTPStatusError,
            httpx.TimeoutException,
        ),
        circuit_breaker_name="cohere_chat",
        circuit_breaker_threshold=5,
        circuit_breaker_timeout=60.0,
    )
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
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate

        Returns:
            ChatResponse with generated text and metadata

        Raises:
            ChatError: If chat generation fails
            ValueError: If messages or parameters invalid
        """
        if not messages:
            raise ValueError("Messages list cannot be empty")

        if temperature < 0.0 or temperature > 1.0:
            raise ValueError(f"Temperature must be 0.0-1.0, got {temperature}")

        if max_tokens < 1:
            raise ValueError(f"max_tokens must be >= 1, got {max_tokens}")

        try:
            start_time = time.time()

            # Build Cohere message format
            cohere_messages = []
            if system_prompt:
                cohere_messages.append({"role": "system", "content": system_prompt})

            for msg in messages:
                cohere_messages.append({"role": msg.role, "content": msg.content})

            # Call Cohere chat API
            response = await self.client.chat(
                model=self._model,
                messages=cohere_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Extract response content
            content = response.message.content[0].text

            # Extract token usage (if available)
            tokens_used = None
            if hasattr(response, "usage") and response.usage:
                tokens_used = {
                    "input": response.usage.tokens.input_tokens,
                    "output": response.usage.tokens.output_tokens,
                }

                # Emit token metrics
                ai_agent_llm_tokens_total.labels(
                    model=self._model,
                    token_type="input",
                ).inc(tokens_used["input"])

                ai_agent_llm_tokens_total.labels(
                    model=self._model,
                    token_type="output",
                ).inc(tokens_used["output"])

            # Emit timing metric
            duration = time.time() - start_time
            ai_agent_llm_duration_seconds.labels(model=self._model).observe(duration)

            logger.info(
                "chat_generated",
                model=self._model,
                input_tokens=tokens_used["input"] if tokens_used else None,
                output_tokens=tokens_used["output"] if tokens_used else None,
                duration_seconds=duration,
            )

            return ChatResponse(
                content=content,
                model=self._model,
                tokens_used=tokens_used,
                finish_reason="stop",
            )

        except ApiError as e:
            # Emit error metric
            ai_agent_llm_errors_total.labels(
                error_type="api_error",
                model=self._model,
            ).inc()

            logger.error(
                "cohere_chat_api_error",
                error=str(e),
                status_code=getattr(e, "status_code", None),
                message="Cohere chat API returned an error",
            )
            raise ChatError(f"Cohere chat API error: {e}") from e

        except Exception as e:
            # Emit error metric
            ai_agent_llm_errors_total.labels(
                error_type=type(e).__name__,
                model=self._model,
            ).inc()

            logger.error(
                "chat_generation_error",
                error=str(e),
                error_type=type(e).__name__,
                message="Unexpected error during chat generation",
            )
            raise ChatError(f"Failed to generate chat response: {e}") from e
