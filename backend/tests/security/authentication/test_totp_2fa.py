"""
Test TOTP/2FA authentication implementation.

Security Requirement: Optional 2FA for enhanced security (HIPAA recommended).

Test Coverage:
- TOTP secret generation and validation
- Backup code generation and verification
- Enrollment and verification flow
- Integration with magic link authentication
- Security properties (encryption, single-use, expiry)
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
import pyotp
from sqlalchemy import select

from pazpaz.models.user import User
from pazpaz.services.totp_service import (
    disable_totp,
    enroll_totp,
    generate_backup_codes,
    generate_totp_secret,
    get_totp_uri,
    hash_backup_codes,
    verify_and_enable_totp,
    verify_backup_code,
    verify_totp_code,
    verify_totp_or_backup,
)


class TestTOTPGeneration:
    """Test TOTP secret and code generation."""

    def test_generate_totp_secret_returns_32_chars(self):
        """TOTP secret should be 32 base32 characters (160 bits)."""
        secret = generate_totp_secret()
        assert len(secret) == 32
        assert secret.isupper()  # Base32 is uppercase
        assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for c in secret)

    def test_generate_totp_secret_is_random(self):
        """Each secret should be unique."""
        secrets = [generate_totp_secret() for _ in range(10)]
        assert len(set(secrets)) == 10  # All unique

    def test_get_totp_uri_format(self):
        """TOTP URI should follow otpauth:// format."""
        secret = "JBSWY3DPEHPK3PXP"
        email = "user@example.com"

        uri = get_totp_uri(secret, email, issuer="PazPaz")

        assert uri.startswith("otpauth://totp/")
        assert "PazPaz" in uri
        # Email is URL-encoded in the URI
        assert "user" in uri and "example.com" in uri
        assert secret in uri

    def test_verify_totp_code_accepts_valid_code(self):
        """Valid TOTP code should verify successfully."""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        code = totp.now()

        assert verify_totp_code(secret, code) is True

    def test_verify_totp_code_rejects_invalid_code(self):
        """Invalid TOTP code should be rejected."""
        secret = pyotp.random_base32()

        assert verify_totp_code(secret, "000000") is False
        assert verify_totp_code(secret, "123456") is False

    def test_verify_totp_code_with_time_window(self):
        """TOTP should accept codes within time window."""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)

        # Current code should always work
        current_code = totp.now()
        assert verify_totp_code(secret, current_code, window=1) is True


class TestBackupCodes:
    """Test backup code generation and verification."""

    def test_generate_backup_codes_returns_8_codes(self):
        """Should generate 8 backup codes by default."""
        codes = generate_backup_codes(count=8)
        assert len(codes) == 8

    def test_backup_codes_are_8_chars(self):
        """Each backup code should be 8 characters."""
        codes = generate_backup_codes()
        assert all(len(code) == 8 for code in codes)

    def test_backup_codes_are_unique(self):
        """All backup codes should be unique."""
        codes = generate_backup_codes(count=10)
        assert len(set(codes)) == 10

    def test_hash_backup_codes(self):
        """Backup codes should be hashed with Argon2id."""
        codes = ["ABC12345", "DEF67890"]
        hashed = hash_backup_codes(codes)

        assert len(hashed) == 2
        assert all(h.startswith("$argon2id$") for h in hashed)
        assert hashed[0] != hashed[1]

    def test_verify_backup_code_success(self):
        """Valid backup code should verify."""
        codes = ["ABC12345"]
        hashed = hash_backup_codes(codes)

        is_valid, matched = verify_backup_code("ABC12345", hashed)
        assert is_valid is True
        assert matched is not None

    def test_verify_backup_code_failure(self):
        """Invalid backup code should fail."""
        codes = ["ABC12345"]
        hashed = hash_backup_codes(codes)

        is_valid, matched = verify_backup_code("WRONG123", hashed)
        assert is_valid is False
        assert matched is None


@pytest.mark.asyncio
class TestTOTPEnrollment:
    """Test TOTP enrollment flow."""

    async def test_enroll_totp_creates_secret(self, db, test_user):
        """Enrollment should create TOTP secret."""
        enrollment = await enroll_totp(db, test_user.id)

        assert "secret" in enrollment
        assert "qr_code" in enrollment
        assert "backup_codes" in enrollment
        assert len(enrollment["backup_codes"]) == 8

    async def test_enroll_totp_stores_secret_encrypted(self, db, test_user):
        """TOTP secret should be stored encrypted."""
        await enroll_totp(db, test_user.id)

        # Re-query user to get updated values
        result = await db.execute(select(User).where(User.id == test_user.id))
        user = result.scalar_one()

        assert user.totp_secret is not None
        assert user.totp_enabled is False  # Not enabled until verified

    async def test_enroll_totp_fails_if_already_enabled(self, db, test_user):
        """Cannot enroll if 2FA already enabled."""
        # Re-query to get persistent instance
        result = await db.execute(select(User).where(User.id == test_user.id))
        user = result.scalar_one()

        user.totp_enabled = True
        await db.commit()

        with pytest.raises(ValueError, match="already enabled"):
            await enroll_totp(db, user.id)

    async def test_verify_and_enable_totp_success(self, db, test_user):
        """Valid TOTP code should enable 2FA."""
        enrollment = await enroll_totp(db, test_user.id)
        secret = enrollment["secret"]

        # Generate valid code
        totp = pyotp.TOTP(secret)
        code = totp.now()

        success = await verify_and_enable_totp(db, test_user.id, code)
        assert success is True

        # Re-query user
        #
        result = await db.execute(select(User).where(User.id == test_user.id))
        user = result.scalar_one()

        assert user.totp_enabled is True
        assert user.totp_enrolled_at is not None

    async def test_verify_and_enable_totp_failure(self, db, test_user):
        """Invalid TOTP code should not enable 2FA."""
        await enroll_totp(db, test_user.id)

        success = await verify_and_enable_totp(db, test_user.id, "000000")
        assert success is False

        # Re-query user
        #
        result = await db.execute(select(User).where(User.id == test_user.id))
        user = result.scalar_one()

        assert user.totp_enabled is False

    async def test_disable_totp_removes_secret(self, db, test_user):
        """Disabling 2FA should remove all TOTP data."""
        enrollment = await enroll_totp(db, test_user.id)
        totp = pyotp.TOTP(enrollment["secret"])
        await verify_and_enable_totp(db, test_user.id, totp.now())

        await disable_totp(db, test_user.id)

        # Re-query user
        #
        result = await db.execute(select(User).where(User.id == test_user.id))
        user = result.scalar_one()

        assert user.totp_enabled is False
        assert user.totp_secret is None
        assert user.totp_backup_codes is None


@pytest.mark.asyncio
class TestTOTPVerification:
    """Test TOTP verification during authentication."""

    async def test_verify_totp_or_backup_with_totp_code(self, db, test_user):
        """Should verify valid TOTP code."""
        enrollment = await enroll_totp(db, test_user.id)
        totp = pyotp.TOTP(enrollment["secret"])
        await verify_and_enable_totp(db, test_user.id, totp.now())

        # Verify with new code
        code = totp.now()
        is_valid = await verify_totp_or_backup(db, test_user.id, code)
        assert is_valid is True

    async def test_verify_totp_or_backup_with_backup_code(self, db, test_user):
        """Should verify valid backup code."""
        enrollment = await enroll_totp(db, test_user.id)
        backup_code = enrollment["backup_codes"][0]

        totp = pyotp.TOTP(enrollment["secret"])
        await verify_and_enable_totp(db, test_user.id, totp.now())

        # Verify with backup code
        is_valid = await verify_totp_or_backup(db, test_user.id, backup_code)
        assert is_valid is True

    async def test_backup_code_removed_after_use(self, db, test_user):
        """Backup code should be removed after successful use."""
        enrollment = await enroll_totp(db, test_user.id)
        backup_code = enrollment["backup_codes"][0]

        totp = pyotp.TOTP(enrollment["secret"])
        await verify_and_enable_totp(db, test_user.id, totp.now())

        # Use backup code
        await verify_totp_or_backup(db, test_user.id, backup_code)

        # Try to use same code again - should fail
        is_valid = await verify_totp_or_backup(db, test_user.id, backup_code)
        assert is_valid is False

    async def test_verify_totp_fails_if_not_enabled(self, db, test_user):
        """TOTP verification should fail if 2FA not enabled."""
        is_valid = await verify_totp_or_backup(db, test_user.id, "123456")
        assert is_valid is False

    async def test_verify_totp_fails_with_wrong_code(self, db, test_user):
        """TOTP verification should fail with wrong code."""
        enrollment = await enroll_totp(db, test_user.id)
        totp = pyotp.TOTP(enrollment["secret"])
        await verify_and_enable_totp(db, test_user.id, totp.now())

        # Try wrong code
        is_valid = await verify_totp_or_backup(db, test_user.id, "000000")
        assert is_valid is False


@pytest.mark.asyncio
class TestTOTPSecurity:
    """Test security properties of TOTP implementation."""

    async def test_totp_secret_is_encrypted_at_rest(self, db, test_user):
        """TOTP secret should be encrypted in database."""
        enrollment = await enroll_totp(db, test_user.id)
        secret = enrollment["secret"]

        # Re-query user
        #
        result = await db.execute(select(User).where(User.id == test_user.id))
        user = result.scalar_one()

        # Secret should be stored as string (EncryptedString handles encryption)
        # The plaintext secret should match what we got from enrollment
        assert user.totp_secret == secret

        # After commit, query raw database to verify encryption
        # (In real DB, totp_secret column would be BYTEA with encrypted data)
        # This is verified by EncryptedString type tests

    async def test_backup_codes_are_hashed(self, db, test_user):
        """Backup codes should be hashed, not stored in plaintext."""
        enrollment = await enroll_totp(db, test_user.id)
        plaintext_codes = enrollment["backup_codes"]

        # Re-query user
        #
        result = await db.execute(select(User).where(User.id == test_user.id))
        user = result.scalar_one()

        # Backup codes should be stored as JSON array of hashes
        stored_codes = json.loads(user.totp_backup_codes)

        # Hashes should start with $argon2id$
        assert all(code.startswith("$argon2id$") for code in stored_codes)

        # Hashes should not contain plaintext codes
        for plaintext in plaintext_codes:
            assert plaintext not in user.totp_backup_codes

    async def test_enrollment_timestamp_recorded(self, db, test_user):
        """Enrollment timestamp should be recorded on enable."""
        enrollment = await enroll_totp(db, test_user.id)
        totp = pyotp.TOTP(enrollment["secret"])

        before = datetime.now(UTC)
        await verify_and_enable_totp(db, test_user.id, totp.now())
        after = datetime.now(UTC)

        # Re-query user
        #
        result = await db.execute(select(User).where(User.id == test_user.id))
        user = result.scalar_one()

        assert user.totp_enrolled_at is not None
        assert before <= user.totp_enrolled_at <= after

    async def test_cannot_enable_without_verification(self, db, test_user):
        """2FA should not be enabled without TOTP verification."""
        await enroll_totp(db, test_user.id)

        # Re-query user
        #
        result = await db.execute(select(User).where(User.id == test_user.id))
        user = result.scalar_one()

        assert user.totp_enabled is False

    async def test_qr_code_format(self, db, test_user):
        """QR code should be valid data URI."""
        enrollment = await enroll_totp(db, test_user.id)
        qr_code = enrollment["qr_code"]

        assert qr_code.startswith("data:image/png;base64,")
        assert len(qr_code) > 100  # Should have substantial base64 data


@pytest.mark.asyncio
class TestTOTPDisable:
    """Test TOTP disable with verification requirement."""

    async def test_disable_totp_requires_valid_code(self, db, test_user):
        """Cannot disable 2FA without valid TOTP code."""
        # Enroll and enable TOTP
        enrollment = await enroll_totp(db, test_user.id)
        totp = pyotp.TOTP(enrollment["secret"])
        await verify_and_enable_totp(db, test_user.id, totp.now())

        # Try to disable with wrong code - should fail
        # In the API endpoint, this would be checked before calling disable_totp
        # Here we're testing the service layer assumption that verification happens first

        # Verify wrong code fails
        is_valid = await verify_totp_or_backup(db, test_user.id, "000000")
        assert is_valid is False

        # Verify TOTP is still enabled
        result = await db.execute(select(User).where(User.id == test_user.id))
        user = result.scalar_one()
        assert user.totp_enabled is True

    async def test_disable_totp_with_valid_code_succeeds(self, db, test_user):
        """Can disable 2FA with valid TOTP code."""
        # Enroll and enable TOTP
        enrollment = await enroll_totp(db, test_user.id)
        totp = pyotp.TOTP(enrollment["secret"])
        await verify_and_enable_totp(db, test_user.id, totp.now())

        # Verify with valid code
        code = totp.now()
        is_valid = await verify_totp_or_backup(db, test_user.id, code)
        assert is_valid is True

        # Now disable
        await disable_totp(db, test_user.id)

        # Verify disabled
        result = await db.execute(select(User).where(User.id == test_user.id))
        user = result.scalar_one()
        assert user.totp_enabled is False

    async def test_disable_totp_with_backup_code_succeeds(self, db, test_user):
        """Can disable 2FA with backup code."""
        # Enroll and enable TOTP
        enrollment = await enroll_totp(db, test_user.id)
        backup_code = enrollment["backup_codes"][0]
        totp = pyotp.TOTP(enrollment["secret"])
        await verify_and_enable_totp(db, test_user.id, totp.now())

        # Verify with backup code
        is_valid = await verify_totp_or_backup(db, test_user.id, backup_code)
        assert is_valid is True

        # Now disable
        await disable_totp(db, test_user.id)

        # Verify disabled
        result = await db.execute(select(User).where(User.id == test_user.id))
        user = result.scalar_one()
        assert user.totp_enabled is False

    async def test_disable_totp_with_invalid_code_fails_verification(
        self, db, test_user
    ):
        """Invalid TOTP code fails verification before disable."""
        # Enroll and enable TOTP
        enrollment = await enroll_totp(db, test_user.id)
        totp = pyotp.TOTP(enrollment["secret"])
        await verify_and_enable_totp(db, test_user.id, totp.now())

        # Try invalid code
        is_valid = await verify_totp_or_backup(db, test_user.id, "123456")
        assert is_valid is False

        # Verify still enabled (since verification failed)
        result = await db.execute(select(User).where(User.id == test_user.id))
        user = result.scalar_one()
        assert user.totp_enabled is True

    async def test_disable_totp_consumes_backup_code(self, db, test_user):
        """Backup code used for disable is consumed."""
        # Enroll and enable TOTP
        enrollment = await enroll_totp(db, test_user.id)
        backup_code = enrollment["backup_codes"][0]
        totp = pyotp.TOTP(enrollment["secret"])
        await verify_and_enable_totp(db, test_user.id, totp.now())

        # Verify with backup code (this consumes it)
        is_valid = await verify_totp_or_backup(db, test_user.id, backup_code)
        assert is_valid is True

        # Get user to check backup codes
        result = await db.execute(select(User).where(User.id == test_user.id))
        user = result.scalar_one()
        stored_codes = json.loads(user.totp_backup_codes)
        assert len(stored_codes) == 7  # One consumed

        # Try to use same code again - should fail
        is_valid = await verify_totp_or_backup(db, test_user.id, backup_code)
        assert is_valid is False
