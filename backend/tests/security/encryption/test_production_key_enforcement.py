"""
Test production enforcement of AWS Secrets Manager for encryption keys.

Security Requirement: Production/staging MUST use AWS Secrets Manager (fail-closed).
HIPAA Compliance: §164.312(a)(2)(iv), §164.312(b)
"""

import base64

import pytest

from pazpaz.core.constants import ENCRYPTION_KEY_SIZE
from pazpaz.utils.secrets_manager import KeyNotFoundError, get_encryption_key


class TestProductionKeyEnforcement:
    """Test that production enforces AWS Secrets Manager usage."""

    @pytest.fixture(autouse=True)
    def clear_lru_cache(self):
        """Clear LRU cache before each test."""
        get_encryption_key.cache_clear()
        yield
        get_encryption_key.cache_clear()

    def test_production_requires_aws_secrets_manager(self, monkeypatch):
        """Production must use AWS Secrets Manager (no env fallback)."""
        # Set environment to production
        monkeypatch.setenv("ENVIRONMENT", "production")

        # Set environment variable (should be ignored)
        fake_key = "x" * 64  # 32 bytes base64
        monkeypatch.setenv("ENCRYPTION_MASTER_KEY", fake_key)

        # Mock AWS to return None (simulating unavailability)
        from unittest.mock import patch

        with patch("pazpaz.utils.secrets_manager._fetch_secret_from_aws") as mock_aws:
            mock_aws.return_value = None

            # Should raise KeyNotFoundError (fail-closed)
            with pytest.raises(KeyNotFoundError) as exc_info:
                get_encryption_key(environment="production")

            assert "AWS Secrets Manager" in str(exc_info.value)
            assert "fallback is DISABLED" in str(exc_info.value)
            assert "production" in str(exc_info.value)

    def test_staging_requires_aws_secrets_manager(self, monkeypatch):
        """Staging must use AWS Secrets Manager (no env fallback)."""
        monkeypatch.setenv("ENVIRONMENT", "staging")
        monkeypatch.setenv("ENCRYPTION_MASTER_KEY", "x" * 64)

        from unittest.mock import patch

        with patch("pazpaz.utils.secrets_manager._fetch_secret_from_aws") as mock_aws:
            mock_aws.return_value = None

            with pytest.raises(KeyNotFoundError) as exc_info:
                get_encryption_key(environment="staging")

            assert "AWS Secrets Manager" in str(exc_info.value)
            assert "staging" in str(exc_info.value)

    def test_production_succeeds_with_aws_key(self, monkeypatch):
        """Production successfully loads key from AWS Secrets Manager."""
        import secrets

        monkeypatch.setenv("ENVIRONMENT", "production")

        # Generate valid 32-byte key
        valid_key = secrets.token_bytes(ENCRYPTION_KEY_SIZE)
        valid_key_b64 = base64.b64encode(valid_key).decode()

        from unittest.mock import patch

        with patch("pazpaz.utils.secrets_manager._fetch_secret_from_aws") as mock_aws:
            mock_aws.return_value = {"encryption_key": valid_key_b64}

            # Should succeed
            result = get_encryption_key(environment="production")

            assert result == valid_key
            assert len(result) == ENCRYPTION_KEY_SIZE
            mock_aws.assert_called_once()

    def test_production_rejects_env_variable(self, monkeypatch):
        """Production ignores ENCRYPTION_MASTER_KEY environment variable."""
        monkeypatch.setenv("ENVIRONMENT", "production")

        # Set environment variable with valid key
        env_key = base64.b64encode(b"A" * ENCRYPTION_KEY_SIZE).decode()
        monkeypatch.setenv("ENCRYPTION_MASTER_KEY", env_key)

        # Mock AWS to return different key
        aws_key = b"B" * ENCRYPTION_KEY_SIZE
        aws_key_b64 = base64.b64encode(aws_key).decode()

        from unittest.mock import patch

        with patch("pazpaz.utils.secrets_manager._fetch_secret_from_aws") as mock_aws:
            mock_aws.return_value = {"encryption_key": aws_key_b64}

            result = get_encryption_key(environment="production")

            # Should return AWS key, NOT env key
            assert result == aws_key
            assert result != base64.b64decode(env_key)

    def test_local_allows_env_variable(self, monkeypatch):
        """Local environment can use ENCRYPTION_MASTER_KEY from .env."""
        monkeypatch.setenv("ENVIRONMENT", "local")

        # Set environment variable with valid key
        env_key_bytes = b"C" * ENCRYPTION_KEY_SIZE
        env_key_b64 = base64.b64encode(env_key_bytes).decode()
        monkeypatch.setenv("ENCRYPTION_MASTER_KEY", env_key_b64)

        # Don't mock AWS (shouldn't be called if env key exists)
        result = get_encryption_key(environment="local")

        assert result == env_key_bytes

    def test_local_tries_aws_if_no_env_key(self, monkeypatch):
        """Local can try AWS Secrets Manager if no env key exists."""
        monkeypatch.setenv("ENVIRONMENT", "local")
        monkeypatch.delenv("ENCRYPTION_MASTER_KEY", raising=False)

        # Also ensure .env file isn't loaded by patching _get_key_from_env
        aws_key = b"D" * ENCRYPTION_KEY_SIZE
        aws_key_b64 = base64.b64encode(aws_key).decode()

        from unittest.mock import patch

        with patch("pazpaz.utils.secrets_manager._get_key_from_env") as mock_env:
            mock_env.return_value = None  # No env key available
            with patch(
                "pazpaz.utils.secrets_manager._fetch_secret_from_aws"
            ) as mock_aws:
                mock_aws.return_value = {"encryption_key": aws_key_b64}

                result = get_encryption_key(environment="local")

                assert result == aws_key

    def test_local_generates_temp_key_if_nothing_available(self, monkeypatch):
        """Local generates temporary key if no env or AWS key available."""
        monkeypatch.setenv("ENVIRONMENT", "local")
        monkeypatch.delenv("ENCRYPTION_MASTER_KEY", raising=False)

        from unittest.mock import patch

        with patch("pazpaz.utils.secrets_manager._fetch_secret_from_aws") as mock_aws:
            mock_aws.return_value = None

            # Should generate temporary key without error
            result = get_encryption_key(environment="local")

            assert len(result) == ENCRYPTION_KEY_SIZE
            assert isinstance(result, bytes)

    def test_production_rejects_wrong_key_length_from_aws(self, monkeypatch):
        """Production rejects keys with incorrect length from AWS."""
        monkeypatch.setenv("ENVIRONMENT", "production")

        # Create key with wrong length (16 bytes instead of 32)
        wrong_length_key = b"E" * 16
        wrong_key_b64 = base64.b64encode(wrong_length_key).decode()

        from unittest.mock import patch

        with patch("pazpaz.utils.secrets_manager._fetch_secret_from_aws") as mock_aws:
            mock_aws.return_value = {"encryption_key": wrong_key_b64}

            with pytest.raises(ValueError) as exc_info:
                get_encryption_key(environment="production")

            assert f"{ENCRYPTION_KEY_SIZE} bytes" in str(exc_info.value)

    def test_production_logs_enforcement_message(self, monkeypatch, capsys):
        """Production logs that fallback is disabled."""
        monkeypatch.setenv("ENVIRONMENT", "production")

        valid_key = b"F" * ENCRYPTION_KEY_SIZE
        valid_key_b64 = base64.b64encode(valid_key).decode()

        from unittest.mock import patch

        with patch("pazpaz.utils.secrets_manager._fetch_secret_from_aws") as mock_aws:
            mock_aws.return_value = {"encryption_key": valid_key_b64}

            get_encryption_key(environment="production")

            # Check stdout for enforcement logs (structlog outputs to stdout)
            captured = capsys.readouterr()
            output = captured.out + captured.err

            # Verify logs contain enforcement information
            assert "enforcing_aws_secrets_manager" in output, (
                f"Expected 'enforcing_aws_secrets_manager' in logs. "
                f"Captured output: {output[:500]}"
            )
            assert "fallback_disabled=True" in output, (
                f"Expected 'fallback_disabled=True' in logs. "
                f"Captured output: {output[:500]}"
            )

    def test_development_environment_allows_env_variable(self, monkeypatch):
        """Development environment can use environment variable (not just local)."""
        monkeypatch.setenv("ENVIRONMENT", "development")

        # Set environment variable with valid key
        env_key_bytes = b"G" * ENCRYPTION_KEY_SIZE
        env_key_b64 = base64.b64encode(env_key_bytes).decode()
        monkeypatch.setenv("ENCRYPTION_MASTER_KEY", env_key_b64)

        # Should use environment variable (development is not production/staging)
        result = get_encryption_key(environment="development")

        assert result == env_key_bytes


class TestKeyNotFoundError:
    """Test KeyNotFoundError exception."""

    def test_key_not_found_error_is_exception(self):
        """KeyNotFoundError is a proper exception."""
        error = KeyNotFoundError("test message")
        assert isinstance(error, Exception)
        assert str(error) == "test message"

    def test_key_not_found_error_can_be_caught(self):
        """KeyNotFoundError can be caught and handled."""
        try:
            raise KeyNotFoundError("Key missing")
        except KeyNotFoundError as e:
            assert "Key missing" in str(e)
        else:
            pytest.fail("Exception not raised")
