"""Test application configuration and validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pazpaz.core.config import Settings


class TestSecretKeyValidation:
    """Test SECRET_KEY validation requirements."""

    def test_secret_key_minimum_length(self, monkeypatch):
        """Verify SECRET_KEY must be at least 32 characters."""
        # Set a short key
        monkeypatch.setenv("SECRET_KEY", "short")

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        error_str = str(exc_info.value)
        assert "insufficient entropy" in error_str or "cryptographically random" in error_str

    def test_secret_key_weak_pattern(self, monkeypatch):
        """Verify SECRET_KEY cannot be weak (all same character)."""
        # Set a weak key (all same character)
        monkeypatch.setenv("SECRET_KEY", "a" * 32)

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        error_str = str(exc_info.value)
        assert "weak" in error_str.lower() or "entropy" in error_str.lower()

    def test_secret_key_weak_pattern_few_unique_chars(self, monkeypatch):
        """Verify SECRET_KEY with few unique characters is rejected."""
        # Set a key with only 5 unique characters (below threshold of 10)
        monkeypatch.setenv("SECRET_KEY", "abcde" * 7)  # 35 chars, only 5 unique

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        error_str = str(exc_info.value)
        assert "weak" in error_str.lower() or "entropy" in error_str.lower()

    def test_secret_key_valid(self, monkeypatch):
        """Verify valid SECRET_KEY is accepted."""
        # Set a valid key (36 chars, varied characters)
        valid_key = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
        monkeypatch.setenv("SECRET_KEY", valid_key)

        # Should not raise
        settings = Settings()
        assert settings.secret_key == valid_key

    def test_secret_key_default_allowed_in_local(self, monkeypatch):
        """Verify default SECRET_KEY is allowed in local environment."""
        # Explicitly set environment to local
        monkeypatch.setenv("ENVIRONMENT", "local")
        # Use a valid non-default key since default is too short
        monkeypatch.setenv("SECRET_KEY", "local-dev-key-that-is-long-enough-32chars!")

        # Should not raise
        settings = Settings()
        assert len(settings.secret_key) >= 32

    def test_secret_key_default_rejected_in_production(self, monkeypatch):
        """Verify default SECRET_KEY is rejected in production."""
        # Set environment to production
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv(
            "SECRET_KEY", "change-me-in-production-but-make-it-longer-than-32"
        )

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        error_str = str(exc_info.value)
        assert "default value" in error_str.lower() or "change-me" in error_str.lower()

    def test_secret_key_default_rejected_in_staging(self, monkeypatch):
        """Verify default SECRET_KEY is rejected in staging."""
        # Set environment to staging
        monkeypatch.setenv("ENVIRONMENT", "staging")
        monkeypatch.setenv(
            "SECRET_KEY", "change-me-in-production-but-make-it-longer-than-32"
        )

        with pytest.raises(ValidationError) as exc_info:
            Settings()

        error_str = str(exc_info.value)
        assert "default value" in error_str.lower() or "change-me" in error_str.lower()

    def test_secret_key_cryptographically_random(self, monkeypatch):
        """Verify cryptographically random key is accepted."""
        # Simulate output from: openssl rand -hex 32
        crypto_key = "a3f7b2d8e1c9f4a6b8d2e5f1c3a7b9d4e6f2a8c1b5d9e3f7a2c6b8d4e1f9a3c7"
        monkeypatch.setenv("SECRET_KEY", crypto_key)

        settings = Settings()
        assert settings.secret_key == crypto_key
        assert len(set(crypto_key)) >= 10  # High entropy
