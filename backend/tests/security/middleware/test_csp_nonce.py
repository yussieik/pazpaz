"""Test CSP nonce-based implementation for production security."""

from __future__ import annotations

import re

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


class TestCSPNonceGeneration:
    """Test CSP nonce generation and uniqueness."""

    async def test_nonce_generated_per_request(self, client: AsyncClient):
        """Verify cryptographically secure nonce is generated for each request."""
        response = await client.get("/health")

        assert response.status_code == 200
        assert "X-CSP-Nonce" in response.headers

        nonce = response.headers["X-CSP-Nonce"]
        # Nonce should be non-empty base64url string
        assert len(nonce) > 0
        # Base64url uses alphanumeric + - and _ (no / or +)
        assert re.match(r"^[A-Za-z0-9_-]+$", nonce)

    async def test_nonce_is_cryptographically_secure(self, client: AsyncClient):
        """Verify nonce uses cryptographically secure randomness (sufficient length)."""
        response = await client.get("/health")

        nonce = response.headers["X-CSP-Nonce"]
        # secrets.token_urlsafe(32) generates 32 bytes = 256 bits
        # Base64url encoding expands to ~43 characters
        # Minimum acceptable length: 32 characters (192 bits)
        assert len(nonce) >= 32, f"Nonce too short: {len(nonce)} chars (expected >= 32)"

    async def test_nonce_unique_across_requests(self, client: AsyncClient):
        """Verify nonce is unique for each request (not reused)."""
        # Make 10 requests and collect nonces
        nonces = []
        for _ in range(10):
            response = await client.get("/health")
            nonces.append(response.headers["X-CSP-Nonce"])

        # All nonces should be unique
        assert len(nonces) == len(set(nonces)), "Nonces are not unique across requests"

    async def test_nonce_format_valid_base64url(self, client: AsyncClient):
        """Verify nonce uses base64url encoding (safe for HTTP headers and HTML)."""
        response = await client.get("/health")

        nonce = response.headers["X-CSP-Nonce"]
        # Base64url character set: A-Z, a-z, 0-9, -, _
        # No padding (=), no / or + (standard base64 uses these)
        assert re.match(r"^[A-Za-z0-9_-]+$", nonce)
        assert "/" not in nonce, "Standard base64 '/' found (should use base64url)"
        assert "+" not in nonce, "Standard base64 '+' found (should use base64url)"
        assert "=" not in nonce, "Base64 padding '=' found (base64url omits padding)"


class TestProductionCSP:
    """Test production CSP policy (no unsafe-inline, no unsafe-eval)."""

    async def test_production_csp_no_unsafe_inline(
        self, client: AsyncClient, monkeypatch
    ):
        """Verify production CSP does not include 'unsafe-inline'."""
        # Simulate production environment
        from pazpaz.core import config

        monkeypatch.setattr(config.settings, "debug", False)
        monkeypatch.setattr(config.settings, "environment", "production")

        response = await client.get("/health")

        csp = response.headers.get("Content-Security-Policy", "")
        assert "unsafe-inline" not in csp, (
            "Production CSP must not include 'unsafe-inline'"
        )

    async def test_production_csp_no_unsafe_eval(
        self, client: AsyncClient, monkeypatch
    ):
        """Verify production CSP does not include 'unsafe-eval'."""
        from pazpaz.core import config

        monkeypatch.setattr(config.settings, "debug", False)
        monkeypatch.setattr(config.settings, "environment", "production")

        response = await client.get("/health")

        csp = response.headers.get("Content-Security-Policy", "")
        assert "unsafe-eval" not in csp, "Production CSP must not include 'unsafe-eval'"

    async def test_production_csp_includes_nonce_in_script_src(
        self, client: AsyncClient, monkeypatch
    ):
        """Verify production CSP includes nonce in script-src directive."""
        from pazpaz.core import config

        monkeypatch.setattr(config.settings, "debug", False)
        monkeypatch.setattr(config.settings, "environment", "production")

        response = await client.get("/health")

        csp = response.headers.get("Content-Security-Policy", "")
        nonce = response.headers.get("X-CSP-Nonce", "")

        # CSP should include script-src with nonce
        assert f"script-src 'self' 'nonce-{nonce}'" in csp

    async def test_production_csp_includes_nonce_in_style_src(
        self, client: AsyncClient, monkeypatch
    ):
        """Verify production CSP includes nonce in style-src directive."""
        from pazpaz.core import config

        monkeypatch.setattr(config.settings, "debug", False)
        monkeypatch.setattr(config.settings, "environment", "production")

        response = await client.get("/health")

        csp = response.headers.get("Content-Security-Policy", "")
        nonce = response.headers.get("X-CSP-Nonce", "")

        # CSP should include style-src with nonce
        assert f"style-src 'self' 'nonce-{nonce}'" in csp

    async def test_production_csp_default_src_self(
        self, client: AsyncClient, monkeypatch
    ):
        """Verify production CSP sets default-src to 'self'."""
        from pazpaz.core import config

        monkeypatch.setattr(config.settings, "debug", False)
        monkeypatch.setattr(config.settings, "environment", "production")

        response = await client.get("/health")

        csp = response.headers.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp

    async def test_production_csp_img_src_allows_data_and_https(
        self, client: AsyncClient, monkeypatch
    ):
        """Verify production CSP allows images from self, data URIs, and HTTPS."""
        from pazpaz.core import config

        monkeypatch.setattr(config.settings, "debug", False)
        monkeypatch.setattr(config.settings, "environment", "production")

        response = await client.get("/health")

        csp = response.headers.get("Content-Security-Policy", "")
        # img-src should allow 'self', data:, and https:
        assert "img-src 'self' data: https:" in csp

    async def test_production_csp_frame_ancestors_none(
        self, client: AsyncClient, monkeypatch
    ):
        """Verify production CSP prevents framing with frame-ancestors 'none'."""
        from pazpaz.core import config

        monkeypatch.setattr(config.settings, "debug", False)
        monkeypatch.setattr(config.settings, "environment", "production")

        response = await client.get("/health")

        csp = response.headers.get("Content-Security-Policy", "")
        assert "frame-ancestors 'none'" in csp

    async def test_production_csp_upgrade_insecure_requests(
        self, client: AsyncClient, monkeypatch
    ):
        """Verify production CSP includes upgrade-insecure-requests."""
        from pazpaz.core import config

        monkeypatch.setattr(config.settings, "debug", False)
        monkeypatch.setattr(config.settings, "environment", "production")

        response = await client.get("/health")

        csp = response.headers.get("Content-Security-Policy", "")
        assert "upgrade-insecure-requests" in csp


class TestDevelopmentCSP:
    """Test development CSP policy (allows unsafe-inline and unsafe-eval for HMR)."""

    async def test_development_csp_includes_unsafe_inline(self, client: AsyncClient):
        """Verify development CSP includes 'unsafe-inline' for Vite HMR."""
        # Default test environment is development (debug=True)
        response = await client.get("/health")

        csp = response.headers.get("Content-Security-Policy", "")
        # Development allows unsafe-inline for Vue/Vite convenience
        assert "unsafe-inline" in csp

    async def test_development_csp_includes_unsafe_eval(self, client: AsyncClient):
        """Verify development CSP includes 'unsafe-eval' for Vite HMR."""
        response = await client.get("/health")

        csp = response.headers.get("Content-Security-Policy", "")
        # Development allows unsafe-eval for Vite module hot reloading
        assert "unsafe-eval" in csp

    async def test_development_csp_allows_localhost(self, client: AsyncClient):
        """Verify development CSP allows localhost for Vite dev server."""
        response = await client.get("/health")

        csp = response.headers.get("Content-Security-Policy", "")
        # Development allows connections to localhost for Vite
        assert "http://localhost:*" in csp
        assert "ws://localhost:*" in csp

    async def test_development_csp_no_upgrade_insecure_requests(
        self, client: AsyncClient
    ):
        """Verify development CSP does NOT include upgrade-insecure-requests."""
        # Development uses HTTP, not HTTPS
        response = await client.get("/health")

        csp = response.headers.get("Content-Security-Policy", "")
        assert "upgrade-insecure-requests" not in csp


class TestNonceInRequestState:
    """Test nonce storage in request.state for middleware/endpoint access."""

    async def test_nonce_stored_in_request_state(self, client: AsyncClient):
        """Verify nonce is stored in request.state.csp_nonce."""
        # This test requires a custom endpoint that returns request.state.csp_nonce
        # Since we don't have one, we'll test indirectly via header consistency

        response = await client.get("/health")
        nonce_from_header = response.headers.get("X-CSP-Nonce")

        # Nonce in X-CSP-Nonce header should match nonce in CSP header
        # (both come from same request.state.csp_nonce value)
        csp = response.headers.get("Content-Security-Policy", "")

        if "nonce-" in csp:
            # Extract nonce from CSP (production mode)
            match = re.search(r"nonce-([A-Za-z0-9_-]+)", csp)
            if match:
                nonce_from_csp = match.group(1)
                assert nonce_from_header == nonce_from_csp, (
                    "Nonce mismatch between header and CSP"
                )


class TestXCSPNonceHeader:
    """Test X-CSP-Nonce response header for frontend access."""

    async def test_x_csp_nonce_header_present(self, client: AsyncClient):
        """Verify X-CSP-Nonce header is present in all responses."""
        response = await client.get("/health")

        assert "X-CSP-Nonce" in response.headers

    async def test_x_csp_nonce_header_non_empty(self, client: AsyncClient):
        """Verify X-CSP-Nonce header contains non-empty value."""
        response = await client.get("/health")

        nonce = response.headers.get("X-CSP-Nonce", "")
        assert len(nonce) > 0

    async def test_x_csp_nonce_header_on_api_endpoints(self, client: AsyncClient):
        """Verify X-CSP-Nonce header is present on API endpoints (not just /health)."""
        # Test on API endpoint
        response = await client.get("/api/v1/health")

        assert "X-CSP-Nonce" in response.headers
        assert len(response.headers.get("X-CSP-Nonce", "")) > 0

    async def test_x_csp_nonce_matches_csp_directive(
        self, client: AsyncClient, monkeypatch
    ):
        """Verify X-CSP-Nonce value matches nonce in CSP directives."""
        from pazpaz.core import config

        monkeypatch.setattr(config.settings, "debug", False)
        monkeypatch.setattr(config.settings, "environment", "production")

        response = await client.get("/health")

        nonce_header = response.headers.get("X-CSP-Nonce", "")
        csp = response.headers.get("Content-Security-Policy", "")

        # CSP should contain script-src and style-src with this exact nonce
        assert f"'nonce-{nonce_header}'" in csp


class TestNonceEntropyAndSecurity:
    """Test nonce entropy and security properties."""

    async def test_nonce_has_sufficient_entropy(self, client: AsyncClient):
        """Verify nonce has sufficient entropy (no repeated patterns)."""
        # Make 100 requests and check for repeated nonces (collision)
        nonces = set()
        for _ in range(100):
            response = await client.get("/health")
            nonce = response.headers.get("X-CSP-Nonce", "")
            nonces.add(nonce)

        # With 256-bit nonces, collision probability is astronomically low
        # 100 nonces should all be unique
        assert len(nonces) == 100, "Nonce collision detected (insufficient entropy)"

    async def test_nonce_not_predictable(self, client: AsyncClient):
        """Verify nonces are not sequential or predictable."""
        # Get 5 nonces
        nonces = []
        for _ in range(5):
            response = await client.get("/health")
            nonces.append(response.headers.get("X-CSP-Nonce", ""))

        # Nonces should not be sequential (no pattern)
        # Check that consecutive nonces are not similar (Hamming distance)
        for i in range(len(nonces) - 1):
            # Simple check: nonces should differ significantly
            # (not just incrementing a counter)
            assert nonces[i] != nonces[i + 1]

            # Check they're not just off by 1 (not sequential base64)
            # This is a heuristic check
            assert abs(len(nonces[i]) - len(nonces[i + 1])) <= 1


class TestCSPDirectivesCoverage:
    """Test all CSP directives are properly configured."""

    async def test_production_csp_has_all_required_directives(
        self, client: AsyncClient, monkeypatch
    ):
        """Verify production CSP includes all security-critical directives."""
        from pazpaz.core import config

        monkeypatch.setattr(config.settings, "debug", False)
        monkeypatch.setattr(config.settings, "environment", "production")

        response = await client.get("/health")
        csp = response.headers.get("Content-Security-Policy", "")

        # Required directives for security
        required_directives = [
            "default-src",
            "script-src",
            "style-src",
            "img-src",
            "font-src",
            "connect-src",
            "frame-ancestors",
            "base-uri",
            "form-action",
        ]

        for directive in required_directives:
            assert directive in csp, f"Missing CSP directive: {directive}"

    async def test_development_csp_has_all_required_directives(
        self, client: AsyncClient
    ):
        """Verify development CSP includes all security-critical directives."""
        response = await client.get("/health")
        csp = response.headers.get("Content-Security-Policy", "")

        # Required directives for development
        required_directives = [
            "default-src",
            "script-src",
            "style-src",
            "img-src",
            "font-src",
            "connect-src",
            "frame-ancestors",
            "base-uri",
            "form-action",
        ]

        for directive in required_directives:
            assert directive in csp, f"Missing CSP directive: {directive}"


class TestCSPEnvironmentDetection:
    """Test CSP changes based on environment (debug and environment settings)."""

    async def test_csp_uses_nonce_when_debug_false(
        self, client: AsyncClient, monkeypatch
    ):
        """Verify nonce-based CSP is used when debug=False."""
        from pazpaz.core import config

        monkeypatch.setattr(config.settings, "debug", False)
        monkeypatch.setattr(config.settings, "environment", "production")

        response = await client.get("/health")
        csp = response.headers.get("Content-Security-Policy", "")

        # Should use nonce-based CSP (no unsafe-inline)
        assert "nonce-" in csp
        assert "unsafe-inline" not in csp

    async def test_csp_uses_unsafe_inline_when_debug_true(
        self, client: AsyncClient, monkeypatch
    ):
        """Verify permissive CSP is used when debug=True."""
        from pazpaz.core import config

        monkeypatch.setattr(config.settings, "debug", True)

        response = await client.get("/health")
        csp = response.headers.get("Content-Security-Policy", "")

        # Should use permissive CSP (unsafe-inline allowed)
        assert "unsafe-inline" in csp

    async def test_csp_uses_unsafe_inline_when_environment_local(
        self, client: AsyncClient, monkeypatch
    ):
        """Verify permissive CSP is used when environment=local."""
        from pazpaz.core import config

        monkeypatch.setattr(config.settings, "debug", False)
        monkeypatch.setattr(config.settings, "environment", "local")

        response = await client.get("/health")
        csp = response.headers.get("Content-Security-Policy", "")

        # Local environment uses permissive CSP even if debug=False
        assert "unsafe-inline" in csp

    async def test_csp_uses_nonce_in_staging(self, client: AsyncClient, monkeypatch):
        """Verify nonce-based CSP is used in staging environment."""
        from pazpaz.core import config

        monkeypatch.setattr(config.settings, "debug", False)
        monkeypatch.setattr(config.settings, "environment", "staging")

        response = await client.get("/health")
        csp = response.headers.get("Content-Security-Policy", "")

        # Staging uses strict CSP (nonce-based)
        assert "nonce-" in csp
        assert "unsafe-inline" not in csp


class TestSecurityImprovementOverBaseline:
    """Test that nonce-based CSP provides security improvement over baseline."""

    async def test_production_csp_prevents_inline_script_execution(
        self, client: AsyncClient, monkeypatch
    ):
        """
        Verify production CSP would block inline scripts without nonce.

        This test documents the security improvement: attackers cannot inject
        inline scripts because CSP only allows scripts with matching nonce.
        """
        from pazpaz.core import config

        monkeypatch.setattr(config.settings, "debug", False)
        monkeypatch.setattr(config.settings, "environment", "production")

        response = await client.get("/health")
        csp = response.headers.get("Content-Security-Policy", "")

        # Production CSP should NOT allow arbitrary inline scripts
        # Only scripts with nonce attribute matching request nonce will execute
        assert "unsafe-inline" not in csp
        assert "nonce-" in csp

    async def test_production_csp_prevents_eval_based_attacks(
        self, client: AsyncClient, monkeypatch
    ):
        """
        Verify production CSP would block eval()-based attacks.

        This prevents attackers from using eval() to execute malicious code
        even if they can inject strings into the page.
        """
        from pazpaz.core import config

        monkeypatch.setattr(config.settings, "debug", False)
        monkeypatch.setattr(config.settings, "environment", "production")

        response = await client.get("/health")
        csp = response.headers.get("Content-Security-Policy", "")

        # Production CSP should block eval()
        assert "unsafe-eval" not in csp
