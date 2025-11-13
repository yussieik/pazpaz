"""Custom business metrics for Prometheus.

These metrics track key business events in PazPaz (appointments, sessions).
All metrics are workspace-scoped to support multi-tenancy analytics.

HIPAA Compliance:
- Metrics use workspace_id UUID only (no PII)
- No client names, session content, or PHI
- Aggregations safe for external monitoring
"""

from prometheus_client import Counter, Gauge

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

active_workspaces_24h = Gauge(
    "active_workspaces_24h",
    "Number of workspaces with activity in last 24 hours",
)

# Note: This gauge is periodically updated by a background task
# See: backend/src/pazpaz/workers/metrics_updater.py (future enhancement)

__all__ = [
    "appointments_created_total",
    "appointments_cancelled_total",
    "session_notes_saved_total",
    "active_websocket_sessions",
    "active_workspaces_24h",
]
