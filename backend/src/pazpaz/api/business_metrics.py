"""Custom business metrics for Prometheus.

These metrics track key business events in PazPaz (appointments, sessions).
All metrics are workspace-scoped to support multi-tenancy analytics.

HIPAA Compliance:
- Metrics use workspace_id UUID only (no PII)
- No client names, session content, or PHI
- Aggregations safe for external monitoring
"""

from datetime import UTC, datetime, timedelta

from prometheus_client import REGISTRY, Counter, Gauge
from sqlalchemy import select, union
from sqlalchemy.sql import func

from pazpaz.db.base import AsyncSessionLocal
from pazpaz.models.appointment import Appointment
from pazpaz.models.client import Client
from pazpaz.models.session import Session

# =============================================================================
# Appointment Metrics
# =============================================================================

appointments_created_total = Counter(
    "appointments_created_total",
    "Total appointments created",
    ["workspace_id"],  # No PII, just workspace UUID
)

appointments_cancelled_total = Counter(
    "appointments_cancelled_total",
    "Total appointments cancelled",
    [
        "workspace_id",
        "reason",
    ],  # reason: "client_request", "therapist_cancelled", "no_show"
)

# =============================================================================
# Session Notes Metrics
# =============================================================================

session_notes_saved_total = Counter(
    "session_notes_saved_total",
    "Total SOAP session notes saved",
    ["workspace_id"],
)

# =============================================================================
# Active Users Metrics
# =============================================================================

active_websocket_sessions = Gauge(
    "active_websocket_sessions",
    "Number of active WebSocket connections (real-time updates)",
)

# Note: This gauge is updated by WebSocket connection handlers
# Increment on connection, decrement on disconnection

# =============================================================================
# Workspace Activity Metrics
# =============================================================================


class ActiveWorkspacesCollector:
    """
    Custom Prometheus collector for active_workspaces_24h metric.

    Calculates the number of workspaces with activity in the last 24 hours
    on-demand when Prometheus scrapes the /metrics endpoint.

    This avoids the multi-process issue where ARQ worker and API server have
    separate metric registries.
    """

    def __init__(self):
        """Initialize the collector and register it with Prometheus."""
        REGISTRY.register(self)

    def collect(self):
        """
        Calculate and yield active workspaces metric.

        Called by Prometheus when scraping /metrics endpoint.
        Runs a database query to count workspaces with recent activity.

        Yields:
            GaugeMetricFamily: active_workspaces_24h metric with current value
        """
        # Import here to avoid circular dependency during module load
        import asyncio
        import traceback

        from prometheus_client.core import GaugeMetricFamily

        # Calculate active workspaces
        try:
            # Create new event loop since Prometheus collector runs in sync context
            # but we need to call async database code
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                count = loop.run_until_complete(self._count_active_workspaces())
                print(f"[METRICS DEBUG] Active workspaces calculated: {count}")
            finally:
                loop.close()
        except Exception as e:
            # If query fails, return 0 rather than breaking metrics endpoint
            print(f"[METRICS ERROR] Failed to calculate active_workspaces_24h: {e}")
            traceback.print_exc()
            count = 0

        # Yield the metric
        gauge = GaugeMetricFamily(
            "active_workspaces_24h",
            "Number of workspaces with activity in last 24 hours",
        )
        gauge.add_metric([], count)
        yield gauge

    async def _count_active_workspaces(self) -> int:
        """
        Count workspaces with activity in last 24 hours.

        Returns:
            Number of distinct workspaces with appointments, sessions,
            or clients created/updated in last 24 hours.
        """
        async with AsyncSessionLocal() as db:
            cutoff_time = datetime.now(UTC) - timedelta(hours=24)

            # Find distinct workspace IDs with any activity in last 24h
            workspace_ids_appointments = (
                select(Appointment.workspace_id)
                .where(
                    (Appointment.created_at >= cutoff_time)
                    | (Appointment.updated_at >= cutoff_time)
                )
                .distinct()
            )

            workspace_ids_sessions = (
                select(Session.workspace_id)
                .where(
                    (Session.created_at >= cutoff_time)
                    | (Session.updated_at >= cutoff_time)
                )
                .distinct()
            )

            workspace_ids_clients = (
                select(Client.workspace_id)
                .where(
                    (Client.created_at >= cutoff_time)
                    | (Client.updated_at >= cutoff_time)
                )
                .distinct()
            )

            # Union all workspace IDs and count
            all_active_workspaces = union(
                workspace_ids_appointments,
                workspace_ids_sessions,
                workspace_ids_clients,
            ).subquery()

            stmt = select(func.count()).select_from(all_active_workspaces)
            result = await db.execute(stmt)
            return result.scalar() or 0


# Initialize the collector (registers itself with Prometheus)
_active_workspaces_collector = ActiveWorkspacesCollector()

__all__ = [
    "appointments_created_total",
    "appointments_cancelled_total",
    "session_notes_saved_total",
    "active_websocket_sessions",
]
