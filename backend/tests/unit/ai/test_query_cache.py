"""Unit tests for L1 query result cache in ClinicalAgent."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.ai.agent import (
    AgentResponse,
    ClinicalAgent,
    SessionCitation,
    get_query_cache_key,
)


class TestQueryCacheKey:
    """Test cache key generation for query results."""

    def test_get_query_cache_key_generates_consistent_keys(self):
        """Test that same query generates same cache key."""
        workspace_id = uuid.uuid4()
        query1 = "What is the patient's back pain history?"
        query2 = "What is the patient's back pain history?"

        key1 = get_query_cache_key(workspace_id, query1, None)
        key2 = get_query_cache_key(workspace_id, query2, None)

        assert key1 == key2
        assert key1.startswith(f"ai:query:{workspace_id}:")

    def test_get_query_cache_key_normalizes_query(self):
        """Test that cache key normalizes query text."""
        workspace_id = uuid.uuid4()
        query1 = "What is the patient's BACK PAIN history?"
        query2 = "  what is the patient's back pain history?  "

        key1 = get_query_cache_key(workspace_id, query1, None)
        key2 = get_query_cache_key(workspace_id, query2, None)

        # Should generate same key after normalization
        assert key1 == key2

    def test_get_query_cache_key_different_queries_different_keys(self):
        """Test that different queries generate different cache keys."""
        workspace_id = uuid.uuid4()
        query1 = "What is the patient's back pain history?"
        query2 = "What is the patient's shoulder pain history?"

        key1 = get_query_cache_key(workspace_id, query1, None)
        key2 = get_query_cache_key(workspace_id, query2, None)

        assert key1 != key2

    def test_get_query_cache_key_different_workspaces_different_keys(self):
        """Test that same query in different workspaces generates different keys."""
        workspace_id1 = uuid.uuid4()
        workspace_id2 = uuid.uuid4()
        query = "What is the patient's back pain history?"

        key1 = get_query_cache_key(workspace_id1, query, None)
        key2 = get_query_cache_key(workspace_id2, query, None)

        assert key1 != key2

    def test_get_query_cache_key_with_client_id(self):
        """Test that client_id is included in cache key."""
        workspace_id = uuid.uuid4()
        client_id = uuid.uuid4()
        query = "What is the patient's back pain history?"

        key_with_client = get_query_cache_key(workspace_id, query, client_id)
        key_without_client = get_query_cache_key(workspace_id, query, None)

        assert key_with_client != key_without_client
        assert str(client_id) in key_with_client
        assert str(client_id) not in key_without_client


@pytest.mark.asyncio
class TestClinicalAgentL1Cache:
    """Test suite for L1 query result cache functionality."""

    @pytest.fixture
    def mock_db(self):
        """Mock database session."""
        return MagicMock(spec=AsyncSession)

    @pytest.fixture
    def mock_retrieval_service(self):
        """Mock retrieval service."""
        mock = MagicMock()
        mock.retrieve_relevant_sessions = AsyncMock(return_value=([], []))
        return mock

    @pytest.fixture
    def mock_cohere_client(self):
        """Mock Cohere client."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.message.content = [MagicMock(text="Based on session notes...")]
        mock_response.usage = None
        mock_client.chat = AsyncMock(return_value=mock_response)
        return mock_client

    @pytest.fixture
    async def agent_with_cache(self, mock_db, redis_client):
        """Create ClinicalAgent with Redis cache."""
        agent = ClinicalAgent(
            db=mock_db,
            cohere_api_key="test-api-key",
            redis=redis_client,
        )
        yield agent

    async def test_query_cache_miss_processes_query_and_stores_result(
        self,
        agent_with_cache,
        redis_client,
        mock_cohere_client,
        mock_retrieval_service,
    ):
        """Test that cache miss processes query and stores result."""
        # Setup mocks
        agent_with_cache.cohere_client = mock_cohere_client
        agent_with_cache.retrieval_service = mock_retrieval_service

        workspace_id = uuid.uuid4()
        query = "What is the patient's back pain history?"

        # Ensure cache is empty
        cache_key = get_query_cache_key(workspace_id, query, None)
        await redis_client.delete(cache_key)

        # Execute query (should be cache miss)
        response = await agent_with_cache.query(
            workspace_id=workspace_id,
            query=query,
            max_results=5,
        )

        # Verify response was generated
        assert isinstance(response, AgentResponse)
        assert response.answer == "Based on session notes..."
        assert response.language in ["en", "he"]

        # Verify Cohere API was called
        mock_cohere_client.chat.assert_called_once()

        # Verify result was cached
        cached_value = await redis_client.get(cache_key)
        assert cached_value is not None

        cached_data = json.loads(cached_value)
        assert cached_data["answer"] == response.answer
        assert cached_data["language"] == response.language
        assert cached_data["cache_version"] == "v1"

        # Verify TTL is set (5 minutes = 300 seconds)
        ttl = await redis_client.ttl(cache_key)
        assert 250 < ttl <= 300  # Allow margin

    async def test_query_cache_hit_returns_cached_result(
        self,
        agent_with_cache,
        redis_client,
        mock_cohere_client,
    ):
        """Test that cache hit returns cached result without processing."""
        # Setup mocks
        agent_with_cache.cohere_client = mock_cohere_client

        workspace_id = uuid.uuid4()
        client_id = uuid.uuid4()
        session_id = uuid.uuid4()
        query = "What is the patient's shoulder pain history?"

        # Pre-populate cache
        cache_key = get_query_cache_key(workspace_id, query, client_id)
        cached_response = {
            "answer": "Cached answer about shoulder pain",
            "citations": [
                {
                    "session_id": str(session_id),
                    "client_name": "John Doe",
                    "session_date": "2025-01-01T10:00:00",
                    "similarity": 0.85,
                    "field_name": "subjective",
                }
            ],
            "language": "en",
            "retrieved_count": 1,
            "cached_at": 1234567890,
            "cache_version": "v1",
        }
        await redis_client.setex(cache_key, 300, json.dumps(cached_response))

        # Execute query (should be cache hit)
        response = await agent_with_cache.query(
            workspace_id=workspace_id,
            query=query,
            client_id=client_id,
            max_results=5,
        )

        # Verify cached response was returned
        assert response.answer == "Cached answer about shoulder pain"
        assert response.language == "en"
        assert response.retrieved_count == 1
        assert len(response.citations) == 1
        assert isinstance(response.citations[0], SessionCitation)
        assert response.citations[0].session_id == session_id

        # Verify Cohere API was NOT called (cache hit)
        mock_cohere_client.chat.assert_not_called()

    async def test_query_without_redis_works_normally(
        self,
        mock_db,
        mock_cohere_client,
        mock_retrieval_service,
    ):
        """Test that agent works without Redis (no cache)."""
        # Create agent WITHOUT Redis
        agent = ClinicalAgent(
            db=mock_db,
            cohere_api_key="test-api-key",
            redis=None,  # No Redis
        )
        agent.cohere_client = mock_cohere_client
        agent.retrieval_service = mock_retrieval_service

        workspace_id = uuid.uuid4()
        query = "What is the patient's knee pain history?"

        # Execute query (should process normally without cache)
        response = await agent.query(
            workspace_id=workspace_id,
            query=query,
            max_results=5,
        )

        # Verify response was generated
        assert isinstance(response, AgentResponse)
        assert response.answer == "Based on session notes..."

        # Verify Cohere API was called
        mock_cohere_client.chat.assert_called_once()

    async def test_query_cache_error_falls_back_to_processing(
        self,
        mock_db,
        mock_cohere_client,
        mock_retrieval_service,
    ):
        """Test that cache errors don't break query processing."""
        # Create Redis client that will raise errors
        mock_redis = AsyncMock(spec=Redis)
        mock_redis.get = AsyncMock(side_effect=Exception("Redis connection error"))
        mock_redis.setex = AsyncMock(side_effect=Exception("Redis connection error"))

        agent = ClinicalAgent(
            db=mock_db,
            cohere_api_key="test-api-key",
            redis=mock_redis,
        )
        agent.cohere_client = mock_cohere_client
        agent.retrieval_service = mock_retrieval_service

        workspace_id = uuid.uuid4()
        query = "What is the patient's ankle pain history?"

        # Should not raise exception, should fallback to normal processing
        response = await agent.query(
            workspace_id=workspace_id,
            query=query,
            max_results=5,
        )

        # Verify response was generated
        assert isinstance(response, AgentResponse)
        assert response.answer == "Based on session notes..."

        # Verify Cohere API was called
        mock_cohere_client.chat.assert_called_once()

    async def test_query_cache_key_includes_client_id(
        self,
        agent_with_cache,
        redis_client,
        mock_cohere_client,
        mock_retrieval_service,
    ):
        """Test that client-scoped queries use different cache keys."""
        agent_with_cache.cohere_client = mock_cohere_client
        agent_with_cache.retrieval_service = mock_retrieval_service

        workspace_id = uuid.uuid4()
        client_id_1 = uuid.uuid4()
        client_id_2 = uuid.uuid4()
        query = "What is the patient's back pain history?"

        # Query for client 1
        response1 = await agent_with_cache.query(
            workspace_id=workspace_id,
            query=query,
            client_id=client_id_1,
            max_results=5,
        )

        # Query for client 2 (same query, different client)
        response2 = await agent_with_cache.query(
            workspace_id=workspace_id,
            query=query,
            client_id=client_id_2,
            max_results=5,
        )

        # Verify both were processed (not cached from each other)
        assert mock_cohere_client.chat.call_count == 2

        # Verify different cache keys were used
        key1 = get_query_cache_key(workspace_id, query, client_id_1)
        key2 = get_query_cache_key(workspace_id, query, client_id_2)

        assert key1 != key2

        cached1 = await redis_client.get(key1)
        cached2 = await redis_client.get(key2)

        assert cached1 is not None
        assert cached2 is not None
