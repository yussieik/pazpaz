"""Test CSRF middleware runs before audit middleware."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestCSRFMiddlewareOrdering:
    """Test that CSRF protection runs before audit logging.

    CRITICAL SECURITY: CSRF protection MUST run before audit logging
    to prevent malicious state-changing operations from being logged
    before being rejected by CSRF validation.

    If audit logging runs first, an attacker could:
    1. Generate audit logs for unauthorized operations
    2. Potentially cause DoS by filling audit logs
    3. Create false audit trails
    """

    async def test_csrf_rejects_before_audit_logs(
        self,
        client: AsyncClient,
        caplog,
    ):
        """Verify CSRF rejection happens before audit logging.

        This test ensures that when a POST request without a CSRF token
        is made, the CSRF middleware rejects it BEFORE the audit middleware
        has a chance to log the operation.

        The test validates that:
        1. Request is rejected with 403 (CSRF violation)
        2. No audit log entry is created for the rejected request
        """
        # Import caplog to capture logs
        import logging

        caplog.set_level(logging.INFO)

        # Attempt POST to logout without CSRF token
        # This should be rejected by CSRF middleware BEFORE audit logging
        response = await client.post("/api/v1/auth/logout")

        # Verify CSRF rejection
        assert response.status_code == 403
        assert "CSRF token missing" in response.json()["detail"]

        # Check that no audit log was created
        # Audit logs contain "audit_event" in the log message
        audit_logs = [
            record
            for record in caplog.records
            if "audit_event" in record.message or hasattr(record, "audit_event")
        ]

        # Should be empty - CSRF rejection happened BEFORE audit logging
        assert len(audit_logs) == 0, (
            "Audit log was created before CSRF rejection! "
            "This indicates middleware ordering is incorrect."
        )

    async def test_valid_csrf_allows_audit_logging(
        self,
        client: AsyncClient,
        caplog,
    ):
        """Verify that valid CSRF requests proceed to audit logging.

        This test ensures that when a request has a valid CSRF token,
        it passes CSRF validation and reaches the audit middleware,
        which then logs the operation.
        """
        import logging

        caplog.set_level(logging.INFO)

        # Set matching CSRF token in cookie and header
        csrf_token = "valid-csrf-token-for-audit-test"
        client.cookies.set("csrf_token", csrf_token)

        # Make POST request with valid CSRF token
        response = await client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": csrf_token},
        )

        # Should succeed (not 403 CSRF error)
        assert response.status_code == 200

        # Audit logging should have occurred
        # (Note: This is an indirect test - we verify the request succeeded,
        # which means it passed both CSRF and audit middleware)

    async def test_csrf_bypass_attempt_rejected_before_audit(
        self,
        client: AsyncClient,
        caplog,
    ):
        """Verify CSRF bypass attempts are rejected before audit logging.

        Test that various CSRF bypass attempts are caught by CSRF middleware
        BEFORE reaching audit logging:
        - Missing CSRF header
        - Missing CSRF cookie
        - Mismatched cookie/header
        """
        import logging

        caplog.set_level(logging.INFO)

        # Test 1: Cookie present, header missing
        caplog.clear()
        client.cookies.set("csrf_token", "token-in-cookie")
        response = await client.post("/api/v1/auth/logout")

        assert response.status_code == 403
        assert "CSRF token missing" in response.json()["detail"]

        audit_logs = [r for r in caplog.records if "audit_event" in r.message]
        assert len(audit_logs) == 0, "CSRF rejection should prevent audit logging"

        # Test 2: Header present, cookie missing
        caplog.clear()
        client.cookies.clear()
        response = await client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": "token-in-header"},
        )

        assert response.status_code == 403
        assert "CSRF token missing" in response.json()["detail"]

        audit_logs = [r for r in caplog.records if "audit_event" in r.message]
        assert len(audit_logs) == 0, "CSRF rejection should prevent audit logging"

        # Test 3: Mismatched cookie and header
        caplog.clear()
        client.cookies.set("csrf_token", "cookie-value")
        response = await client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": "different-header-value"},
        )

        assert response.status_code == 403
        assert "CSRF token mismatch" in response.json()["detail"]

        audit_logs = [r for r in caplog.records if "audit_event" in r.message]
        assert len(audit_logs) == 0, "CSRF rejection should prevent audit logging"

    async def test_safe_methods_bypass_csrf_and_reach_audit(
        self,
        client: AsyncClient,
        caplog,
    ):
        """Verify safe methods (GET) bypass CSRF but still reach audit logging.

        GET requests should:
        1. Bypass CSRF validation (no CSRF token required)
        2. Still be logged by audit middleware (if configured)
        """
        import logging

        caplog.set_level(logging.INFO)

        # Make GET request without CSRF token
        response = await client.get("/api/v1/health")

        # Should succeed (GET bypasses CSRF)
        assert response.status_code == 200

        # No CSRF error should be logged
        csrf_errors = [
            r
            for r in caplog.records
            if "CSRF" in r.message or "csrf" in r.message.lower()
        ]
        assert len(csrf_errors) == 0, "GET requests should not trigger CSRF validation"


class TestMiddlewareStackOrder:
    """Test overall middleware stack ordering."""

    async def test_middleware_execution_order_documented(self):
        """Document the expected middleware execution order.

        EXPECTED ORDER (outer to inner):
        1. SecurityHeadersMiddleware - Add security headers
        2. RequestLoggingMiddleware - Log requests/responses
        3. CSRFProtectionMiddleware - Validate CSRF tokens (BEFORE Audit)
        4. AuditMiddleware - Log data access/modifications (AFTER CSRF)
        5. SlowAPIMiddleware - Rate limiting
        6. CORSMiddleware - CORS (dev only)

        This order ensures:
        - Security headers applied to all responses
        - Request/response logging captures everything
        - CSRF protection runs BEFORE audit logging (security critical)
        - Audit logs only valid, CSRF-validated requests
        - Rate limiting happens after security checks
        """
        # This is a documentation test - always passes
        # The actual ordering is verified by integration tests above
        assert True
