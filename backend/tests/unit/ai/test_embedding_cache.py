"""Unit tests for L2 embedding cache in EmbeddingService."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.asyncio import Redis

from pazpaz.ai.embeddings import EmbeddingService, get_embedding_cache_key


class TestEmbeddingCacheKey:
    """Test cache key generation for embeddings."""

    def test_get_embedding_cache_key_generates_consistent_keys(self):
        """Test that same text generates same cache key."""
        text1 = "Patient reports lower back pain"
        text2 = "Patient reports lower back pain"

        key1 = get_embedding_cache_key(text1)
        key2 = get_embedding_cache_key(text2)

        assert key1 == key2
        assert key1.startswith("ai:embedding:")

    def test_get_embedding_cache_key_normalizes_text(self):
        """Test that cache key normalizes text (case, whitespace)."""
        text1 = "Patient Reports LOWER BACK PAIN"
        text2 = "  patient reports lower back pain  "

        key1 = get_embedding_cache_key(text1)
        key2 = get_embedding_cache_key(text2)

        # Should generate same key after normalization
        assert key1 == key2

    def test_get_embedding_cache_key_different_texts_different_keys(self):
        """Test that different texts generate different cache keys."""
        text1 = "Patient reports lower back pain"
        text2 = "Patient reports shoulder pain"

        key1 = get_embedding_cache_key(text1)
        key2 = get_embedding_cache_key(text2)

        assert key1 != key2


@pytest.mark.asyncio
class TestEmbeddingServiceL2Cache:
    """Test suite for L2 embedding cache functionality."""

    @pytest.fixture
    def mock_cohere_client(self):
        """Mock Cohere client for embedding generation."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        # Simulate Cohere v2 response structure
        mock_response.embeddings = [[0.1] * 1536]  # 1536-dim embedding
        mock_client.embed = AsyncMock(return_value=mock_response)
        return mock_client

    @pytest.fixture
    async def embedding_service_with_cache(self, redis_client):
        """Create EmbeddingService with Redis cache."""
        service = EmbeddingService(
            api_key="test-api-key",
            input_type="search_document",
            redis=redis_client,
        )
        yield service
        # Cleanup: flush all test keys
        await redis_client.flushdb()

    async def test_embed_text_cache_miss_generates_and_stores_embedding(
        self,
        embedding_service_with_cache,
        redis_client,
        mock_cohere_client,
    ):
        """Test that cache miss generates embedding and stores in cache."""
        # Replace Cohere client with mock
        embedding_service_with_cache.cohere_client = mock_cohere_client

        text = "Patient reports lower back pain"
        cache_key = get_embedding_cache_key(text)

        # Ensure cache is empty
        await redis_client.delete(cache_key)

        # Call embed_text (should be cache miss)
        embedding = await embedding_service_with_cache.embed_text(text)

        # Verify embedding was generated
        assert len(embedding) == 1536
        assert embedding == [0.1] * 1536

        # Verify Cohere API was called
        mock_cohere_client.embed.assert_called_once()

        # Verify result was cached
        cached_value = await redis_client.get(cache_key)
        assert cached_value is not None

        cached_data = json.loads(cached_value)
        assert cached_data["embedding"] == embedding
        assert cached_data["model"] == "embed-multilingual-v4.0"
        assert cached_data["cache_version"] == "v1"

        # Verify TTL is set (1 hour = 3600 seconds)
        ttl = await redis_client.ttl(cache_key)
        assert 3500 < ttl <= 3600  # Allow small margin

    async def test_embed_text_cache_hit_returns_cached_embedding(
        self,
        embedding_service_with_cache,
        redis_client,
        mock_cohere_client,
    ):
        """Test that cache hit returns cached embedding without calling API."""
        # Replace Cohere client with mock
        embedding_service_with_cache.cohere_client = mock_cohere_client

        text = "Patient reports shoulder pain"
        cache_key = get_embedding_cache_key(text)

        # Pre-populate cache
        cached_embedding = [0.5] * 1536
        cache_value = json.dumps(
            {
                "embedding": cached_embedding,
                "model": "embed-multilingual-v4.0",
                "created_at": 1234567890,
                "cache_version": "v1",
            }
        )
        await redis_client.setex(cache_key, 3600, cache_value)

        # Call embed_text (should be cache hit)
        embedding = await embedding_service_with_cache.embed_text(text)

        # Verify cached embedding was returned
        assert embedding == cached_embedding

        # Verify Cohere API was NOT called
        mock_cohere_client.embed.assert_not_called()

    async def test_embed_text_cache_disabled_always_calls_api(
        self,
        embedding_service_with_cache,
        redis_client,
        mock_cohere_client,
    ):
        """Test that use_cache=False always calls API."""
        # Replace Cohere client with mock
        embedding_service_with_cache.cohere_client = mock_cohere_client

        text = "Patient reports knee pain"
        cache_key = get_embedding_cache_key(text)

        # Pre-populate cache
        cached_embedding = [0.5] * 1536
        cache_value = json.dumps(
            {
                "embedding": cached_embedding,
                "model": "embed-multilingual-v4.0",
                "created_at": 1234567890,
                "cache_version": "v1",
            }
        )
        await redis_client.setex(cache_key, 3600, cache_value)

        # Call embed_text with use_cache=False
        embedding = await embedding_service_with_cache.embed_text(text, use_cache=False)

        # Verify API embedding was returned (not cached)
        assert embedding == [0.1] * 1536  # Mock returns [0.1] * 1536

        # Verify Cohere API WAS called despite cache
        mock_cohere_client.embed.assert_called_once()

    async def test_embed_text_without_redis_falls_back_to_api(
        self,
        mock_cohere_client,
    ):
        """Test that service works without Redis (no cache)."""
        # Create service WITHOUT Redis
        service = EmbeddingService(
            api_key="test-api-key",
            input_type="search_document",
            redis=None,  # No Redis
        )
        service.cohere_client = mock_cohere_client

        text = "Patient reports elbow pain"

        # Call embed_text (should go straight to API)
        embedding = await service.embed_text(text)

        # Verify embedding was generated
        assert embedding == [0.1] * 1536

        # Verify Cohere API was called
        mock_cohere_client.embed.assert_called_once()

    async def test_embed_text_empty_text_returns_zero_vector(
        self,
        embedding_service_with_cache,
        mock_cohere_client,
    ):
        """Test that empty text returns zero vector without caching."""
        embedding_service_with_cache.cohere_client = mock_cohere_client

        # Test empty string
        embedding = await embedding_service_with_cache.embed_text("")
        assert embedding == [0.0] * 1536

        # Test whitespace only
        embedding = await embedding_service_with_cache.embed_text("   ")
        assert embedding == [0.0] * 1536

        # Verify Cohere API was NOT called
        mock_cohere_client.embed.assert_not_called()

    async def test_embed_text_cache_error_falls_back_to_api(
        self,
        mock_cohere_client,
    ):
        """Test that cache errors don't break embedding generation."""
        # Create Redis client that will raise errors
        mock_redis = AsyncMock(spec=Redis)
        mock_redis.get = AsyncMock(side_effect=Exception("Redis connection error"))
        mock_redis.setex = AsyncMock(side_effect=Exception("Redis connection error"))

        service = EmbeddingService(
            api_key="test-api-key",
            input_type="search_document",
            redis=mock_redis,
        )
        service.cohere_client = mock_cohere_client

        text = "Patient reports wrist pain"

        # Should not raise exception, should fallback to API
        embedding = await service.embed_text(text)

        # Verify embedding was generated
        assert embedding == [0.1] * 1536

        # Verify Cohere API was called
        mock_cohere_client.embed.assert_called_once()
