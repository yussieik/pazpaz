"""Test password hashing migration from bcrypt to Argon2id.

This test suite validates:
1. Argon2id is used for new password hashes
2. Password verification works with Argon2id
3. Backward compatibility with bcrypt hashes
4. Password strength validation
5. Weak passwords are rejected

Security Requirements:
- OWASP A02:2021 - Cryptographic Failures
- Use Argon2id (winner of Password Hashing Competition)
- Enforce strong password requirements

Reference: Week 3, Task 3.1 - Migrate to Argon2id
"""

from __future__ import annotations

import pytest

from pazpaz.core.security import (
    get_password_hash,
    needs_rehash,
    validate_password_strength,
    verify_password,
)


class TestArgon2idHashing:
    """Test Argon2id password hashing implementation."""

    def test_password_hashing_uses_argon2id(self):
        """Verify new passwords are hashed with Argon2id."""
        password = "MySecurePassword123!"
        hashed = get_password_hash(password)

        assert hashed.startswith("$argon2id$")
        assert "v=19" in hashed
        assert "m=65536" in hashed
        assert "t=3" in hashed
        assert "p=4" in hashed

    def test_password_verification_with_argon2id(self):
        """Verify password verification works with Argon2id."""
        password = "MySecurePassword123!"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True
        assert verify_password("WrongPassword", hashed) is False

    def test_bcrypt_hashes_need_rehashing(self):
        """Verify bcrypt hashes are flagged for rehashing."""
        bcrypt_hash = "$2b$12$LvZ5fKqhqHj6cJqZQJ0YTOqN5YKnXJLqKqZQJ0YTOqN5YKnXJLqK."
        assert needs_rehash(bcrypt_hash) is True

    def test_argon2id_hashes_dont_need_rehashing(self):
        """Verify Argon2id hashes don't need rehashing."""
        password = "MySecurePassword123!"
        argon2_hash = get_password_hash(password)
        assert needs_rehash(argon2_hash) is False


class TestPasswordStrengthValidation:
    """Test password strength validation."""

    def test_password_too_short(self):
        """Verify passwords shorter than 12 characters are rejected."""
        valid, error = validate_password_strength("short")
        assert valid is False
        assert "12 characters" in error

    def test_password_sequential_numbers(self):
        """Verify passwords with sequential numbers are rejected."""
        valid, error = validate_password_strength("abc123defgh4567")
        assert valid is False
        assert "sequential" in error.lower()

    def test_password_repeated_characters(self):
        """Verify passwords with excessive repeated characters are rejected."""
        valid, error = validate_password_strength("aaaaaaaaaaaaa")
        assert valid is False
        assert "repeated" in error.lower()

    def test_password_valid_strong(self):
        """Verify strong passwords are accepted."""
        valid, error = validate_password_strength("MySecurePassword123!")
        assert valid is True
        assert error is None


class TestGetPasswordHash:
    """Test get_password_hash function with validation."""

    def test_get_password_hash_rejects_too_short(self):
        """Verify get_password_hash rejects passwords too short."""
        with pytest.raises(ValueError, match="12 characters"):
            get_password_hash("short")

    def test_get_password_hash_rejects_sequential(self):
        """Verify get_password_hash rejects sequential characters."""
        with pytest.raises(ValueError, match="sequential"):
            get_password_hash("abc123defgh4567")

    def test_get_password_hash_accepts_strong(self):
        """Verify get_password_hash accepts strong passwords."""
        password = "MySecurePassword123!"
        hashed = get_password_hash(password)

        assert hashed.startswith("$argon2id$")
        assert verify_password(password, hashed) is True
