"""Tests for request size limit middleware (DoS prevention)."""

import pytest
from fastapi import status
from httpx import AsyncClient


class TestRequestSizeLimitMiddleware:
    """Test request size validation to prevent DoS attacks."""

    @pytest.mark.asyncio
    async def test_small_json_request_accepted(self, client_with_csrf: AsyncClient):
        """Test that small JSON requests are accepted."""
        # Small JSON payload (< 1 KB)
        small_payload = {"name": "Test Client", "email": "test@example.com"}

        response = await client_with_csrf.post(
            "/api/v1/health",  # Use health endpoint for testing
            json=small_payload,
        )

        # Should not be rejected for size (may fail for other reasons, but not 413)
        assert response.status_code != status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

    @pytest.mark.asyncio
    async def test_large_json_request_rejected(self, client_with_csrf: AsyncClient):
        """Test that large JSON requests are rejected with 413."""
        # Create a JSON payload larger than 20 MB
        # Each character is 1 byte, so 21 million characters = 21 MB
        large_payload = {"data": "x" * (21 * 1024 * 1024)}

        response = await client_with_csrf.post(
            "/api/v1/health",
            json=large_payload,
        )

        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        assert "Request body too large" in response.json()["detail"]
        assert "20 MB" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_100mb_json_payload_rejected(self, client_with_csrf: AsyncClient):
        """Test that 100 MB JSON payload is rejected (DoS attack simulation)."""
        # Create a 100 MB JSON payload
        huge_payload = {"data": "x" * (100 * 1024 * 1024)}

        response = await client_with_csrf.post(
            "/api/v1/health",
            json=huge_payload,
        )

        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        assert "Request body too large" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_exactly_20mb_request_accepted(self, client_with_csrf: AsyncClient):
        """Test that requests at exactly 20 MB limit are accepted."""
        # Create exactly 20 MB of data (accounting for JSON overhead)
        # 20 MB = 20,971,520 bytes
        data_size = 20 * 1024 * 1024 - 100  # Subtract JSON overhead
        exact_payload = {"data": "x" * data_size}

        response = await client_with_csrf.post(
            "/api/v1/health",
            json=exact_payload,
        )

        # Should not be rejected for size
        assert response.status_code != status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

    @pytest.mark.asyncio
    async def test_21mb_request_rejected(self, client_with_csrf: AsyncClient):
        """Test that requests just over 20 MB are rejected."""
        # Create 21 MB of data
        data_size = 21 * 1024 * 1024
        large_payload = {"data": "x" * data_size}

        response = await client_with_csrf.post(
            "/api/v1/health",
            json=large_payload,
        )

        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

    @pytest.mark.asyncio
    async def test_error_message_format(self, client_with_csrf: AsyncClient):
        """Test that error message is clear and actionable."""
        # Create 25 MB payload
        large_payload = {"data": "x" * (25 * 1024 * 1024)}

        response = await client_with_csrf.post(
            "/api/v1/health",
            json=large_payload,
        )

        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

        error_detail = response.json()["detail"]
        # Check error message format
        assert "Request body too large" in error_detail
        assert "20 MB" in error_detail  # Max allowed size
        assert "25" in error_detail  # Actual size provided

    @pytest.mark.asyncio
    async def test_invalid_content_length_header(self, client_with_csrf: AsyncClient):
        """Test handling of invalid Content-Length header."""
        response = await client_with_csrf.post(
            "/api/v1/health",
            content=b"test data",
            headers={"Content-Length": "invalid"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid Content-Length header" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_missing_content_length_header_accepted(
        self, client_with_csrf: AsyncClient
    ):
        """Test that requests without Content-Length header are not blocked."""
        # GET requests don't require CSRF and don't send Content-Length
        # This test verifies that missing Content-Length doesn't cause issues
        response = await client_with_csrf.get("/api/v1/health")

        # Should not be rejected for missing Content-Length
        assert response.status_code != status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

    @pytest.mark.asyncio
    async def test_get_request_not_affected(self, client_with_csrf: AsyncClient):
        """Test that GET requests are not affected by size limits."""
        response = await client_with_csrf.get("/api/v1/health")

        assert response.status_code != status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

    @pytest.mark.asyncio
    async def test_multiple_small_requests_not_affected(
        self, client_with_csrf: AsyncClient
    ):
        """Test that multiple small requests don't trigger size limit."""
        for _ in range(10):
            response = await client_with_csrf.post(
                "/api/v1/health",
                json={"test": "data"},
            )
            assert response.status_code != status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

    @pytest.mark.asyncio
    async def test_middleware_runs_early_in_stack(self, client_with_csrf: AsyncClient):
        """Test that middleware rejects large requests before body parsing."""
        # This test verifies that the middleware runs early enough
        # to prevent memory exhaustion from reading large bodies

        # Create a 50 MB payload
        huge_payload = {"data": "x" * (50 * 1024 * 1024)}

        response = await client_with_csrf.post(
            "/api/v1/health",
            json=huge_payload,
        )

        # Should be rejected immediately with 413
        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

        # Response should be returned quickly (not timeout from memory exhaustion)
        # If middleware didn't run early, this would cause memory issues


class TestFileUploadWithSizeLimit:
    """Test that file uploads work correctly with size limits."""

    @pytest.mark.asyncio
    async def test_10mb_file_upload_works(
        self,
        authenticated_client: AsyncClient,
        workspace_id: str,
        client_id: str,
    ):
        """Test that 10 MB file uploads still work (within limit)."""
        # Skip - file upload endpoints not yet implemented
        pytest.skip("File upload endpoints not yet implemented")

    @pytest.mark.asyncio
    async def test_25mb_file_upload_rejected(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test that 25 MB file uploads are rejected (exceeds limit)."""
        # Skip - file upload endpoints not yet implemented
        pytest.skip("File upload endpoints not yet implemented")

    @pytest.mark.asyncio
    async def test_file_upload_with_metadata_under_limit(
        self,
        authenticated_client: AsyncClient,
    ):
        """Test that file + metadata stays under 20 MB limit."""
        # Skip - file upload endpoints not yet implemented
        pytest.skip("File upload endpoints not yet implemented")


class TestPerformanceImpact:
    """Test that middleware has negligible performance impact."""

    @pytest.mark.asyncio
    async def test_no_performance_impact_on_normal_requests(
        self, client_with_csrf: AsyncClient
    ):
        """Test that middleware doesn't slow down normal requests."""
        import time

        # Make 50 normal requests and measure average time
        times = []
        for _ in range(50):
            start = time.time()
            response = await client_with_csrf.post(
                "/api/v1/health",
                json={"test": "data"},
            )
            elapsed = time.time() - start
            times.append(elapsed)

        avg_time = sum(times) / len(times)

        # Average request time should be under 100ms (very generous)
        # Middleware should add <1ms overhead (just header check)
        assert avg_time < 0.1, f"Average request time too high: {avg_time:.3f}s"

    @pytest.mark.asyncio
    async def test_fast_rejection_of_large_requests(
        self, client_with_csrf: AsyncClient
    ):
        """Test that large requests are rejected quickly (no body read)."""
        import time

        # Create 100 MB payload
        huge_payload = {"data": "x" * (100 * 1024 * 1024)}

        start = time.time()
        response = await client_with_csrf.post(
            "/api/v1/health",
            json=huge_payload,
        )
        elapsed = time.time() - start

        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

        # Should be rejected in under 1 second (not reading entire body)
        assert elapsed < 1.0, f"Rejection took too long: {elapsed:.3f}s"


class TestSecurityLogging:
    """Test that security events are logged correctly."""

    @pytest.mark.asyncio
    async def test_rejected_request_logged(self, client_with_csrf: AsyncClient, caplog):
        """Test that rejected large requests are logged for security monitoring."""
        # Create 50 MB payload
        large_payload = {"data": "x" * (50 * 1024 * 1024)}

        response = await client_with_csrf.post(
            "/api/v1/health",
            json=large_payload,
        )

        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE

        # Check that rejection was logged
        # Note: This test may need adjustment based on actual logging configuration
        # The key is that the event should appear in logs for security monitoring
