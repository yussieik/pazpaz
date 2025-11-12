"""Sentry configuration with HIPAA-compliant PII stripping."""

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

from pazpaz.core.config import settings
from pazpaz.core.constants import PHI_FIELDS


def strip_pii_from_sentry_event(event, hint):
    """
    Remove PII/PHI before sending to Sentry (HIPAA compliance).

    Removes:
    - User emails, names, phone numbers
    - Session notes (S/O/A/P fields)
    - Client data
    - Authentication tokens
    - SQL queries (may contain PHI)
    - Local variables from stack traces

    Args:
        event: Sentry event dict
        hint: Additional context from Sentry

    Returns:
        Modified event dict with PII stripped, or None to drop event
    """
    # Remove user PII (keep UUID only for tracking)
    if "user" in event:
        event["user"] = {"id": event["user"].get("id")}

    # Scrub request data
    if "request" in event:
        # Remove cookies (may contain session tokens)
        event["request"].pop("cookies", None)

        # Keep only safe headers (no Authorization, cookies, etc.)
        safe_headers = {"content-type", "user-agent", "host"}
        if "headers" in event["request"]:
            event["request"]["headers"] = {
                k: v
                for k, v in event["request"]["headers"].items()
                if k.lower() in safe_headers
            }

        # Remove query string (may contain tokens or PII)
        event["request"].pop("query_string", None)

    # Scrub breadcrumbs (may contain SQL queries with PHI)
    if "breadcrumbs" in event:
        for crumb in event["breadcrumbs"].get("values", []):
            if crumb.get("category") == "query":
                # SQL queries may contain PHI in WHERE clauses
                crumb["message"] = "[REDACTED SQL QUERY]"
            # Redact API response data (may contain PHI)
            if crumb.get("category") in ("fetch", "xhr"):
                if crumb.get("data") and crumb["data"].get("response"):
                    crumb["data"]["response"] = "[REDACTED]"

    # Remove local variables from stack traces (may contain PHI)
    # Local vars can contain function arguments with client data, session notes, etc.
    if "exception" in event:
        for exception in event["exception"].get("values", []):
            if "stacktrace" in exception:
                for frame in exception["stacktrace"].get("frames", []):
                    frame.pop("vars", None)

    # Scrub POST/PUT body if contains PHI fields
    if "request" in event and "data" in event["request"]:
        body = event["request"]["data"]
        if isinstance(body, dict):
            for field in PHI_FIELDS:
                if field in body:
                    body[field] = "[REDACTED PHI]"

    return event


def init_sentry():
    """
    Initialize Sentry with PII stripping and performance monitoring.

    Configuration:
    - Environment-based DSN (optional in local dev)
    - 10% transaction sampling for cost control
    - FastAPI integration for automatic request tracking
    - PII stripping via before_send hook
    - Ignore noisy errors (WebSocket disconnects, cancelled requests)
    """
    if not settings.sentry_dsn:
        # Sentry not configured - acceptable in local dev
        # Production should have SENTRY_DSN in .env.production
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        # Environment tag for filtering in Sentry dashboard
        environment=settings.environment,  # "production", "staging", or "local"
        # Performance monitoring
        traces_sample_rate=0.1,  # 10% of transactions (cost control)
        profiles_sample_rate=0.1,  # 10% of profiles
        # Integrations
        integrations=[
            FastApiIntegration(
                transaction_style="endpoint"  # Group by endpoint, not dynamic path
            ),
        ],
        # PII/PHI stripping (HIPAA compliance)
        before_send=strip_pii_from_sentry_event,
        # Ignore noisy errors that don't indicate real problems
        ignore_errors=[
            "ConnectionClosed",  # WebSocket disconnects (normal)
            "CancelledError",  # Client cancelled requests (normal)
        ],
        # Additional settings
        send_default_pii=False,  # Never send PII automatically
        attach_stacktrace=True,  # Include stack traces for all events
        max_breadcrumbs=50,  # Limit breadcrumb history
    )
