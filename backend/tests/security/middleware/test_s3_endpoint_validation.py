"""
Test S3 endpoint HTTPS validation in production.

Security Requirement: Production S3 endpoints MUST use HTTPS (HIPAA §164.312(e)(1)).
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from pazpaz.core.config import Settings


@pytest.fixture(autouse=True)
def clear_lru_cache():
    """Clear LRU cache for get_s3_client() between tests."""
    from pazpaz.core.storage import get_s3_client

    # Clear cache before test
    get_s3_client.cache_clear()

    yield

    # Clear cache after test
    get_s3_client.cache_clear()


class TestS3EndpointValidation:
    """Test S3 endpoint HTTPS enforcement."""

    def test_production_rejects_http_endpoint_in_settings(self):
        """Production environment rejects HTTP S3 endpoint in settings validation."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                environment="production",
                s3_endpoint_url="http://s3.amazonaws.com",  # HTTP not allowed
                s3_access_key="test-key-production",
                s3_secret_key="test-secret-production-key",
                secret_key="x" * 64,
                redis_password="x" * 32,
            )

        error_msg = str(exc_info.value)
        assert "HTTPS" in error_msg
        assert "production" in error_msg
        assert "http://s3.amazonaws.com" in error_msg

    def test_staging_rejects_http_endpoint_in_settings(self):
        """Staging environment rejects HTTP S3 endpoint in settings validation."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(
                environment="staging",
                s3_endpoint_url="http://s3-staging.example.com",
                s3_access_key="test-key-staging",
                s3_secret_key="test-secret-staging-key",
                secret_key="x" * 64,
                redis_password="x" * 32,
            )

        assert "HTTPS" in str(exc_info.value)
        assert "staging" in str(exc_info.value)

    def test_production_accepts_https_endpoint(self):
        """Production environment accepts HTTPS S3 endpoint."""
        settings = Settings(
            environment="production",
            s3_endpoint_url="https://s3.amazonaws.com",  # HTTPS allowed
            s3_access_key="test-key-production",
            s3_secret_key="test-secret-production-key",
            secret_key="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2",
            redis_password="r3d1sp@ssw0rd1234567890abcdefghi",
            redis_url="redis://:r3d1sp@ssw0rd1234567890abcdefghi@localhost:6379/0",
            db_ssl_mode="verify-ca",  # Required for production
        )

        assert settings.s3_endpoint_url == "https://s3.amazonaws.com"

    def test_production_accepts_none_endpoint(self):
        """Production accepts None endpoint (uses AWS S3 default with HTTPS)."""
        settings = Settings(
            environment="production",
            s3_endpoint_url=None,  # None allowed (AWS default)
            s3_access_key="test-key-production",
            s3_secret_key="test-secret-production-key",
            secret_key="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2",
            redis_password="r3d1sp@ssw0rd1234567890abcdefghi",
            redis_url="redis://:r3d1sp@ssw0rd1234567890abcdefghi@localhost:6379/0",
            db_ssl_mode="verify-ca",  # Required for production
        )

        assert settings.s3_endpoint_url is None

    def test_local_allows_http_endpoint(self):
        """Local environment allows HTTP S3 endpoint (for MinIO)."""
        settings = Settings(
            environment="local",
            s3_endpoint_url="http://localhost:9000",  # HTTP allowed in local
            s3_access_key="minioadmin",
            s3_secret_key="minioadmin123",
            secret_key="dev-secret-key",
            redis_password="dev-redis-pass",
        )

        assert settings.s3_endpoint_url == "http://localhost:9000"

    def test_development_allows_http_endpoint(self):
        """Development environment allows HTTP S3 endpoint."""
        settings = Settings(
            environment="development",
            s3_endpoint_url="http://minio-dev.example.com:9000",
            s3_access_key="test-key",
            s3_secret_key="test-secret-key",
            secret_key="dev-secret-key",
            redis_password="dev-redis-pass",
        )

        assert settings.s3_endpoint_url == "http://minio-dev.example.com:9000"

    def test_get_s3_client_validates_production_endpoint(self):
        """get_s3_client() validates endpoint is HTTPS in production."""
        from pazpaz.core.storage import get_s3_client

        # Mock settings with HTTP endpoint in production
        with patch("pazpaz.core.storage.settings") as mock_settings:
            mock_settings.environment = "production"
            mock_settings.s3_endpoint_url = "http://s3.amazonaws.com"  # Invalid
            mock_settings.s3_access_key = "test"
            mock_settings.s3_secret_key = "test"
            mock_settings.s3_region = "us-east-1"

            with pytest.raises(ValueError) as exc_info:
                get_s3_client()

            assert "HTTPS" in str(exc_info.value)
            assert "production" in str(exc_info.value)
            assert "http://s3.amazonaws.com" in str(exc_info.value)

    def test_get_s3_client_succeeds_with_https_in_production(self):
        """get_s3_client() succeeds with HTTPS endpoint in production."""
        from pazpaz.core.storage import get_s3_client

        with patch("pazpaz.core.storage.settings") as mock_settings:
            mock_settings.environment = "production"
            mock_settings.s3_endpoint_url = "https://s3.amazonaws.com"  # Valid
            mock_settings.s3_access_key = "test"
            mock_settings.s3_secret_key = "test"
            mock_settings.s3_region = "us-east-1"

            # Should succeed without error
            client = get_s3_client()
            assert client is not None

    def test_get_s3_client_allows_http_in_local(self):
        """get_s3_client() allows HTTP endpoint in local environment."""
        from pazpaz.core.storage import get_s3_client

        with patch("pazpaz.core.storage.settings") as mock_settings:
            mock_settings.environment = "local"
            mock_settings.s3_endpoint_url = "http://localhost:9000"  # Valid for local
            mock_settings.s3_access_key = "minioadmin"
            mock_settings.s3_secret_key = "minioadmin123"
            mock_settings.s3_region = "us-east-1"

            # Should succeed without error
            client = get_s3_client()
            assert client is not None


class TestS3TLSConfiguration:
    """Test S3 client TLS configuration."""

    def test_production_uses_ssl_true(self):
        """Production S3 client has use_ssl=True."""
        from pazpaz.core.storage import get_s3_client

        with patch("pazpaz.core.storage.settings") as mock_settings:
            mock_settings.environment = "production"
            mock_settings.s3_endpoint_url = "https://s3.amazonaws.com"
            mock_settings.s3_access_key = "test"
            mock_settings.s3_secret_key = "test"
            mock_settings.s3_region = "us-east-1"
            mock_settings.s3_bucket_name = "test-bucket"

            with patch("pazpaz.core.storage.boto3.client") as mock_boto3:
                # Return a mock client
                mock_boto3.return_value = MagicMock()

                get_s3_client()

                # Verify use_ssl=True was passed to boto3.client
                call_kwargs = mock_boto3.call_args[1]
                assert call_kwargs["use_ssl"] is True

    def test_local_http_endpoint_uses_ssl_false(self):
        """Local environment with HTTP endpoint uses use_ssl=False."""
        from pazpaz.core.storage import get_s3_client

        with patch("pazpaz.core.storage.settings") as mock_settings:
            mock_settings.environment = "local"
            mock_settings.s3_endpoint_url = "http://localhost:9000"
            mock_settings.s3_access_key = "minioadmin"
            mock_settings.s3_secret_key = "minioadmin123"
            mock_settings.s3_region = "us-east-1"
            mock_settings.s3_bucket_name = "test-bucket"

            with patch("pazpaz.core.storage.boto3.client") as mock_boto3:
                # Return a mock client
                mock_boto3.return_value = MagicMock()

                get_s3_client()

                # Verify use_ssl=False for HTTP endpoint
                call_kwargs = mock_boto3.call_args[1]
                assert call_kwargs["use_ssl"] is False

    def test_local_https_endpoint_uses_ssl_true(self):
        """Local environment with HTTPS endpoint uses use_ssl=True."""
        from pazpaz.core.storage import get_s3_client

        with patch("pazpaz.core.storage.settings") as mock_settings:
            mock_settings.environment = "local"
            mock_settings.s3_endpoint_url = "https://minio-local.example.com"
            mock_settings.s3_access_key = "minioadmin"
            mock_settings.s3_secret_key = "minioadmin123"
            mock_settings.s3_region = "us-east-1"
            mock_settings.s3_bucket_name = "test-bucket"

            with patch("pazpaz.core.storage.boto3.client") as mock_boto3:
                # Return a mock client
                mock_boto3.return_value = MagicMock()

                get_s3_client()

                # Verify use_ssl=True for HTTPS endpoint
                call_kwargs = mock_boto3.call_args[1]
                assert call_kwargs["use_ssl"] is True

    def test_staging_enforces_https(self):
        """Staging environment enforces HTTPS endpoint."""
        from pazpaz.core.storage import get_s3_client

        with patch("pazpaz.core.storage.settings") as mock_settings:
            mock_settings.environment = "staging"
            mock_settings.s3_endpoint_url = "http://s3-staging.example.com"
            mock_settings.s3_access_key = "test"
            mock_settings.s3_secret_key = "test"
            mock_settings.s3_region = "us-east-1"
            mock_settings.s3_bucket_name = "test-bucket"

            with pytest.raises(ValueError) as exc_info:
                get_s3_client()

            assert "HTTPS" in str(exc_info.value)
            assert "staging" in str(exc_info.value)

    def test_none_endpoint_defaults_to_ssl_true(self):
        """None endpoint (AWS default) uses use_ssl=True."""
        from pazpaz.core.storage import get_s3_client

        with patch("pazpaz.core.storage.settings") as mock_settings:
            mock_settings.environment = "local"
            mock_settings.s3_endpoint_url = None
            mock_settings.s3_access_key = "test"
            mock_settings.s3_secret_key = "test"
            mock_settings.s3_region = "us-east-1"
            mock_settings.s3_bucket_name = "test-bucket"

            with patch("pazpaz.core.storage.boto3.client") as mock_boto3:
                # Return a mock client
                mock_boto3.return_value = MagicMock()

                get_s3_client()

                # Verify use_ssl=True for None endpoint (AWS default)
                call_kwargs = mock_boto3.call_args[1]
                assert call_kwargs["use_ssl"] is True
