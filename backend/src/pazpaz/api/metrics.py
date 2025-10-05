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

    Returns:
        Prometheus-formatted metrics text

    Example:
        # HELP audit_events_total Total audit events created
        # TYPE audit_events_total counter
        audit_events_total{resource_type="Client",action="CREATE"} 42.0
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
