"""Prometheus metrics endpoint for monitoring."""

from fastapi import APIRouter
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

router = APIRouter(tags=["monitoring"])


@router.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.

    Exposes application metrics in Prometheus format for scraping.

    Metrics include:
    - audit_events_total: Audit events by resource type, action, workspace
    - audit_failures_total: Audit failures by resource type, action, error
    - audit_latency_seconds: Audit event write latency histogram by action
    - ai_agent_queries_total: AI agent queries by workspace, language, status
    - ai_agent_query_duration_seconds: End-to-end query latency histogram
    - ai_agent_embedding_duration_seconds: Embedding generation latency
    - ai_agent_retrieval_duration_seconds: Vector search latency
    - ai_agent_llm_duration_seconds: LLM synthesis latency by model
    - ai_agent_llm_errors_total: LLM API errors by error type
    - ai_agent_llm_tokens_total: Token consumption by model and type
    - ai_agent_rate_limit_hits_total: Rate limit violations by workspace
    - ai_agent_sources_retrieved: Number of sources per query
    - ai_agent_citations_returned: Number of citations per query

    Returns:
        Prometheus-formatted metrics text

    Example:
        # HELP audit_events_total Total audit events created
        # TYPE audit_events_total counter
        audit_events_total{resource_type="Client",action="CREATE"} 42.0

        # HELP ai_agent_queries_total Total AI agent queries processed
        # TYPE ai_agent_queries_total counter
        ai_agent_queries_total{workspace_id="uuid",language="en",status="success"} 150.0
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
