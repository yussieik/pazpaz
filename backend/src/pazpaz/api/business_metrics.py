"""Custom business metrics for Prometheus."""

from prometheus_client import Counter, Gauge

# Appointment metrics
appointments_created_total = Counter(
    "appointments_created_total",
    "Total appointments created",
    ["workspace_id"],  # No PII, just UUID
)

appointments_cancelled_total = Counter(
    "appointments_cancelled_total",
    "Total appointments cancelled",
    [
        "workspace_id",
        "reason",
    ],  # reason: "client_request", "therapist_cancelled", "no_show"
)

# Session notes metrics
session_notes_saved_total = Counter(
    "session_notes_saved_total",
    "Total SOAP session notes saved",
    ["workspace_id"],
)

# Active users
active_sessions_gauge = Gauge(
    "active_websocket_sessions",
    "Number of active WebSocket connections (real-time updates)",
)

# Workspace metrics
active_workspaces_24h_gauge = Gauge(
    "active_workspaces_24h",
    "Number of workspaces with activity in last 24 hours",
)

__all__ = [
    "appointments_created_total",
    "appointments_cancelled_total",
    "session_notes_saved_total",
    "active_sessions_gauge",
    "active_workspaces_24h_gauge",
]
