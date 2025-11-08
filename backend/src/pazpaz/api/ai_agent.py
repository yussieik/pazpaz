"""AI Agent chat API endpoints for clinical documentation queries."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.ai.agent import get_clinical_agent
from pazpaz.ai.metrics import ai_agent_rate_limit_hits_total
from pazpaz.ai.prompt_injection import PromptInjectionError, validate_query
from pazpaz.api.deps import get_current_user, get_db
from pazpaz.core.logging import get_logger
from pazpaz.core.rate_limiting import check_rate_limit_redis
from pazpaz.core.redis import get_redis
from pazpaz.models.user import User
from pazpaz.schemas.ai_agent import (
    AgentChatRequest,
    AgentChatResponse,
    ClientCitationResponse,
    SessionCitationResponse,
)

router = APIRouter(prefix="/ai/agent", tags=["ai-agent"])
logger = get_logger(__name__)


@router.post("/chat", response_model=AgentChatResponse, status_code=200)
async def chat_with_agent(
    request_data: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
) -> AgentChatResponse:
    """
    Chat with AI clinical documentation assistant.

    Processes natural language queries (Hebrew or English) about patient
    clinical history using semantic search and LLM synthesis.

    **Features:**
    - Bilingual support (Hebrew/English auto-detection)
    - Semantic search across SOAP notes (pgvector + Cohere embeddings)
    - Workspace-scoped (multi-tenant isolation)
    - Citations with session links
    - HIPAA-compliant audit logging

    **Security:**
    - Rate limited: 30 queries/hour per workspace
    - Workspace isolation enforced
    - No query text stored (ephemeral processing)
    - PHI auto-decrypted only for authorized workspace

    **AUDIT:** All queries are logged with metadata (query_length, language,
    retrieved_count, processing_time) but NOT the query text itself (PHI risk).

    Args:
        request_data: Chat request with query and optional filters
        current_user: Authenticated user (from JWT token)
        db: Database session
        redis_client: Redis client for rate limiting

    Returns:
        AgentChatResponse with answer, citations, and metadata

    Raises:
        HTTPException: 401 if not authenticated,
                      429 if rate limit exceeded,
                      500 if agent processing fails

    Example:
        POST /api/v1/ai/agent/chat
        {
            "query": "What was the patient's back pain history?",
            "client_id": "uuid",
            "max_results": 5,
            "min_similarity": 0.7
        }

        Response:
        {
            "answer": "Based on session notes, the patient...",
            "citations": [
                {
                    "session_id": "uuid",
                    "client_name": "John Doe",
                    "session_date": "2025-11-01T10:30:00Z",
                    "similarity": 0.85,
                    "field_name": "subjective"
                }
            ],
            "language": "en",
            "retrieved_count": 3,
            "processing_time_ms": 1250
        }
    """
    workspace_id = current_user.workspace_id

    # Apply rate limit (30 queries per hour per workspace)
    # Workspace-level scoping prevents abuse across all users in workspace
    rate_limit_key = f"ai_agent_chat:{workspace_id}"
    if not await check_rate_limit_redis(
        redis_client=redis_client,
        key=rate_limit_key,
        max_requests=30,
        window_seconds=3600,  # 1 hour
    ):
        # Track rate limit hit
        ai_agent_rate_limit_hits_total.labels(workspace_id=str(workspace_id)).inc()

        logger.warning(
            "ai_agent_chat_rate_limit_exceeded",
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
            query_length=len(request_data.query),
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Rate limit exceeded. Maximum 30 AI chat queries "
                "per hour per workspace."
            ),
        )

    logger.info(
        "ai_agent_chat_request",
        user_id=str(current_user.id),
        workspace_id=str(workspace_id),
        query_length=len(request_data.query),
        client_id=str(request_data.client_id) if request_data.client_id else None,
        max_results=request_data.max_results,
        min_similarity=request_data.min_similarity,
    )

    # Validate and sanitize query (prompt injection protection)
    try:
        sanitized_query = validate_query(request_data.query)
    except PromptInjectionError as e:
        logger.warning(
            "ai_agent_chat_prompt_injection_blocked",
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
            query_length=len(request_data.query),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except ValueError as e:
        logger.warning(
            "ai_agent_chat_invalid_query",
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
            query_length=len(request_data.query),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    try:
        # Initialize agent with database session
        agent = get_clinical_agent(db)

        # Query agent with workspace scoping and user ID for audit logging
        # Use sanitized_query (validated and cleaned for prompt injection)
        response = await agent.query(
            workspace_id=workspace_id,
            query=sanitized_query,
            user_id=current_user.id,  # For HIPAA audit logging
            client_id=request_data.client_id,
            max_results=request_data.max_results,
            min_similarity=request_data.min_similarity,
        )

        # Convert agent response to API response schema
        # Handle both SessionCitation and ClientCitation types
        from pazpaz.ai.agent import ClientCitation, SessionCitation

        citations: list[SessionCitationResponse | ClientCitationResponse] = []
        for citation in response.citations:
            if isinstance(citation, SessionCitation):
                citations.append(
                    SessionCitationResponse(
                        type="session",
                        session_id=citation.session_id,
                        client_id=citation.client_id,
                        client_name=citation.client_name,
                        session_date=citation.session_date,
                        similarity=citation.similarity,
                        field_name=citation.field_name,
                    )
                )
            elif isinstance(citation, ClientCitation):
                # Client citations reference the client profile, not a session
                citations.append(
                    ClientCitationResponse(
                        type="client",
                        client_id=citation.client_id,
                        client_name=citation.client_name,
                        similarity=citation.similarity,
                        field_name=citation.field_name,
                    )
                )

        api_response = AgentChatResponse(
            answer=response.answer,
            citations=citations,
            language=response.language,
            retrieved_count=response.retrieved_count,
            processing_time_ms=response.processing_time_ms,
        )

        logger.info(
            "ai_agent_chat_success",
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
            language=response.language,
            retrieved_count=response.retrieved_count,
            citations_count=len(response.citations),
            processing_time_ms=response.processing_time_ms,
        )

        return api_response

    except Exception as e:
        logger.error(
            "ai_agent_chat_error",
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )

        # Don't expose internal errors to client
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process AI chat query. Please try again later.",
        ) from e
