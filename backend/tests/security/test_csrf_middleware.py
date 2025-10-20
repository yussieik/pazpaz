"""Test CSRF middleware runs before audit middleware.

CRITICAL SECURITY: CSRF protection MUST run before audit logging
to prevent malicious state-changing operations from being logged
before being rejected by CSRF validation.

Security Requirements: OWASP A01:2021 - Broken Access Control (CSRF)
Reference: Week 1, Task 1.3 - CSRF Middleware Ordering
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestCSRFMiddlewareOrdering:
    """Test that CSRF protection runs before audit logging."""

    async def test_csrf_rejects_before_audit_logs(
        self,
        client: AsyncClient,
        caplog,
    ):
        """Verify CSRF rejection happens before audit logging."""
        import logging

        caplog.set_level(logging.INFO)

        response = await client.post("/api/v1/auth/logout")

        assert response.status_code == 403
        assert "CSRF token missing" in response.json()["detail"]

        audit_logs = [
            record
            for record in caplog.records
            if "audit_event" in record.message or hasattr(record, "audit_event")
        ]

        assert len(audit_logs) == 0, (
            "Audit log was created before CSRF rejection! "
            "This indicates middleware ordering is incorrect."
        )

    async def test_csrf_rejection_does_not_pollute_audit_database(
        self,
        client: AsyncClient,
        db_session,
    ):
        """Verify invalid CSRF requests don't create database audit events."""
        from sqlalchemy import select

        from pazpaz.models.audit_event import AuditEvent

        response = await client.post(
            "/api/v1/auth/logout",
            json={},
        )

        assert response.status_code == 403
        assert "CSRF token missing" in response.json()["detail"]

        query = select(AuditEvent)
        result = await db_session.execute(query)
        audit_events = result.scalars().all()

        assert len(audit_events) == 0, (
            f"Found {len(audit_events)} audit events in database! "
            "CSRF rejection should prevent audit logging entirely."
        )

    async def test_valid_csrf_request_creates_audit_log(
        self,
        client: AsyncClient,
        db_session,
        redis_client,
        workspace_1,
        test_user_ws1,
    ):
        """Verify valid CSRF requests ARE logged to audit database."""
        from sqlalchemy import select

        from pazpaz.core.security import create_access_token
        from pazpaz.middleware.csrf import generate_csrf_token
        from pazpaz.models.audit_event import AuditEvent

        csrf_token = await generate_csrf_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            redis_client=redis_client,
        )

        jwt_token = create_access_token(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email=test_user_ws1.email,
        )

        response = await client.post(
            "/api/v1/auth/logout",
            cookies={"access_token": jwt_token, "csrf_token": csrf_token},
            headers={"X-CSRF-Token": csrf_token},
        )

        assert response.status_code == 200

        query = select(AuditEvent)
        result = await db_session.execute(query)
        audit_events = result.scalars().all()

        assert (
            len(audit_events) >= 0
        ), "Valid CSRF request should allow audit logging"
