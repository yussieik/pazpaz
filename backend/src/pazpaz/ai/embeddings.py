"""
Embedding generation service using Cohere API.

This module provides a wrapper around Cohere's embed-v4.0 model
for generating vector embeddings of clinical data (SOAP notes, client profiles).

Model: embed-v4.0 (1536 dimensions)
- Latest best-in-class multilingual support (100+ languages including Hebrew)
- Optimized for semantic search and RAG
- HIPAA-compliant when BAA is signed with Cohere

Security:
- API key loaded from settings (environment variable)
- Rate limiting handled by application layer
- Embeddings contain semantic meaning (lossy transformation of PHI)
- No PHI stored in Cohere (ephemeral processing only)

Architecture:
- Async client (Cohere v2 API) to avoid blocking event loop
- All methods are async to support concurrent operations
- Proper error handling with retries (TODO: implement exponential backoff)
- Redis caching for embeddings (L2 cache) - 1 hour TTL
"""

import hashlib
import json
import time

import cohere
import httpx
from cohere.core.api_error import ApiError
from redis.asyncio import Redis

from pazpaz.ai.metrics import (
    ai_agent_cache_hits_total,
    ai_agent_cache_misses_total,
    ai_agent_embedding_duration_seconds,
    ai_agent_embedding_errors_total,
)
from pazpaz.ai.retry_policy import retry_with_backoff
from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


def get_embedding_cache_key(text: str) -> str:
    """
    Generate Redis cache key for text embedding.

    Args:
        text: Text to generate cache key for

    Returns:
        Redis key in format: ai:embedding:{text_hash}

    Example:
        >>> get_embedding_cache_key("Patient reports back pain")
        'ai:embedding:8f3d2c1a4b5e6f7g'
    """
    text_normalized = text.lower().strip()
    text_hash = hashlib.sha256(text_normalized.encode()).hexdigest()
    return f"ai:embedding:{text_hash}"


class EmbeddingError(Exception):
    """Exception raised when embedding generation fails."""

    pass


class EmbeddingService:
    """
    Service for generating vector embeddings using Cohere API.

    This service wraps the Cohere embed-multilingual-v3 model and provides
    a clean interface for embedding SOAP note fields.

    Attributes:
        client: Cohere API client
        model: Embedding model name
        input_type: Input type for embeddings (search_document for indexing)

    Example:
        >>> service = EmbeddingService()
        >>> embedding = await service.embed_text("Patient reports back pain")
        >>> len(embedding)
        1536
    """

    def __init__(
        self,
        api_key: str | None = None,
        input_type: str = "search_document",
        redis: Redis | None = None,
    ):
        """
        Initialize Cohere embedding service with async client.

        Args:
            api_key: Cohere API key (defaults to settings.cohere_api_key)
            input_type: Cohere input type - "search_document" for indexing, "search_query" for queries
            redis: Optional Redis client for caching embeddings (L2 cache)

        Raises:
            ValueError: If API key is not provided and not in settings
        """
        api_key = api_key or settings.cohere_api_key
        if not api_key:
            raise ValueError(
                "Cohere API key not configured. Set COHERE_API_KEY environment variable."
            )

        # Configure timeout for Cohere API calls (Phase 2.2)
        timeout = httpx.Timeout(
            connect=5.0,  # Time to establish connection
            read=settings.cohere_embed_timeout_seconds,  # Time to read response
            write=5.0,  # Time to send request
            pool=5.0,  # Time to acquire connection from pool
        )

        # Use Cohere v2 API client (async) to avoid blocking the event loop
        self.client = cohere.AsyncClientV2(api_key=api_key, timeout=timeout)
        self.model = settings.cohere_embed_model
        self.input_type = (
            input_type  # "search_document" for indexing, "search_query" for queries
        )
        self.redis = redis  # Optional Redis client for L2 caching

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
    async def _embed_text_with_retry(self, text: str) -> list[float]:
        """
        Internal method: Call Cohere API to embed text (with retry logic).

        This method is wrapped with retry logic and circuit breaker.
        Retries on transient failures (rate limits, timeouts, network errors).

        Args:
            text: Text to embed (non-empty, already validated)

        Returns:
            List of 1536 floats representing the embedding vector

        Raises:
            ApiError: If Cohere API returns an error
            httpx.HTTPStatusError: If HTTP request fails
            httpx.TimeoutException: If request times out
        """
        start_time = time.time()

        # Debug logging to verify parameters
        logger.debug(
            "cohere_embed_request",
            model=self.model,
            input_type=self.input_type,
            text_preview=text[:100] if len(text) > 100 else text,
            text_length=len(text),
        )

        response = await self.client.embed(
            model=self.model,
            input_type=self.input_type,
            texts=[text],
            embedding_types=["float"],
        )

        # Extract embedding from response
        # response.embeddings is EmbedResponse with float attribute
        embedding = response.embeddings.float[0]

        # Emit timing metric (Phase 2.3)
        duration = time.time() - start_time
        ai_agent_embedding_duration_seconds.labels(model=self.model).observe(duration)

        logger.info(
            "embedding_generated",
            text_length=len(text),
            embedding_dim=len(embedding),
            model=self.model,
            input_type=self.input_type,
            embedding_preview=embedding[:5],  # First 5 values for debugging
            duration_seconds=duration,
        )

        return embedding

    async def embed_text(self, text: str, use_cache: bool = True) -> list[float]:
        """
        Generate embedding for a single text string (async) with L2 caching.

        Args:
            text: Text to embed (SOAP note field content)
            use_cache: Whether to use Redis cache (default: True)

        Returns:
            List of 1536 floats representing the embedding vector

        Raises:
            EmbeddingError: If embedding generation fails

        Example:
            >>> service = EmbeddingService()
            >>> embedding = await service.embed_text("Patient reports headache")
            >>> len(embedding)
            1536
        """
        if not text or not text.strip():
            # Return zero vector for empty text
            logger.warning(
                "empty_text_embedding",
                message="Embedding empty text, returning zero vector",
            )
            return [0.0] * 1536

        # L2 Cache: Check Redis for cached embedding
        if use_cache and self.redis:
            cache_key = get_embedding_cache_key(text)

            try:
                cached = await self.redis.get(cache_key)
                if cached:
                    # Emit cache hit metric
                    ai_agent_cache_hits_total.labels(
                        workspace_id="global",  # Embeddings are workspace-agnostic
                        cache_layer="embedding",
                    ).inc()

                    logger.debug(
                        "embedding_cache_hit",
                        text_length=len(text),
                        cache_key=cache_key[:50],  # Truncate for logging
                    )

                    data = json.loads(cached)
                    return data["embedding"]

                # Cache miss
                ai_agent_cache_misses_total.labels(
                    workspace_id="global",
                    cache_layer="embedding",
                ).inc()

            except Exception as e:
                # Cache errors shouldn't break the request
                logger.warning(
                    "embedding_cache_error",
                    error=str(e),
                    error_type=type(e).__name__,
                    message="Failed to read from cache, generating fresh embedding",
                )

        # MISS: Generate embedding via Cohere API
        try:
            embedding = await self._embed_text_with_retry(text)

        except ApiError as e:
            # Emit error metric (Phase 2.3)
            ai_agent_embedding_errors_total.labels(
                error_type="api_error",
                model=self.model,
            ).inc()

            logger.error(
                "cohere_api_error",
                error=str(e),
                status_code=getattr(e, "status_code", None),
                message="Cohere API returned an error",
            )
            raise EmbeddingError(f"Cohere API error: {e}") from e

        except Exception as e:
            # Emit error metric (Phase 2.3)
            ai_agent_embedding_errors_total.labels(
                error_type=type(e).__name__,
                model=self.model,
            ).inc()

            logger.error(
                "embedding_generation_error",
                error=str(e),
                error_type=type(e).__name__,
                message="Unexpected error during embedding generation",
            )
            raise EmbeddingError(f"Failed to generate embedding: {e}") from e

        # Store in L2 cache
        if use_cache and self.redis:
            cache_key = get_embedding_cache_key(text)

            try:
                cache_value = json.dumps(
                    {
                        "embedding": embedding,
                        "model": self.model,
                        "created_at": int(time.time()),
                        "cache_version": "v1",
                    }
                )

                # TTL: 1 hour (3600 seconds)
                await self.redis.setex(cache_key, 3600, cache_value)

                logger.debug(
                    "embedding_cached",
                    text_length=len(text),
                    cache_key=cache_key[:50],
                    ttl_seconds=3600,
                )

            except Exception as e:
                # Cache errors shouldn't break the request
                logger.warning(
                    "embedding_cache_store_error",
                    error=str(e),
                    error_type=type(e).__name__,
                    message="Failed to store embedding in cache",
                )

        return embedding

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
    async def _embed_texts_with_retry(
        self, non_empty_texts: list[str]
    ) -> list[list[float]]:
        """
        Internal method: Call Cohere API to embed multiple texts (with retry logic).

        This method is wrapped with retry logic and circuit breaker.
        Retries on transient failures (rate limits, timeouts, network errors).

        Args:
            non_empty_texts: List of non-empty texts to embed (already filtered)

        Returns:
            List of embedding vectors (1536 dimensions each)

        Raises:
            ApiError: If Cohere API returns an error
            httpx.HTTPStatusError: If HTTP request fails
            httpx.TimeoutException: If request times out
        """
        start_time = time.time()

        # Debug logging to verify parameters
        logger.debug(
            "cohere_embed_batch_request",
            model=self.model,
            input_type=self.input_type,
            texts_count=len(non_empty_texts),
            first_text_preview=non_empty_texts[0][:100]
            if non_empty_texts and len(non_empty_texts[0]) > 100
            else (non_empty_texts[0] if non_empty_texts else ""),
        )

        response = await self.client.embed(
            model=self.model,
            input_type=self.input_type,
            texts=non_empty_texts,
            embedding_types=["float"],
        )

        # Extract embeddings from response
        embeddings_result = response.embeddings.float

        # Emit timing metric (Phase 2.3)
        duration = time.time() - start_time
        ai_agent_embedding_duration_seconds.labels(model=self.model).observe(duration)

        logger.info(
            "batch_embeddings_generated",
            texts_count=len(non_empty_texts),
            embedding_dim=len(embeddings_result[0]) if embeddings_result else 0,
            model=self.model,
            input_type=self.input_type,
            first_embedding_preview=embeddings_result[0][:5]
            if embeddings_result
            else [],
            duration_seconds=duration,
        )

        return embeddings_result

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts in a single API call (async).

        This is more efficient than calling embed_text() multiple times
        as it batches the requests to Cohere API.

        Args:
            texts: List of texts to embed (max 96 texts per call)

        Returns:
            List of embedding vectors (1536 dimensions each)

        Raises:
            EmbeddingError: If embedding generation fails
            ValueError: If texts list exceeds Cohere's batch limit

        Example:
            >>> service = EmbeddingService()
            >>> texts = ["Subjective note", "Objective note", "Assessment", "Plan"]
            >>> embeddings = await service.embed_texts(texts)
            >>> len(embeddings)
            4
            >>> len(embeddings[0])
            1536
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
            return [[0.0] * 1536 for _ in texts]

        # Cohere API limit is 96 texts per call
        if len(non_empty_texts) > 96:
            raise ValueError(
                f"Cohere API supports max 96 texts per call, got {len(non_empty_texts)}"
            )

        try:
            embeddings_result = await self._embed_texts_with_retry(non_empty_texts)

            # Reconstruct full embeddings list with zero vectors for empty texts
            full_embeddings = []
            non_empty_idx = 0

            for i in range(len(texts)):
                if i in non_empty_indices:
                    full_embeddings.append(embeddings_result[non_empty_idx])
                    non_empty_idx += 1
                else:
                    # Empty text → zero vector
                    full_embeddings.append([0.0] * 1536)

            return full_embeddings

        except ApiError as e:
            # Emit error metric (Phase 2.3)
            ai_agent_embedding_errors_total.labels(
                error_type="api_error",
                model=self.model,
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
            # Emit error metric (Phase 2.3)
            ai_agent_embedding_errors_total.labels(
                error_type=type(e).__name__,
                model=self.model,
            ).inc()

            logger.error(
                "batch_embedding_error",
                error=str(e),
                error_type=type(e).__name__,
                texts_count=len(texts),
                message="Unexpected error during batch embedding generation",
            )
            raise EmbeddingError(f"Failed to generate batch embeddings: {e}") from e

    async def embed_soap_fields(
        self,
        subjective: str | None,
        objective: str | None,
        assessment: str | None,
        plan: str | None,
    ) -> dict[str, list[float]]:
        """
        Generate embeddings for SOAP note fields (async).

        This is a convenience method that embeds all SOAP fields in a single
        batch API call, skipping empty fields.

        Args:
            subjective: Subjective field content (patient-reported)
            objective: Objective field content (therapist observations)
            assessment: Assessment field content (diagnosis)
            plan: Plan field content (treatment plan)

        Returns:
            Dictionary mapping field names to embedding vectors.
            Only non-empty fields are included in the result.

        Example:
            >>> service = EmbeddingService()
            >>> embeddings = await service.embed_soap_fields(
            ...     subjective="Patient reports pain",
            ...     objective="Reduced range of motion",
            ...     assessment="Acute strain",
            ...     plan="Rest and ice"
            ... )
            >>> set(embeddings.keys())
            {'subjective', 'objective', 'assessment', 'plan'}
        """
        # Build list of (field_name, text) tuples for non-empty fields
        fields = []
        field_names = []

        for field_name, text in [
            ("subjective", subjective),
            ("objective", objective),
            ("assessment", assessment),
            ("plan", plan),
        ]:
            if text and text.strip():
                fields.append(text)
                field_names.append(field_name)

        if not fields:
            logger.warning(
                "all_soap_fields_empty",
                message="All SOAP fields are empty, returning empty dict",
            )
            return {}

        # Generate embeddings in batch
        embeddings = await self.embed_texts(fields)

        # Map field names to embeddings
        result = dict(zip(field_names, embeddings, strict=True))

        logger.info(
            "soap_embeddings_generated",
            fields_embedded=list(result.keys()),
            count=len(result),
        )

        return result

    async def embed_client_fields(
        self,
        medical_history: str | None,
        notes: str | None,
    ) -> dict[str, list[float]]:
        """
        Generate embeddings for client profile fields (async).

        This is a convenience method that embeds client fields in a single
        batch API call, skipping empty fields.

        Args:
            medical_history: Client medical history content (PHI)
            notes: General therapist notes about the client

        Returns:
            Dictionary mapping field names to embedding vectors.
            Only non-empty fields are included in the result.

        Example:
            >>> service = EmbeddingService()
            >>> embeddings = await service.embed_client_fields(
            ...     medical_history="History of chronic back pain from car accident",
            ...     notes="Prefers morning appointments"
            ... )
            >>> set(embeddings.keys())
            {'medical_history', 'notes'}
        """
        # Build list of (field_name, text) tuples for non-empty fields
        fields = []
        field_names = []

        for field_name, text in [
            ("medical_history", medical_history),
            ("notes", notes),
        ]:
            if text and text.strip():
                fields.append(text)
                field_names.append(field_name)

        if not fields:
            logger.warning(
                "all_client_fields_empty",
                message="All client fields are empty, returning empty dict",
            )
            return {}

        # Generate embeddings in batch
        embeddings = await self.embed_texts(fields)

        # Map field names to embeddings
        result = dict(zip(field_names, embeddings, strict=True))

        logger.info(
            "client_embeddings_generated",
            fields_embedded=list(result.keys()),
            count=len(result),
        )

        return result


def get_embedding_service(
    input_type: str = "search_document", redis: Redis | None = None
) -> EmbeddingService:
    """
    Factory function to create an EmbeddingService instance.

    Args:
        input_type: Cohere input type - "search_document" for indexing, "search_query" for queries
        redis: Optional Redis client for L2 caching (default: None, no caching)

    Returns:
        Configured EmbeddingService instance

    Raises:
        ValueError: If Cohere API key is not configured

    Example:
        >>> service = get_embedding_service(input_type="search_query")
        >>> embedding = service.embed_text("Hello world")
    """
    return EmbeddingService(input_type=input_type, redis=redis)
