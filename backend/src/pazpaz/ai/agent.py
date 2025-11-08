"""
Async LangGraph agent for RAG-based clinical documentation assistant.

This module implements the LangGraph agent that orchestrates:
1. Query processing and language detection
2. Semantic retrieval (via RetrievalService)
3. Context synthesis with LLM (via Cohere)
4. Response formatting with citations

Architecture:
- Fully async (matches FastAPI/AsyncSession architecture)
- Stateless (no conversation memory for HIPAA compliance)
- Workspace-scoped (multi-tenant isolation)
- Bilingual (Hebrew/English with auto-detection)

Security:
- No data retention (ephemeral processing only)
- PHI never logged (only session IDs for citations)
- Output filtering (token limits, basic PII redaction)
- Workspace isolation enforced throughout

Performance:
- Single LLM call per query
- Efficient retrieval with configurable limits
- Concurrent request support via async
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime

import cohere
import httpx
from cohere.core.api_error import ApiError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.ai.metrics import (
    ai_agent_cache_hits_total,
    ai_agent_cache_misses_total,
    ai_agent_citations_returned,
    ai_agent_llm_duration_seconds,
    ai_agent_llm_errors_total,
    ai_agent_llm_tokens_total,
    ai_agent_queries_total,
    ai_agent_query_duration_seconds,
    ai_agent_retrieval_duration_seconds,
    ai_agent_sources_retrieved,
)
from pazpaz.ai.prompts import (
    detect_language,
    get_context_format,
    get_error_message,
    get_no_results_message,
    get_synthesis_prompt,
    get_system_prompt,
)
from pazpaz.ai.query_expansion import expand_query
from pazpaz.ai.retrieval import ClientContext, SessionContext, get_retrieval_service
from pazpaz.ai.retry_policy import retry_with_backoff
from pazpaz.ai.search_config import compute_adaptive_threshold, should_expand_query
from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger
from pazpaz.models.audit_event import AuditAction, ResourceType
from pazpaz.services.audit_service import create_audit_event

logger = get_logger(__name__)


def get_query_cache_key(
    workspace_id: uuid.UUID,
    query: str,
    client_id: uuid.UUID | None,
) -> str:
    """
    Generate Redis cache key for query result.

    Args:
        workspace_id: Workspace ID for multi-tenant isolation
        query: User's query text
        client_id: Optional client ID for scoped queries

    Returns:
        Redis cache key (e.g., "ai:query:ws-id:hash:client-id")
    """
    query_normalized = query.lower().strip()
    query_hash = hashlib.sha256(query_normalized.encode()).hexdigest()[:16]
    client_suffix = f":{client_id}" if client_id else ""
    return f"ai:query:{workspace_id}:{query_hash}{client_suffix}"


class AgentError(Exception):
    """Exception raised when agent operations fail."""

    pass


@dataclass
class AgentResponse:
    """
    Structured response from the AI agent.

    Attributes:
        answer: The synthesized answer text
        citations: List of session citations referenced in the answer
        language: Detected language of the query ("he" or "en")
        retrieved_count: Number of sessions retrieved
        processing_time_ms: Total processing time in milliseconds

    Example:
        >>> response = AgentResponse(
        ...     answer="Based on session notes, the patient reported...",
        ...     citations=[
        ...         SessionCitation(
        ...             session_id=uuid.uuid4(),
        ...             client_id=uuid.uuid4(),
        ...             client_name="John Doe",
        ...             session_date=datetime.now(),
        ...             similarity=0.85,
        ...             field_name="subjective",
        ...         )
        ...     ],
        ...     language="en",
        ...     retrieved_count=3,
        ...     processing_time_ms=1250,
        ... )
    """

    answer: str
    citations: list[SessionCitation]
    language: str
    retrieved_count: int
    processing_time_ms: int


@dataclass
class SessionCitation:
    """
    Citation reference to a specific session.

    Attributes:
        session_id: UUID of the cited session
        client_id: UUID of the client (for navigation)
        client_name: Name of the client (for display)
        session_date: Date of the session
        similarity: Cosine similarity score (0.0 to 1.0)
        field_name: SOAP field that matched (subjective, objective, assessment, plan)
    """

    session_id: uuid.UUID
    client_id: uuid.UUID
    client_name: str
    session_date: datetime
    similarity: float
    field_name: str


@dataclass
class ClientCitation:
    """
    Citation reference to a client profile.

    Attributes:
        client_id: UUID of the client
        client_name: Name of the client (for display)
        similarity: Cosine similarity score (0.0 to 1.0)
        field_name: Client field that matched (medical_history, notes)
    """

    client_id: uuid.UUID
    client_name: str
    similarity: float
    field_name: str


class ClinicalAgent:
    """
    Async LangGraph agent for clinical documentation queries.

    This agent orchestrates the RAG pipeline:
    1. Detects query language (Hebrew/English)
    2. Retrieves relevant sessions via semantic search
    3. Formats context with retrieved SOAP notes
    4. Synthesizes answer using Cohere Command-R
    5. Extracts citations and filters output

    All operations are async and workspace-scoped.

    Example:
        >>> async with get_db_session() as db:
        ...     agent = ClinicalAgent(db)
        ...     response = await agent.query(
        ...         workspace_id=workspace_id,
        ...         query="What did we discuss about lower back pain?",
        ...         client_id=client_id,  # Optional: scope to specific client
        ...     )
        ...     print(response.answer)
        ...     for citation in response.citations:
        ...         print(f"  - {citation.client_name} ({citation.session_date})")
    """

    def __init__(
        self,
        db: AsyncSession,
        cohere_api_key: str | None = None,
        model: str | None = None,
        redis: Redis | None = None,
    ):
        """
        Initialize the clinical agent.

        Args:
            db: SQLAlchemy async session for database operations
            cohere_api_key: Cohere API key (defaults to settings.cohere_api_key)
            model: Cohere model to use (defaults to settings.cohere_chat_model)
            redis: Optional Redis client for L1 query result caching

        Raises:
            ValueError: If Cohere API key not provided
        """
        api_key = cohere_api_key or settings.cohere_api_key
        if not api_key:
            raise ValueError(
                "Cohere API key not configured. Set COHERE_API_KEY environment variable."
            )

        # Configure timeout for Cohere chat API calls (Phase 2.2)
        timeout = httpx.Timeout(
            connect=5.0,  # Time to establish connection
            read=settings.cohere_chat_timeout_seconds,  # Time to read response (longer for LLM)
            write=5.0,  # Time to send request
            pool=5.0,  # Time to acquire connection from pool
        )

        self.db = db
        # Use Cohere v2 API client (async) for LLM synthesis
        self.cohere_client = cohere.AsyncClientV2(api_key=api_key, timeout=timeout)
        self.model = model or settings.cohere_chat_model
        self.retrieval_service = get_retrieval_service(db)
        self.redis = redis

    async def query(
        self,
        workspace_id: uuid.UUID,
        query: str,
        user_id: uuid.UUID | None = None,
        client_id: uuid.UUID | None = None,
        max_results: int = 5,
        min_similarity: float = 0.7,
    ) -> AgentResponse:
        """
        Process a clinical documentation query and generate response.

        This is the main entry point for the agent. It orchestrates:
        1. Language detection
        2. Semantic retrieval
        3. Context formatting
        4. LLM synthesis
        5. Citation extraction
        6. Audit logging (if user_id provided)

        Args:
            workspace_id: Workspace ID (MANDATORY - multi-tenant isolation)
            query: Natural language query (Hebrew or English)
            user_id: User ID for audit logging (optional, recommended)
            client_id: Optional client ID to scope retrieval to specific patient
            max_results: Maximum sessions to retrieve (default: 5, max: 10)
            min_similarity: Minimum similarity threshold (default: 0.7)

        Returns:
            AgentResponse with answer, citations, and metadata

        Raises:
            AgentError: If query processing fails
            ValueError: If parameters are invalid

        Example:
            >>> response = await agent.query(
            ...     workspace_id=workspace_id,
            ...     query="מה היה הטיפול בכאבי גב?",  # Hebrew
            ...     user_id=current_user.id,
            ...     client_id=client_id,
            ...     max_results=5,
            ... )
        """
        start_time = time.time()

        # Validate parameters
        if max_results < 1 or max_results > 10:
            raise ValueError(f"Invalid max_results: {max_results}. Must be 1-10.")

        # Create query hash for correlation (SHA-256, first 16 chars)
        # Hashing prevents PHI leakage while allowing query correlation in logs
        query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]

        logger.info(
            "agent_query_started",
            workspace_id=str(workspace_id),
            query_hash=query_hash,
            query_length=len(query),
            client_id=str(client_id) if client_id else None,
            max_results=max_results,
        )

        # L1 Cache: Check for cached query result
        if self.redis:
            cache_key = get_query_cache_key(workspace_id, query, client_id)
            try:
                cached = await self.redis.get(cache_key)
                if cached:
                    # Cache hit - deserialize and return cached response
                    cache_data = json.loads(cached)

                    # Emit cache hit metric
                    ai_agent_cache_hits_total.labels(
                        workspace_id=str(workspace_id),
                        cache_layer="query_result",
                    ).inc()

                    processing_time = int((time.time() - start_time) * 1000)

                    logger.info(
                        "agent_query_cache_hit",
                        workspace_id=str(workspace_id),
                        query_hash=query_hash,
                        processing_time_ms=processing_time,
                        cached_at=cache_data.get("cached_at"),
                    )

                    # Reconstruct citations
                    citations = []
                    for citation_data in cache_data.get("citations", []):
                        if "session_id" in citation_data:
                            citations.append(
                                SessionCitation(
                                    session_id=uuid.UUID(citation_data["session_id"]),
                                    client_id=uuid.UUID(citation_data["client_id"]),
                                    client_name=citation_data["client_name"],
                                    session_date=datetime.fromisoformat(
                                        citation_data["session_date"]
                                    ),
                                    similarity=citation_data["similarity"],
                                    field_name=citation_data["field_name"],
                                )
                            )
                        else:
                            citations.append(
                                ClientCitation(
                                    client_id=uuid.UUID(citation_data["client_id"]),
                                    client_name=citation_data["client_name"],
                                    similarity=citation_data["similarity"],
                                    field_name=citation_data["field_name"],
                                )
                            )

                    return AgentResponse(
                        answer=cache_data["answer"],
                        citations=citations,
                        language=cache_data["language"],
                        retrieved_count=cache_data["retrieved_count"],
                        processing_time_ms=processing_time,
                    )

                # Cache miss
                ai_agent_cache_misses_total.labels(
                    workspace_id=str(workspace_id),
                    cache_layer="query_result",
                ).inc()

            except Exception as e:
                # Don't fail query if cache check fails
                logger.warning(
                    "query_cache_check_error",
                    workspace_id=str(workspace_id),
                    error=str(e),
                )

        try:
            # Step 1: Detect language
            language = detect_language(query)
            logger.debug(
                "language_detected",
                workspace_id=str(workspace_id),
                language=language,
            )

            # Step 1.5: Expand query with clinical terminology (if beneficial)
            expanded_query = query
            if should_expand_query(query):
                expanded_query = expand_query(query, language=language)
                logger.debug(
                    "query_expanded",
                    workspace_id=str(workspace_id),
                    original_length=len(query),
                    expanded_length=len(expanded_query),
                    expansion_added=len(expanded_query) - len(query),
                )

            # Step 1.6: Adjust similarity threshold for short/general queries
            # Uses centralized search configuration for adaptive threshold tuning
            # See: pazpaz/ai/search_config.py for tuning parameters
            adjusted_min_similarity = compute_adaptive_threshold(
                query=query,
                base_threshold=min_similarity,
            )

            if adjusted_min_similarity != min_similarity:
                logger.debug(
                    "threshold_adjusted_for_short_query",
                    workspace_id=str(workspace_id),
                    original_threshold=min_similarity,
                    adjusted_threshold=adjusted_min_similarity,
                    query_word_count=len(query.split()),
                )

            # Step 2: Retrieve relevant sessions and client contexts
            retrieval_start = time.time()
            if client_id:
                # Client-scoped query: sessions and client profile for this client
                (
                    session_contexts,
                    client_contexts,
                ) = await self.retrieval_service.retrieve_client_history(
                    workspace_id=workspace_id,
                    client_id=client_id,
                    query=expanded_query,  # Use expanded query for better retrieval
                    limit=max_results,
                    min_similarity=adjusted_min_similarity,  # Use adjusted threshold
                )
            else:
                # Workspace-wide query: both sessions and client contexts
                (
                    session_contexts,
                    client_contexts,
                ) = await self.retrieval_service.retrieve_relevant_sessions(
                    workspace_id=workspace_id,
                    query=expanded_query,  # Use expanded query for better retrieval
                    limit=max_results,
                    min_similarity=adjusted_min_similarity,  # Use adjusted threshold
                    include_client_context=True,
                )
            retrieval_duration = time.time() - retrieval_start

            # Combine contexts for unified processing
            total_sources = len(session_contexts) + len(client_contexts)

            # Track retrieval metrics
            ai_agent_retrieval_duration_seconds.observe(retrieval_duration)
            ai_agent_sources_retrieved.observe(total_sources)

            logger.info(
                "agent_retrieval_completed",
                workspace_id=str(workspace_id),
                query_hash=query_hash,
                sources_count=total_sources,
                session_count=len(session_contexts),
                client_count=len(client_contexts),
                retrieved_count=total_sources,  # Keep for backwards compatibility
                retrieval_duration_seconds=retrieval_duration,
            )

            # Step 3: Handle no results
            if not session_contexts and not client_contexts:
                processing_time = int((time.time() - start_time) * 1000)
                return AgentResponse(
                    answer=get_no_results_message(language),
                    citations=[],
                    language=language,
                    retrieved_count=0,
                    processing_time_ms=processing_time,
                )

            # Step 4: Format context for LLM
            formatted_context = self._format_context(
                session_contexts=session_contexts,
                client_contexts=client_contexts,
                language=language,
            )

            # Step 5: Synthesize answer with Cohere
            answer = await self._synthesize_answer(
                query=query,
                context=formatted_context,
                language=language,
            )

            # Step 6: Extract citations
            citations = self._extract_citations(
                session_contexts=session_contexts,
                client_contexts=client_contexts,
            )

            # Step 7: Filter output (basic PII redaction + token limits)
            filtered_answer = self._filter_output(answer, max_tokens=500)

            processing_time = int((time.time() - start_time) * 1000)
            processing_time_seconds = time.time() - start_time

            # Track overall query metrics
            ai_agent_queries_total.labels(
                workspace_id=str(workspace_id), language=language, status="success"
            ).inc()
            ai_agent_query_duration_seconds.labels(language=language).observe(
                processing_time_seconds
            )
            ai_agent_citations_returned.observe(len(citations))

            logger.info(
                "agent_query_completed",
                workspace_id=str(workspace_id),
                query_hash=query_hash,
                sources_count=total_sources,
                answer_length=len(filtered_answer),
                citations_count=len(citations),
                processing_time_ms=processing_time,
                language=language,
            )

            # Step 7.5: Store result in L1 cache
            if self.redis:
                try:
                    # Serialize citations
                    serialized_citations = []
                    for citation in citations:
                        if isinstance(citation, SessionCitation):
                            serialized_citations.append(
                                {
                                    "session_id": str(citation.session_id),
                                    "client_name": citation.client_name,
                                    "session_date": citation.session_date.isoformat(),
                                    "similarity": citation.similarity,
                                    "field_name": citation.field_name,
                                }
                            )
                        else:  # ClientCitation
                            serialized_citations.append(
                                {
                                    "client_id": str(citation.client_id),
                                    "client_name": citation.client_name,
                                    "similarity": citation.similarity,
                                    "field_name": citation.field_name,
                                }
                            )

                    cache_value = json.dumps(
                        {
                            "answer": filtered_answer,
                            "citations": serialized_citations,
                            "language": language,
                            "retrieved_count": total_sources,
                            "cached_at": int(time.time()),
                            "cache_version": "v1",
                        }
                    )

                    cache_key = get_query_cache_key(workspace_id, query, client_id)
                    await self.redis.setex(cache_key, 300, cache_value)  # 5 min TTL

                    logger.debug(
                        "query_result_cached",
                        workspace_id=str(workspace_id),
                        query_hash=query_hash,
                        cache_key=cache_key,
                    )

                except Exception as e:
                    # Don't fail query if cache storage fails
                    logger.warning(
                        "query_cache_store_error",
                        workspace_id=str(workspace_id),
                        error=str(e),
                    )

            # Step 8: Audit log (HIPAA compliance)
            if user_id:
                try:
                    await create_audit_event(
                        db=self.db,
                        user_id=user_id,
                        workspace_id=workspace_id,
                        action=AuditAction.READ,
                        resource_type=ResourceType.AI_AGENT,
                        resource_id=None,  # No specific resource (query is ephemeral)
                        metadata={
                            "query_hash": query_hash,
                            "query_length": len(query),
                            "language": language,
                            "sources_count": total_sources,
                            "retrieved_count": total_sources,  # Backwards compat
                            "citations_count": len(citations),
                            "processing_time_ms": processing_time,
                            "client_id": str(client_id) if client_id else None,
                            # Note: query text NOT logged (PHI risk)
                        },
                    )
                    logger.debug(
                        "agent_query_audited",
                        workspace_id=str(workspace_id),
                        user_id=str(user_id),
                    )
                except Exception as audit_error:
                    # Don't fail query if audit logging fails
                    logger.error(
                        "agent_audit_logging_failed",
                        workspace_id=str(workspace_id),
                        error=str(audit_error),
                        exc_info=True,
                    )

            return AgentResponse(
                answer=filtered_answer,
                citations=citations,
                language=language,
                retrieved_count=total_sources,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            language = detect_language(query)

            # Track failed query
            ai_agent_queries_total.labels(
                workspace_id=str(workspace_id), language=language, status="error"
            ).inc()

            logger.error(
                "agent_query_failed",
                workspace_id=str(workspace_id),
                error=str(e),
                error_type=type(e).__name__,
                processing_time_ms=processing_time,
                exc_info=True,
            )

            # Return user-friendly error message
            return AgentResponse(
                answer=get_error_message(language),
                citations=[],
                language=language,
                retrieved_count=0,
                processing_time_ms=processing_time,
            )

    def _format_context(
        self,
        session_contexts: list[SessionContext],
        client_contexts: list[ClientContext],
        language: str,
    ) -> str:
        """
        Format retrieved session and client contexts for LLM consumption.

        Args:
            session_contexts: List of SessionContext objects
            client_contexts: List of ClientContext objects
            language: Language code ("he" or "en")

        Returns:
            Formatted context string with sessions and client profiles
        """
        formatted_parts = []

        # Format client profile contexts first (baseline data)
        if client_contexts:
            client_header = (
                "=== פרופילי לקוחות רלוונטיים ==="
                if language == "he"
                else "=== Relevant Client Profiles ==="
            )
            formatted_parts.append(client_header)

            for i, context in enumerate(client_contexts, 1):
                client_info = []
                client_info.append(f"Client {i}: {context.client_name}")
                client_info.append(f"Similarity: {context.similarity_score:.2%}")
                client_info.append(f"Matched field: {context.matched_field}")

                if context.medical_history:
                    client_info.append(f"Medical History: {context.medical_history}")
                if context.notes:
                    client_info.append(f"Notes: {context.notes}")

                formatted_parts.append("\n".join(client_info))

        # Format session contexts
        if session_contexts:
            session_header = (
                "=== הערות מפגשי טיפול רלוונטיים ==="
                if language == "he"
                else "=== Relevant Treatment Session Notes ==="
            )
            formatted_parts.append(session_header)

            # Sort sessions chronologically by date for proper numbering
            sorted_sessions = sorted(session_contexts, key=lambda ctx: ctx.session_date)

            context_template = get_context_format(language)
            for i, context in enumerate(sorted_sessions, 1):
                formatted_session = context_template.format(
                    session_number=i,
                    client_name=context.client_name,
                    date=context.session_date.strftime("%Y-%m-%d"),
                    matched_field=context.matched_field,
                    similarity=context.similarity_score,
                    subjective=context.subjective or "N/A",
                    objective=context.objective or "N/A",
                    assessment=context.assessment or "N/A",
                    plan=context.plan or "N/A",
                )
                formatted_parts.append(formatted_session)

        return "\n\n".join(formatted_parts)

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
    async def _synthesize_answer_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[str, dict | None, float]:
        """
        Internal method: Call Cohere LLM API to synthesize answer (with retry logic).

        This method is wrapped with retry logic and circuit breaker.
        Retries on transient failures (rate limits, timeouts, network errors).

        Args:
            system_prompt: System prompt for the LLM
            user_prompt: User prompt with query and context

        Returns:
            Tuple of (answer text, token usage dict, llm duration)

        Raises:
            ApiError: If Cohere API returns an error
            httpx.HTTPStatusError: If HTTP request fails
            httpx.TimeoutException: If request times out
        """
        llm_start = time.time()
        response = await self.cohere_client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,  # Low temperature for factual responses
            max_tokens=settings.ai_agent_max_output_tokens,
        )
        llm_duration = time.time() - llm_start

        answer = response.message.content[0].text

        # Extract token usage if available (Cohere API v2 includes this)
        tokens_used = None
        if hasattr(response, "usage") and response.usage:
            billed_units = getattr(response.usage, "billed_units", None)
            tokens_used = {
                "input_tokens": getattr(billed_units, "input_tokens", 0)
                if billed_units
                else 0,
                "output_tokens": getattr(billed_units, "output_tokens", 0)
                if billed_units
                else 0,
            }

        logger.info(
            "llm_synthesis_completed",
            model=self.model,
            answer_length=len(answer),
            tokens_used=tokens_used,
            llm_duration_seconds=llm_duration,
        )

        return answer, tokens_used, llm_duration

    async def _synthesize_answer(
        self,
        query: str,
        context: str,
        language: str,
    ) -> str:
        """
        Synthesize answer using Cohere LLM.

        Args:
            query: User's question
            context: Formatted session contexts
            language: Language code ("he" or "en")

        Returns:
            Synthesized answer string

        Raises:
            AgentError: If LLM call fails
        """
        # Get system and synthesis prompts
        system_prompt = get_system_prompt(language)
        synthesis_template = get_synthesis_prompt(language)

        # Format synthesis prompt with query and context
        user_prompt = synthesis_template.format(
            query=query,
            context=context,
        )

        logger.debug(
            "llm_synthesis_started",
            model=self.model,
            context_length=len(context),
        )

        try:
            # Call retry-wrapped method
            (
                answer,
                tokens_used,
                llm_duration,
            ) = await self._synthesize_answer_with_retry(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )

            # Track token usage metrics if available
            if tokens_used:
                ai_agent_llm_tokens_total.labels(
                    model=self.model, token_type="input"
                ).inc(tokens_used["input_tokens"])
                ai_agent_llm_tokens_total.labels(
                    model=self.model, token_type="output"
                ).inc(tokens_used["output_tokens"])

            # Track LLM duration
            ai_agent_llm_duration_seconds.labels(model=self.model).observe(llm_duration)

            return answer

        except ApiError as e:
            # Track LLM API errors
            ai_agent_llm_errors_total.labels(
                error_type="api_error", model=self.model
            ).inc()

            logger.error(
                "llm_synthesis_api_error",
                error=str(e),
                status_code=getattr(e, "status_code", None),
                exc_info=True,
            )
            raise AgentError(f"Cohere API error: {e}") from e

        except Exception as e:
            # Track generic LLM errors
            ai_agent_llm_errors_total.labels(
                error_type=type(e).__name__, model=self.model
            ).inc()

            logger.error(
                "llm_synthesis_failed",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            raise AgentError(f"Failed to synthesize answer: {e}") from e

    def _extract_citations(
        self,
        session_contexts: list[SessionContext],
        client_contexts: list[ClientContext],
    ) -> list[SessionCitation | ClientCitation]:
        """
        Extract citation metadata from retrieved contexts.

        Args:
            session_contexts: List of SessionContext objects
            client_contexts: List of ClientContext objects

        Returns:
            List of SessionCitation and ClientCitation objects
        """
        citations: list[SessionCitation | ClientCitation] = []

        # Extract session citations
        for context in session_contexts:
            citations.append(
                SessionCitation(
                    session_id=context.session_id,
                    client_id=context.client_id,
                    client_name=context.client_name,
                    session_date=context.session_date,
                    similarity=context.similarity_score,
                    field_name=context.matched_field,
                )
            )

        # Extract client citations
        for context in client_contexts:
            citations.append(
                ClientCitation(
                    client_id=context.client_id,
                    client_name=context.client_name,
                    similarity=context.similarity_score,
                    field_name=context.matched_field,
                )
            )

        return citations

    def _filter_output(self, text: str, max_tokens: int = 500) -> str:
        """
        Filter LLM output for safety and length.

        Applies:
        1. Token limit (approximate, by words)
        2. Basic PII redaction (phone numbers, emails)

        Args:
            text: Raw LLM output
            max_tokens: Maximum tokens (approximated as words)

        Returns:
            Filtered text
        """
        # Token limit (approximate: 1 token ≈ 0.75 words in Hebrew/English)
        words = text.split()
        if len(words) > max_tokens:
            text = " ".join(words[:max_tokens]) + "..."

        # Basic PII redaction patterns
        # Phone numbers (Israeli format: 05X-XXXXXXX, 0X-XXXXXXX)
        text = re.sub(
            r"\b0\d{1,2}-?\d{7,8}\b",
            "[PHONE]",
            text,
        )

        # Email addresses
        text = re.sub(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            "[EMAIL]",
            text,
        )

        # Israeli ID numbers (9 digits)
        text = re.sub(
            r"\b\d{9}\b",
            "[ID]",
            text,
        )

        return text


def get_clinical_agent(db: AsyncSession, redis: Redis | None = None) -> ClinicalAgent:
    """
    Factory function to create a ClinicalAgent instance.

    Args:
        db: SQLAlchemy async session
        redis: Optional Redis client for L1 query result caching

    Returns:
        Configured ClinicalAgent instance

    Example:
        >>> async with get_db_session() as db:
        ...     agent = get_clinical_agent(db, redis)
        ...     response = await agent.query(...)
    """
    return ClinicalAgent(db, redis=redis)
