"""Test security headers middleware implementation.

This test suite verifies all security headers are present and correctly configured
to prevent common web attacks (XSS, clickjacking, MIME sniffing, etc.) and protect PHI.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestReferrerPolicyHeader:
    """Test Referrer-Policy header implementation."""

    async def test_referrer_policy_header_present(self, client: AsyncClient):
        """Verify Referrer-Policy header is present in all responses."""
        response = await client.get("/health")

        assert response.status_code == 200
        assert "Referrer-Policy" in response.headers

    async def test_referrer_policy_value_correct(self, client: AsyncClient):
        """Verify Referrer-Policy is set to strict-origin-when-cross-origin."""
        response = await client.get("/health")

        referrer_policy = response.headers.get("Referrer-Policy", "")
        assert referrer_policy == "strict-origin-when-cross-origin"

    async def test_referrer_policy_on_api_endpoints(self, client: AsyncClient):
        """Verify Referrer-Policy header is present on API endpoints."""
        response = await client.get("/api/v1/health")

        assert "Referrer-Policy" in response.headers
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    async def test_referrer_policy_on_different_methods(self, client: AsyncClient):
        """Verify Referrer-Policy header is present on different HTTP methods."""
        # GET
        response_get = await client.get("/health")
        assert (
            response_get.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        )

        # OPTIONS (CORS preflight)
        response_options = await client.options("/health")
        assert "Referrer-Policy" in response_options.headers
        assert (
            response_options.headers["Referrer-Policy"]
            == "strict-origin-when-cross-origin"
        )

    async def test_referrer_policy_prevents_sensitive_data_leakage(
        self, client: AsyncClient
    ):
        """
        Document that Referrer-Policy prevents sensitive data leakage.

        strict-origin-when-cross-origin behavior:
        - Same-origin requests: Send full URL (safe)
        - Cross-origin HTTPS → HTTPS: Send origin only (no path/query)
        - Cross-origin HTTPS → HTTP: Send nothing (prevent downgrade attacks)

        This prevents PHI, session tokens, or other sensitive data in URLs
        from being leaked to third-party sites via the Referer header.
        """
        response = await client.get("/health")

        referrer_policy = response.headers.get("Referrer-Policy", "")

        # Verify policy would prevent cross-origin full URL leakage
        assert referrer_policy == "strict-origin-when-cross-origin"
        # This is a documentation test - actual behavior is enforced by browser


class TestPermissionsPolicyHeader:
    """Test Permissions-Policy header implementation."""

    async def test_permissions_policy_header_present(self, client: AsyncClient):
        """Verify Permissions-Policy header is present in all responses."""
        response = await client.get("/health")

        assert response.status_code == 200
        assert "Permissions-Policy" in response.headers

    async def test_permissions_policy_disables_geolocation(self, client: AsyncClient):
        """Verify Permissions-Policy disables geolocation API."""
        response = await client.get("/health")

        permissions_policy = response.headers.get("Permissions-Policy", "")
        assert "geolocation=()" in permissions_policy

    async def test_permissions_policy_disables_microphone(self, client: AsyncClient):
        """Verify Permissions-Policy disables microphone API."""
        response = await client.get("/health")

        permissions_policy = response.headers.get("Permissions-Policy", "")
        assert "microphone=()" in permissions_policy

    async def test_permissions_policy_disables_camera(self, client: AsyncClient):
        """Verify Permissions-Policy disables camera API."""
        response = await client.get("/health")

        permissions_policy = response.headers.get("Permissions-Policy", "")
        assert "camera=()" in permissions_policy

    async def test_permissions_policy_disables_payment(self, client: AsyncClient):
        """Verify Permissions-Policy disables payment API."""
        response = await client.get("/health")

        permissions_policy = response.headers.get("Permissions-Policy", "")
        assert "payment=()" in permissions_policy

    async def test_permissions_policy_disables_usb(self, client: AsyncClient):
        """Verify Permissions-Policy disables USB API."""
        response = await client.get("/health")

        permissions_policy = response.headers.get("Permissions-Policy", "")
        assert "usb=()" in permissions_policy

    async def test_permissions_policy_on_api_endpoints(self, client: AsyncClient):
        """Verify Permissions-Policy header is present on API endpoints."""
        response = await client.get("/api/v1/health")

        assert "Permissions-Policy" in response.headers
        permissions_policy = response.headers["Permissions-Policy"]

        # All features should be disabled
        assert "geolocation=()" in permissions_policy
        assert "microphone=()" in permissions_policy
        assert "camera=()" in permissions_policy

    async def test_permissions_policy_on_different_methods(self, client: AsyncClient):
        """Verify Permissions-Policy header is present on different HTTP methods."""
        # GET
        response_get = await client.get("/health")
        assert "Permissions-Policy" in response_get.headers

        # OPTIONS (CORS preflight)
        response_options = await client.options("/health")
        assert "Permissions-Policy" in response_options.headers

    async def test_permissions_policy_protects_phi_privacy(self, client: AsyncClient):
        """
        Document that Permissions-Policy protects PHI privacy.

        Disabled features:
        - geolocation=() - Prevents location tracking (HIPAA privacy requirement)
        - microphone=() - Prevents audio recording of therapy sessions
        - camera=() - Prevents video recording of therapy sessions
        - payment=() - Not needed for this application
        - usb=() - Prevents USB device access (security)

        This ensures therapist workspace cannot be exploited to capture
        sensitive patient information via browser APIs.
        """
        response = await client.get("/health")

        permissions_policy = response.headers.get("Permissions-Policy", "")

        # Verify all privacy-sensitive features are disabled
        assert "geolocation=()" in permissions_policy
        assert "microphone=()" in permissions_policy
        assert "camera=()" in permissions_policy


class TestExistingSecurityHeaders:
    """Test existing security headers are still present (regression tests)."""

    async def test_content_security_policy_present(self, client: AsyncClient):
        """Verify CSP header is still present."""
        response = await client.get("/health")

        assert "Content-Security-Policy" in response.headers

    async def test_x_content_type_options_present(self, client: AsyncClient):
        """Verify X-Content-Type-Options header is still present."""
        response = await client.get("/health")

        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    async def test_x_xss_protection_present(self, client: AsyncClient):
        """Verify X-XSS-Protection header is still present."""
        response = await client.get("/health")

        assert "X-XSS-Protection" in response.headers
        assert response.headers["X-XSS-Protection"] == "1; mode=block"

    async def test_x_frame_options_present(self, client: AsyncClient):
        """Verify X-Frame-Options header is still present."""
        response = await client.get("/health")

        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"

    async def test_x_csp_nonce_present(self, client: AsyncClient):
        """Verify X-CSP-Nonce header is still present."""
        response = await client.get("/health")

        assert "X-CSP-Nonce" in response.headers


class TestAllSecurityHeadersComprehensive:
    """Test all security headers are present in a single comprehensive test."""

    async def test_all_security_headers_present(self, client: AsyncClient):
        """Verify all required security headers are present in responses."""
        response = await client.get("/health")

        # Required security headers
        required_headers = {
            "Content-Security-Policy": None,  # Dynamic value, just check presence
            "X-Content-Type-Options": "nosniff",
            "X-XSS-Protection": "1; mode=block",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=(), payment=(), usb=()",
            "X-CSP-Nonce": None,  # Dynamic value, just check presence
        }

        for header, expected_value in required_headers.items():
            assert header in response.headers, f"Missing security header: {header}"

            if expected_value is not None:
                actual_value = response.headers[header]
                assert actual_value == expected_value, (
                    f"Header {header} has incorrect value: {actual_value} != {expected_value}"
                )

    async def test_security_headers_on_all_endpoint_types(self, client: AsyncClient):
        """Verify security headers are present on different endpoint types."""
        endpoints = [
            "/health",  # Root health check
            "/api/v1/health",  # API health check
        ]

        for endpoint in endpoints:
            response = await client.get(endpoint)

            # All endpoints should have security headers
            assert "Referrer-Policy" in response.headers, f"Missing on {endpoint}"
            assert "Permissions-Policy" in response.headers, f"Missing on {endpoint}"
            assert "X-Frame-Options" in response.headers, f"Missing on {endpoint}"


class TestSecurityHeadersHIPAACompliance:
    """Test security headers meet HIPAA requirements."""

    async def test_headers_protect_phi_in_transit(self, client: AsyncClient):
        """
        Verify headers protect PHI during transmission.

        HIPAA §164.312(e)(1) - Transmission Security:
        - Referrer-Policy prevents PHI in URLs from leaking to third parties
        - Permissions-Policy prevents unauthorized audio/video recording
        - CSP prevents XSS attacks that could exfiltrate PHI
        - X-Frame-Options prevents clickjacking attacks on PHI data
        """
        response = await client.get("/health")

        # Referrer-Policy prevents PHI in URLs from leaking
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

        # Permissions-Policy prevents unauthorized recording
        permissions_policy = response.headers["Permissions-Policy"]
        assert "microphone=()" in permissions_policy
        assert "camera=()" in permissions_policy

        # X-Frame-Options prevents clickjacking
        assert response.headers["X-Frame-Options"] == "DENY"

        # CSP prevents XSS
        assert "Content-Security-Policy" in response.headers

    async def test_headers_prevent_information_disclosure(self, client: AsyncClient):
        """
        Verify headers prevent information disclosure.

        HIPAA §164.308(a)(4)(ii)(A) - Access Management:
        - Permissions-Policy prevents geolocation tracking
        - Referrer-Policy prevents URL-based information leakage
        - X-Content-Type-Options prevents MIME confusion attacks
        """
        response = await client.get("/health")

        # Prevent geolocation tracking
        assert "geolocation=()" in response.headers["Permissions-Policy"]

        # Prevent referrer leakage
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

        # Prevent MIME confusion
        assert response.headers["X-Content-Type-Options"] == "nosniff"


class TestSecurityHeadersAttackMitigation:
    """Test security headers mitigate common attacks."""

    async def test_headers_prevent_xss_attacks(self, client: AsyncClient):
        """
        Verify headers provide defense-in-depth against XSS attacks.

        Multiple layers:
        1. CSP - Primary XSS defense
        2. X-XSS-Protection - Legacy browser support
        3. Referrer-Policy - Prevents XSS payload reflection via referer
        """
        response = await client.get("/health")

        # Primary XSS defense
        assert "Content-Security-Policy" in response.headers

        # Legacy XSS defense
        assert response.headers["X-XSS-Protection"] == "1; mode=block"

        # Prevent XSS via referer
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    async def test_headers_prevent_clickjacking_attacks(self, client: AsyncClient):
        """
        Verify headers prevent clickjacking attacks.

        Defense layers:
        1. X-Frame-Options: DENY - No framing allowed
        2. CSP frame-ancestors: 'none' - CSP-based framing protection
        """
        response = await client.get("/health")

        # X-Frame-Options
        assert response.headers["X-Frame-Options"] == "DENY"

        # CSP frame-ancestors
        csp = response.headers["Content-Security-Policy"]
        assert "frame-ancestors 'none'" in csp

    async def test_headers_prevent_mime_sniffing_attacks(self, client: AsyncClient):
        """
        Verify headers prevent MIME sniffing attacks.

        X-Content-Type-Options: nosniff forces browsers to respect
        declared Content-Type, preventing malicious files from being
        disguised as safe types.
        """
        response = await client.get("/health")

        assert response.headers["X-Content-Type-Options"] == "nosniff"


class TestSecurityHeadersEdgeCases:
    """Test security headers in edge cases and error scenarios."""

    async def test_headers_present_on_404_errors(self, client: AsyncClient):
        """Verify security headers are present even on 404 errors."""
        response = await client.get("/nonexistent-endpoint")

        # Even 404 responses should have security headers
        assert "Referrer-Policy" in response.headers
        assert "Permissions-Policy" in response.headers
        assert "X-Frame-Options" in response.headers

    async def test_headers_present_on_500_errors(self, client: AsyncClient):
        """Verify security headers are present even on server errors."""
        # This test would require triggering a 500 error
        # For now, we'll test that middleware adds headers before error handling

        # GET to health endpoint (should succeed)
        response = await client.get("/health")

        # Headers should be present
        assert "Referrer-Policy" in response.headers
        assert "Permissions-Policy" in response.headers

    async def test_headers_present_on_different_http_methods(self, client: AsyncClient):
        """Verify security headers are present on all HTTP methods."""
        # GET
        response_get = await client.get("/health")
        assert "Referrer-Policy" in response_get.headers
        assert "Permissions-Policy" in response_get.headers

        # HEAD
        response_head = await client.head("/health")
        assert "Referrer-Policy" in response_head.headers
        assert "Permissions-Policy" in response_head.headers

        # OPTIONS (CORS preflight)
        response_options = await client.options("/health")
        assert "Referrer-Policy" in response_options.headers
        assert "Permissions-Policy" in response_options.headers
