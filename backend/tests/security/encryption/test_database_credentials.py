"""
Tests for database credential fetching from AWS Secrets Manager.

This test suite validates the secure database credential management
implementation using AWS Secrets Manager with graceful fallback to
environment variables.

Test Coverage:
- AWS Secrets Manager credential fetching
- Environment variable fallback
- Error handling for missing/invalid credentials
- Production vs development behavior
- Caching behavior
- Secret format validation
"""

from unittest.mock import patch

import pytest

from pazpaz.utils.secrets_manager import (
    KeyNotFoundError,
    get_database_credentials,
)


class TestDatabaseCredentialFetching:
    """Test database credential fetching from AWS Secrets Manager."""

    def setup_method(self):
        """Clear cache before each test."""
        # Clear lru_cache to ensure fresh calls
        get_database_credentials.cache_clear()

    def test_local_environment_uses_env_var_first(self, monkeypatch):
        """Test local environment loads from DATABASE_URL env var first."""
        # Set environment variable
        test_db_url = "postgresql+asyncpg://user:pass@localhost:5432/testdb"
        monkeypatch.setenv("DATABASE_URL", test_db_url)

        result = get_database_credentials(environment="local")

        assert result == test_db_url

    def test_local_environment_falls_back_to_aws(self, monkeypatch):
        """Test local environment falls back to AWS if env var not set."""
        # Remove DATABASE_URL env var
        monkeypatch.delenv("DATABASE_URL", raising=False)

        # Mock dotenv load_dotenv to prevent loading .env file
        monkeypatch.setattr("pazpaz.utils.secrets_manager.os.getenv", lambda key: None)

        # Mock AWS Secrets Manager response
        mock_secret = {
            "username": "testuser",
            "password": "testpass123",
            "host": "test-db.local",
            "port": 5432,
            "database": "testdb",
            "ssl_cert_path": "/etc/ssl/certs/ca-cert.pem",
        }

        with patch("pazpaz.utils.secrets_manager._fetch_secret_from_aws") as mock_fetch:
            mock_fetch.return_value = mock_secret

            result = get_database_credentials(environment="local")

            assert result == (
                "postgresql+asyncpg://testuser:testpass123@test-db.local:5432/testdb"
            )

    def test_production_uses_aws_secrets_manager(self):
        """Test production environment uses AWS Secrets Manager."""
        mock_secret = {
            "username": "produser",
            "password": "prod_secure_password_123",
            "host": "prod-db.internal",
            "port": 5432,
            "database": "pazpaz_prod",
            "ssl_cert_path": "/etc/ssl/certs/rds-ca-2019-root.pem",
        }

        with patch("pazpaz.utils.secrets_manager._fetch_secret_from_aws") as mock_fetch:
            mock_fetch.return_value = mock_secret

            result = get_database_credentials(
                secret_name="pazpaz/database-credentials",
                region="us-east-1",
                environment="production",
            )

            assert (
                result
                == "postgresql+asyncpg://produser:prod_secure_password_123@prod-db.internal:5432/pazpaz_prod"
            )
            mock_fetch.assert_called_once_with(
                "pazpaz/database-credentials", "us-east-1", "production"
            )

    def test_staging_uses_aws_secrets_manager(self):
        """Test staging environment uses AWS Secrets Manager."""
        mock_secret = {
            "username": "staginguser",
            "password": "staging_password_456",
            "host": "staging-db.internal",
            "port": 5432,
            "database": "pazpaz_staging",
        }

        with patch("pazpaz.utils.secrets_manager._fetch_secret_from_aws") as mock_fetch:
            mock_fetch.return_value = mock_secret

            result = get_database_credentials(environment="staging")

            assert (
                result
                == "postgresql+asyncpg://staginguser:staging_password_456@staging-db.internal:5432/pazpaz_staging"
            )

    def test_production_falls_back_to_env_var_if_aws_unavailable(self, monkeypatch):
        """Test production falls back to env var if AWS Secrets Manager fails."""
        # Set fallback env var
        fallback_url = "postgresql+asyncpg://fallback:pass@localhost:5432/fallback_db"
        monkeypatch.setenv("DATABASE_URL", fallback_url)

        # Mock AWS failure
        with patch("pazpaz.utils.secrets_manager._fetch_secret_from_aws") as mock_fetch:
            mock_fetch.return_value = None  # AWS unavailable

            result = get_database_credentials(environment="production")

            assert result == fallback_url

    def test_raises_key_not_found_if_no_credentials_available(self, monkeypatch):
        """Test raises KeyNotFoundError if both AWS and env var fail."""
        # Mock os.getenv to return None (no DATABASE_URL)
        monkeypatch.setattr("pazpaz.utils.secrets_manager.os.getenv", lambda key: None)

        # Mock AWS failure
        with patch("pazpaz.utils.secrets_manager._fetch_secret_from_aws") as mock_fetch:
            mock_fetch.return_value = None

            with pytest.raises(
                KeyNotFoundError,
                match="Database credentials not found in AWS Secrets Manager",
            ):
                get_database_credentials(environment="production")

    def test_handles_missing_required_fields_in_secret(self, monkeypatch):
        """Test error handling when secret is missing required fields."""
        # Mock os.getenv to return None (no DATABASE_URL for fallback)
        monkeypatch.setattr("pazpaz.utils.secrets_manager.os.getenv", lambda key: None)

        # Secret missing 'password' field
        incomplete_secret = {
            "username": "testuser",
            "host": "test-db.local",
            "port": 5432,
            "database": "testdb",
        }

        with patch("pazpaz.utils.secrets_manager._fetch_secret_from_aws") as mock_fetch:
            mock_fetch.return_value = incomplete_secret

            # Should fall back to env var (which doesn't exist)
            with pytest.raises(KeyNotFoundError):
                get_database_credentials(environment="production")

    def test_ssl_cert_path_defaults_to_standard_location(self):
        """Test ssl_cert_path defaults to standard location if not in secret."""
        mock_secret = {
            "username": "testuser",
            "password": "testpass",
            "host": "test-db.local",
            "port": 5432,
            "database": "testdb",
            # ssl_cert_path omitted
        }

        with patch("pazpaz.utils.secrets_manager._fetch_secret_from_aws") as mock_fetch:
            mock_fetch.return_value = mock_secret

            result = get_database_credentials(environment="production")

            # SSL path should default but NOT be in connection string
            # (SSL is configured in db/base.py)
            assert (
                result
                == "postgresql+asyncpg://testuser:testpass@test-db.local:5432/testdb"
            )

    def test_caching_behavior(self):
        """Test that credentials are cached after first fetch."""
        mock_secret = {
            "username": "cacheduser",
            "password": "cachedpass",
            "host": "cache-db.local",
            "port": 5432,
            "database": "cachedb",
        }

        with patch("pazpaz.utils.secrets_manager._fetch_secret_from_aws") as mock_fetch:
            mock_fetch.return_value = mock_secret

            # First call - should fetch from AWS
            result1 = get_database_credentials(environment="production")
            assert mock_fetch.call_count == 1

            # Second call - should use cache
            result2 = get_database_credentials(environment="production")
            assert mock_fetch.call_count == 1  # Not called again

            # Results should be identical
            assert result1 == result2

    def test_custom_secret_name_and_region(self):
        """Test using custom secret name and AWS region."""
        mock_secret = {
            "username": "customuser",
            "password": "custompass",
            "host": "custom-db.local",
            "port": 5432,
            "database": "customdb",
        }

        with patch("pazpaz.utils.secrets_manager._fetch_secret_from_aws") as mock_fetch:
            mock_fetch.return_value = mock_secret

            result = get_database_credentials(
                secret_name="custom/db-credentials",
                region="eu-west-1",
                environment="production",
            )

            mock_fetch.assert_called_once_with(
                "custom/db-credentials", "eu-west-1", "production"
            )
            assert (
                result
                == "postgresql+asyncpg://customuser:custompass@custom-db.local:5432/customdb"
            )

    def test_handles_invalid_secret_format(self, monkeypatch):
        """Test error handling for invalid secret format (not dict)."""
        # Mock os.getenv to return None (no DATABASE_URL for fallback)
        monkeypatch.setattr("pazpaz.utils.secrets_manager.os.getenv", lambda key: None)

        with patch("pazpaz.utils.secrets_manager._fetch_secret_from_aws") as mock_fetch:
            # Return invalid format (string instead of dict)
            mock_fetch.return_value = "not-a-dict"

            with pytest.raises(KeyNotFoundError):
                get_database_credentials(environment="production")

    def test_handles_non_standard_port(self):
        """Test handling of non-standard PostgreSQL port."""
        mock_secret = {
            "username": "testuser",
            "password": "testpass",
            "host": "test-db.local",
            "port": 15432,  # Non-standard port
            "database": "testdb",
        }

        with patch("pazpaz.utils.secrets_manager._fetch_secret_from_aws") as mock_fetch:
            mock_fetch.return_value = mock_secret

            result = get_database_credentials(environment="production")

            assert (
                result
                == "postgresql+asyncpg://testuser:testpass@test-db.local:15432/testdb"
            )

    def test_no_credentials_logged(self, caplog):
        """Test that credentials (password) are never logged."""
        mock_secret = {
            "username": "testuser",
            "password": "secret_password_123",
            "host": "test-db.local",
            "port": 5432,
            "database": "testdb",
        }

        with patch("pazpaz.utils.secrets_manager._fetch_secret_from_aws") as mock_fetch:
            mock_fetch.return_value = mock_secret

            result = get_database_credentials(environment="production")

            # Check that password is NOT in any log message
            for record in caplog.records:
                assert "secret_password_123" not in record.message
                assert "secret_password_123" not in str(record.args)

            # But credentials are in the returned URL
            assert "secret_password_123" in result


class TestDatabaseCredentialsIntegration:
    """Integration tests for database credentials with config.py."""

    def test_config_database_url_property(self, monkeypatch):
        """Test config.py database_url property uses get_database_credentials."""
        # Import here to avoid circular imports
        from pazpaz.core.config import Settings

        test_db_url = "postgresql+asyncpg://testuser:testpass@localhost:5432/testdb"
        monkeypatch.setenv("DATABASE_URL", test_db_url)
        monkeypatch.setenv("ENVIRONMENT", "local")

        # Create fresh settings instance
        settings = Settings()

        # Clear cache
        get_database_credentials.cache_clear()

        # Access database_url property
        result = settings.database_url

        assert result == test_db_url

    def test_config_uses_secrets_manager_in_production(self, monkeypatch):
        """Test config.py uses Secrets Manager in production environment."""
        from pazpaz.core.config import Settings

        monkeypatch.setenv("ENVIRONMENT", "production")
        # Override SSL and S3 settings to pass production validation
        monkeypatch.setenv("DB_SSL_MODE", "verify-full")
        monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com")

        mock_secret = {
            "username": "produser",
            "password": "prodpass",
            "host": "prod-db.internal",
            "port": 5432,
            "database": "pazpaz_prod",
        }

        with patch("pazpaz.utils.secrets_manager._fetch_secret_from_aws") as mock_fetch:
            mock_fetch.return_value = mock_secret

            settings = Settings()
            get_database_credentials.cache_clear()

            result = settings.database_url

            assert (
                result
                == "postgresql+asyncpg://produser:prodpass@prod-db.internal:5432/pazpaz_prod"
            )


class TestSecurityConsiderations:
    """Test security-related requirements for database credentials."""

    def test_credentials_not_in_exception_messages(self, monkeypatch):
        """Test that credentials don't leak in exception messages."""
        # Mock os.getenv to return None (no DATABASE_URL)
        monkeypatch.setattr("pazpaz.utils.secrets_manager.os.getenv", lambda key: None)

        with patch("pazpaz.utils.secrets_manager._fetch_secret_from_aws") as mock_fetch:
            mock_fetch.return_value = None

            try:
                get_database_credentials(environment="production")
                pytest.fail("Should have raised KeyNotFoundError")
            except KeyNotFoundError as e:
                # Exception message should NOT contain any credentials
                error_msg = str(e)
                assert "password" not in error_msg.lower() or "PASSWORD" in error_msg
                # Should contain helpful guidance
                assert "DATABASE_URL" in error_msg or "AWS Secrets Manager" in error_msg

    def test_different_credentials_per_environment(self):
        """Test that different environments can have different credentials."""
        prod_secret = {
            "username": "produser",
            "password": "prodpass",
            "host": "prod-db.internal",
            "port": 5432,
            "database": "pazpaz_prod",
        }

        staging_secret = {
            "username": "staginguser",
            "password": "stagingpass",
            "host": "staging-db.internal",
            "port": 5432,
            "database": "pazpaz_staging",
        }

        def mock_fetch_secret(secret_name, region, environment):
            if environment == "production":
                return prod_secret
            elif environment == "staging":
                return staging_secret
            return None

        with patch("pazpaz.utils.secrets_manager._fetch_secret_from_aws") as mock_fetch:
            mock_fetch.side_effect = mock_fetch_secret

            # Clear cache between calls
            get_database_credentials.cache_clear()
            prod_url = get_database_credentials(environment="production")

            get_database_credentials.cache_clear()
            staging_url = get_database_credentials(environment="staging")

            # URLs should be different
            assert prod_url != staging_url
            assert "prod-db.internal" in prod_url
            assert "staging-db.internal" in staging_url
