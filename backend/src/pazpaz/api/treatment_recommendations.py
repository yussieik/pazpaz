"""Treatment Recommendation API endpoints (ADR 0002).

This module provides AI-powered treatment plan recommendations for therapists
based on SOAP note inputs (Subjective, Objective, Assessment).

Features:
- Therapy-specific recommendations (massage, physiotherapy, psychotherapy)
- Patient context integration (retrieves similar past sessions)
- Rate limiting (60 requests/hour per workspace)
- HIPAA-compliant audit logging
- Bilingual support (Hebrew/English auto-detection)
"""

from __future__ import annotations

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
from pazpaz.schemas.treatment_recommendations import (
    TreatmentRecommendationItem,
    TreatmentRecommendationRequest,
    TreatmentRecommendationResponse,
)

router = APIRouter(prefix="/ai/treatment-recommendations", tags=["ai-treatment"])
logger = get_logger(__name__)


@router.post("/", response_model=TreatmentRecommendationResponse, status_code=200)
async def get_treatment_recommendations(
    request_data: TreatmentRecommendationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: Redis = Depends(get_redis),
) -> TreatmentRecommendationResponse:
    """
    Generate AI-powered treatment plan recommendations based on SOAP notes.

    This endpoint analyzes Subjective, Objective, and Assessment findings to
    generate 1-2 focused, evidence-based treatment recommendations tailored
    to the detected therapy type (massage, physiotherapy, psychotherapy).

    **Process:**
    1. Detect therapy type from clinical terminology
    2. Retrieve patient context (similar past sessions) if client_id provided
    3. Generate recommendations using therapy-specific LLM prompts
    4. Return structured recommendations with evidence sources

    **Security:**
    - Rate limited: 60 requests/hour per workspace
    - Workspace isolation enforced
    - Input validation (prompt injection protection)
    - PHI auto-decrypted only for authorized workspace
    - All requests logged to audit trail (metadata only, no PHI)

    **AUDIT:** All recommendation requests are logged with metadata
    (therapy_type, language, retrieved_count, processing_time) but NOT
    the SOAP note contents (PHI risk).

    Args:
        request_data: SOAP note inputs (S, O, A) and optional client_id
        current_user: Authenticated user (from JWT token)
        db: Database session
        redis_client: Redis client for rate limiting

    Returns:
        TreatmentRecommendationResponse with 1-2 recommendations and metadata

    Raises:
        HTTPException: 401 if not authenticated,
                      400 if invalid input or prompt injection detected,
                      429 if rate limit exceeded,
                      500 if recommendation generation fails

    Example:
        POST /api/v1/ai/treatment-recommendations/
        {
            "subjective": "Patient reports tight upper trapezius, 6/10 pain",
            "objective": "Palpation reveals trigger points, limited ROM",
            "assessment": "Myofascial pain syndrome, upper trapezius",
            "client_id": "uuid-optional"
        }

        Response:
        {
            "recommendations": [
                {
                    "recommendation_id": "uuid",
                    "title": "Manual Therapy + Home Exercises",
                    "description": "Apply manual therapy to upper trap...",
                    "therapy_type": "massage",
                    "evidence_type": "hybrid",
                    "similar_cases_count": 5
                }
            ],
            "therapy_type": "massage",
            "language": "en",
            "retrieved_count": 5,
            "processing_time_ms": 1450
        }
    """
    workspace_id = current_user.workspace_id

    # Apply rate limit (60 requests per hour per workspace)
    # Higher limit than chat (30/hr) because recommendations are shorter queries
    rate_limit_key = f"ai_treatment_recommendations:{workspace_id}"
    if not await check_rate_limit_redis(
        redis_client=redis_client,
        key=rate_limit_key,
        max_requests=60,
        window_seconds=3600,  # 1 hour
    ):
        # Track rate limit hit (reuse existing metric)
        ai_agent_rate_limit_hits_total.labels(workspace_id=str(workspace_id)).inc()

        logger.warning(
            "ai_treatment_recommendations_rate_limit_exceeded",
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
            subjective_length=len(request_data.subjective),
            objective_length=len(request_data.objective),
            assessment_length=len(request_data.assessment),
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Rate limit exceeded. Maximum 60 treatment recommendation "
                "requests per hour per workspace."
            ),
        )

    logger.info(
        "ai_treatment_recommendations_request",
        user_id=str(current_user.id),
        workspace_id=str(workspace_id),
        subjective_length=len(request_data.subjective),
        objective_length=len(request_data.objective),
        assessment_length=len(request_data.assessment),
        client_id=str(request_data.client_id) if request_data.client_id else None,
    )

    # Validate and sanitize all SOAP inputs (prompt injection protection)
    # SOAP notes need higher length limits (2000 chars) than chat queries (500 chars)
    # as they contain detailed clinical documentation
    soap_max_length = 2000
    try:
        sanitized_subjective = validate_query(
            request_data.subjective, max_length=soap_max_length
        )
        sanitized_objective = validate_query(
            request_data.objective, max_length=soap_max_length
        )
        sanitized_assessment = validate_query(
            request_data.assessment, max_length=soap_max_length
        )
    except PromptInjectionError as e:
        logger.warning(
            "ai_treatment_recommendations_prompt_injection_blocked",
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except ValueError as e:
        logger.warning(
            "ai_treatment_recommendations_invalid_input",
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    try:
        # Initialize agent with database session
        agent = get_clinical_agent(db)

        # Generate treatment recommendations with workspace scoping
        # Use sanitized inputs (validated for prompt injection)
        response = await agent.recommend_treatment_plan(
            workspace_id=workspace_id,
            subjective=sanitized_subjective,
            objective=sanitized_objective,
            assessment=sanitized_assessment,
            client_id=request_data.client_id,
        )

        # Convert agent dataclass response to Pydantic API response
        recommendations_list = [
            TreatmentRecommendationItem(
                recommendation_id=rec.recommendation_id,
                title=rec.title,
                description=rec.description,
                therapy_type=rec.therapy_type,
                evidence_type=rec.evidence_type,
                similar_cases_count=rec.similar_cases_count,
            )
            for rec in response.recommendations
        ]

        api_response = TreatmentRecommendationResponse(
            recommendations=recommendations_list,
            therapy_type=response.therapy_type,
            language=response.language,
            retrieved_count=response.retrieved_count,
            processing_time_ms=response.processing_time_ms,
        )

        logger.info(
            "ai_treatment_recommendations_success",
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
            therapy_type=response.therapy_type,
            language=response.language,
            retrieved_count=response.retrieved_count,
            recommendations_count=len(response.recommendations),
            processing_time_ms=response.processing_time_ms,
        )

        return api_response

    except Exception as e:
        logger.error(
            "ai_treatment_recommendations_error",
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )

        # Don't expose internal errors to client
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Failed to generate treatment recommendations. Please try again later."
            ),
        ) from e
