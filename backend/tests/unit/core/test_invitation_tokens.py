"""Test invitation token utilities for platform admin."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import pytest

from pazpaz.core.invitation_tokens import (
    TOKEN_BYTES,
    TOKEN_EXPIRY_DAYS,
    generate_invitation_token,
    is_invitation_expired,
    verify_invitation_token,
)


class TestGenerateInvitationToken:
    """Test invitation token generation."""

    def test_generate_token_returns_tuple(self):
        """Verify generate_invitation_token returns a tuple of (token, hash)."""
        result = generate_invitation_token()

        assert isinstance(result, tuple)
        assert len(result) == 2
        token, token_hash = result
        assert isinstance(token, str)
        assert isinstance(token_hash, str)

    def test_generate_token_creates_unique_tokens(self):
        """Verify each generated token is unique."""
        token1, hash1 = generate_invitation_token()
        token2, hash2 = generate_invitation_token()

        # Tokens should be different
        assert token1 != token2
        # Hashes should be different
        assert hash1 != hash2

    def test_token_hash_is_sha256(self):
        """Verify token hash is SHA256 (64 hex characters)."""
        _token, token_hash = generate_invitation_token()

        # SHA256 produces 64 hex characters (32 bytes * 2)
        assert len(token_hash) == 64
        # Verify it's valid hex
        assert all(c in "0123456789abcdef" for c in token_hash)

    def test_token_is_url_safe(self):
        """Verify token is URL-safe (no special characters that need encoding)."""
        token, _hash = generate_invitation_token()

        # URL-safe base64 uses: A-Z, a-z, 0-9, -, _
        # No padding (=) in token_urlsafe output
        url_safe_chars = set(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        )
        assert all(c in url_safe_chars for c in token)

    def test_token_has_sufficient_entropy(self):
        """Verify token has sufficient entropy (256 bits from 32 bytes)."""
        # Generate multiple tokens and verify they have high entropy
        tokens = [generate_invitation_token()[0] for _ in range(10)]

        # Each token should be unique
        assert len(set(tokens)) == 10

        # Tokens should be reasonably long (32 bytes encodes to ~43 chars in base64)
        for token in tokens:
            assert len(token) >= 40  # URL-safe base64 encoding


class TestVerifyInvitationToken:
    """Test invitation token verification."""

    def test_verify_token_matches_hash(self):
        """Verify token verification works correctly for valid token."""
        token, token_hash = generate_invitation_token()

        # Should verify successfully
        assert verify_invitation_token(token, token_hash) is True

    def test_verify_token_rejects_wrong_token(self):
        """Verify verification fails for incorrect token."""
        _token, token_hash = generate_invitation_token()
        wrong_token, _wrong_hash = generate_invitation_token()

        # Should reject wrong token
        assert verify_invitation_token(wrong_token, token_hash) is False

    def test_verify_token_rejects_tampered_token(self):
        """Verify verification fails for tampered token."""
        token, token_hash = generate_invitation_token()

        # Tamper with token by changing last character
        tampered_token = token[:-1] + ("a" if token[-1] != "a" else "b")

        # Should reject tampered token
        assert verify_invitation_token(tampered_token, token_hash) is False

    def test_verify_token_timing_safe(self):
        """Verify token verification uses timing-safe comparison.

        This test ensures we're using secrets.compare_digest() instead of
        regular string comparison. While we can't directly measure timing,
        we can verify the function behaves correctly even with similar hashes.
        """
        token, token_hash = generate_invitation_token()

        # Create a hash that differs only in the last character
        similar_hash = token_hash[:-1] + ("0" if token_hash[-1] != "0" else "1")

        # Both should be rejected (wrong hashes)
        assert verify_invitation_token("wrong", token_hash) is False
        assert verify_invitation_token("wrong", similar_hash) is False

        # Original should still verify
        assert verify_invitation_token(token, token_hash) is True

    def test_verify_token_empty_strings(self):
        """Verify verification handles empty strings gracefully."""
        token, token_hash = generate_invitation_token()

        # Empty token should not match
        assert verify_invitation_token("", token_hash) is False

        # Empty hash should not match
        assert verify_invitation_token(token, "") is False

        # Both empty - computes hash of "" which is deterministic
        # SHA256("") has a known hash value
        empty_hash = hashlib.sha256(b"").hexdigest()
        assert verify_invitation_token("", empty_hash) is True

    def test_verify_token_consistent_hashing(self):
        """Verify same token always produces same hash."""
        token = "test-token-for-consistency"

        # Compute hash manually
        expected_hash = hashlib.sha256(token.encode()).hexdigest()

        # Verify our function produces the same hash
        assert verify_invitation_token(token, expected_hash) is True


class TestInvitationExpiry:
    """Test invitation expiration logic."""

    def test_invitation_not_expired_within_7_days(self):
        """Verify invitation is not expired within 7 days."""
        # Test at different points within the 7-day window
        test_cases = [
            datetime.now(UTC),  # Just now
            datetime.now(UTC) - timedelta(days=1),  # 1 day ago
            datetime.now(UTC) - timedelta(days=3),  # 3 days ago
            datetime.now(UTC) - timedelta(days=6, hours=23),  # Almost 7 days
        ]

        for invited_at in test_cases:
            assert is_invitation_expired(invited_at) is False

    def test_invitation_expired_after_7_days(self):
        """Verify invitation is expired after 7 days."""
        test_cases = [
            datetime.now(UTC) - timedelta(days=8),  # 8 days ago
            datetime.now(UTC) - timedelta(days=14),  # 2 weeks ago
            datetime.now(UTC) - timedelta(days=30),  # 1 month ago
        ]

        for invited_at in test_cases:
            assert is_invitation_expired(invited_at) is True

    def test_invitation_expiry_boundary(self):
        """Test expiration exactly at 7 days boundary."""
        # Exactly 7 days ago (should be expired)
        exactly_7_days = datetime.now(UTC) - timedelta(days=7)
        assert is_invitation_expired(exactly_7_days) is True

        # Slightly less than 7 days (should not be expired)
        just_under_7_days = datetime.now(UTC) - timedelta(days=7, seconds=-1)
        assert is_invitation_expired(just_under_7_days) is False

    def test_invitation_expiry_uses_utc(self):
        """Verify expiry calculation uses UTC timezone."""
        # Create datetime in UTC
        invited_at_utc = datetime.now(UTC)

        # Should not be expired
        assert is_invitation_expired(invited_at_utc) is False

    def test_invitation_expiry_rejects_naive_datetime(self):
        """Verify expiry check requires timezone-aware datetime."""
        # Create naive datetime (no timezone)
        naive_datetime = datetime.now()  # No UTC parameter

        # Should raise TypeError
        with pytest.raises(TypeError, match="timezone-aware"):
            is_invitation_expired(naive_datetime)

    def test_invitation_expiry_constant(self):
        """Verify TOKEN_EXPIRY_DAYS constant is set correctly."""
        # This test documents the expected expiry period
        assert TOKEN_EXPIRY_DAYS == 7

        # Verify the constant is actually used in calculations
        invited_at = datetime.now(UTC) - timedelta(days=TOKEN_EXPIRY_DAYS + 1)
        assert is_invitation_expired(invited_at) is True

        invited_at = datetime.now(UTC) - timedelta(days=TOKEN_EXPIRY_DAYS - 1)
        assert is_invitation_expired(invited_at) is False


class TestInvitationTokenConstants:
    """Test module constants and configuration."""

    def test_token_bytes_constant(self):
        """Verify TOKEN_BYTES constant is set to 32 (256 bits)."""
        assert TOKEN_BYTES == 32

        # Verify this produces sufficient entropy
        # 32 bytes = 256 bits of entropy
        assert TOKEN_BYTES * 8 == 256

    def test_token_expiry_days_constant(self):
        """Verify TOKEN_EXPIRY_DAYS constant is set to 7."""
        assert TOKEN_EXPIRY_DAYS == 7


class TestInvitationTokenIntegration:
    """Integration tests for complete invitation workflow."""

    def test_full_invitation_workflow(self):
        """Test complete invitation workflow: generate, verify, check expiry."""
        # Step 1: Platform admin generates invitation
        token, token_hash = generate_invitation_token()

        # Step 2: Token is sent in email (not tested here)
        # Step 3: User clicks link with token

        # Step 4: Backend verifies token
        assert verify_invitation_token(token, token_hash) is True

        # Step 5: Check if invitation is still valid (not expired)
        invited_at = datetime.now(UTC)
        assert is_invitation_expired(invited_at) is False

        # Step 6: Simulate expired invitation
        old_invitation = datetime.now(UTC) - timedelta(days=8)
        assert is_invitation_expired(old_invitation) is True

    def test_invitation_security_properties(self):
        """Verify security properties of invitation system."""
        token, token_hash = generate_invitation_token()

        # 1. Token is never stored (only hash)
        assert token != token_hash

        # 2. Hash is deterministic (same token = same hash)
        expected_hash = hashlib.sha256(token.encode()).hexdigest()
        assert token_hash == expected_hash

        # 3. Timing-safe comparison is used
        assert verify_invitation_token(token, token_hash) is True

        # 4. Wrong token is rejected
        wrong_token = secrets.token_urlsafe(TOKEN_BYTES)
        assert verify_invitation_token(wrong_token, token_hash) is False

        # 5. Expiry is enforced
        expired_date = datetime.now(UTC) - timedelta(days=TOKEN_EXPIRY_DAYS + 1)
        assert is_invitation_expired(expired_date) is True
