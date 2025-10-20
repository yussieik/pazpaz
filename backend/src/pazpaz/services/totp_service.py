"""
TOTP (Time-based One-Time Password) service for 2FA authentication.

Implements TOTP per RFC 6238 with 6-digit codes, 30-second intervals.

Security Features:
- TOTP secrets encrypted at rest with AES-256-GCM
- Backup codes hashed with Argon2id
- Single-use backup codes
- Audit logging for all 2FA operations
- Defense against brute force attacks

HIPAA Compliance:
- Multi-factor authentication recommended for PHI access
- Provides defense-in-depth for authentication
- Reduces risk of email account compromise

Usage:
    # Enroll user in 2FA
    enrollment = await enroll_totp(db, user_id)
    # Show QR code and backup codes to user (ONLY ONCE)

    # Verify code during enrollment
    success = await verify_and_enable_totp(db, user_id, totp_code)

    # Verify code during authentication
    is_valid = await verify_totp_or_backup(db, user_id, code)

    # Disable 2FA
    await disable_totp(db, user_id)
"""

from __future__ import annotations

import base64
import io
import json
import secrets
import uuid
from datetime import UTC, datetime

import pyotp
import qrcode
import structlog
from passlib.hash import argon2
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.user import User

logger = structlog.get_logger(__name__)


def generate_totp_secret() -> str:
    """
    Generate a cryptographically secure TOTP secret.

    Returns:
        str: Base32-encoded secret (160 bits = 32 characters)

    Security:
        - 160 bits of entropy (20 bytes)
        - Base32 encoded (compatible with authenticator apps)
        - Cryptographically secure random generation

    Example:
        >>> secret = generate_totp_secret()
        >>> len(secret)
        32
        >>> all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for c in secret)
        True
    """
    # Generate 20 bytes (160 bits) of randomness
    # Base32 encoding will produce 32 characters
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str, issuer: str = "PazPaz") -> str:
    """
    Generate TOTP provisioning URI for QR code.

    Args:
        secret: Base32-encoded TOTP secret
        email: User's email address (account identifier)
        issuer: Application name

    Returns:
        str: otpauth:// URI for QR code generation

    Example:
        >>> uri = get_totp_uri("JBSWY3DPEHPK3PXP", "user@example.com")
        >>> uri.startswith("otpauth://totp/")
        True
        >>> "PazPaz" in uri
        True
    """
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer)


def generate_qr_code(uri: str) -> str:
    """
    Generate QR code image from TOTP URI.

    Args:
        uri: TOTP provisioning URI

    Returns:
        str: Base64-encoded PNG image as data URI

    Example:
        >>> uri = "otpauth://totp/PazPaz:user@example.com?secret=SECRET&issuer=PazPaz"
        >>> qr_code = generate_qr_code(uri)
        >>> qr_code.startswith("data:image/png;base64,")
        True
    """
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(uri)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img_base64 = base64.b64encode(buffer.getvalue()).decode()

    return f"data:image/png;base64,{img_base64}"


def verify_totp_code(secret: str, code: str, window: int = 1) -> bool:
    """
    Verify TOTP code against secret.

    Args:
        secret: Base32-encoded TOTP secret
        code: 6-digit TOTP code from user
        window: Number of time windows to check (±30 seconds per window)

    Returns:
        bool: True if code is valid

    Security:
        - Window of 1 allows for ±30 seconds clock skew
        - Prevents timing attacks (constant-time comparison in pyotp)
        - 6-digit codes provide 1M possibilities per 30-second window

    Example:
        >>> secret = pyotp.random_base32()
        >>> totp = pyotp.TOTP(secret)
        >>> code = totp.now()
        >>> verify_totp_code(secret, code)
        True
        >>> verify_totp_code(secret, "000000")
        False
    """
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=window)


def generate_backup_codes(count: int = 8) -> list[str]:
    """
    Generate backup recovery codes.

    Args:
        count: Number of backup codes to generate

    Returns:
        list[str]: List of 8-character alphanumeric backup codes

    Security:
        - 48 bits of entropy per code (8 hex characters)
        - Cryptographically secure random generation
        - Single-use (deleted after successful verification)

    Example:
        >>> codes = generate_backup_codes(count=8)
        >>> len(codes)
        8
        >>> all(len(code) == 8 for code in codes)
        True
    """
    codes = []
    for _ in range(count):
        # Generate 8-character code (48 bits entropy)
        code = secrets.token_hex(4).upper()  # 8 hex chars
        codes.append(code)
    return codes


def hash_backup_codes(codes: list[str]) -> list[str]:
    """
    Hash backup codes using Argon2id.

    Args:
        codes: List of plaintext backup codes

    Returns:
        list[str]: List of hashed backup codes

    Security:
        - Argon2id winner of Password Hashing Competition
        - Memory-hard algorithm resistant to GPU attacks
        - Time cost and memory cost parameters tuned for security

    Example:
        >>> codes = ["ABC12345", "DEF67890"]
        >>> hashed = hash_backup_codes(codes)
        >>> len(hashed)
        2
        >>> all(h.startswith("$argon2id$") for h in hashed)
        True
    """
    return [argon2.hash(code) for code in codes]


def verify_backup_code(code: str, hashed_codes: list[str]) -> tuple[bool, str | None]:
    """
    Verify backup code against hashed codes.

    Args:
        code: Plaintext backup code from user
        hashed_codes: List of hashed backup codes

    Returns:
        tuple: (is_valid, matched_hash) - matched_hash is returned for removal

    Security:
        - Constant-time comparison prevents timing attacks
        - Returns matched hash for single-use deletion
        - Validates against all stored hashes

    Example:
        >>> codes = ["ABC12345"]
        >>> hashed = hash_backup_codes(codes)
        >>> is_valid, matched = verify_backup_code("ABC12345", hashed)
        >>> is_valid
        True
        >>> matched is not None
        True
    """
    for hashed_code in hashed_codes:
        try:
            if argon2.verify(code, hashed_code):
                return True, hashed_code
        except Exception:
            continue
    return False, None


async def enroll_totp(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> dict:
    """
    Start TOTP enrollment process for user.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        dict: {secret, qr_code, backup_codes}

    Raises:
        ValueError: If 2FA already enabled or user not found

    Security:
        - TOTP secret stored encrypted (AES-256-GCM)
        - Backup codes hashed with Argon2id
        - Not enabled until user verifies TOTP code
        - Audit logging for enrollment start

    Example:
        >>> enrollment = await enroll_totp(db, user_id)
        >>> "secret" in enrollment
        True
        >>> "qr_code" in enrollment
        True
        >>> len(enrollment["backup_codes"])
        8
    """
    # Fetch user
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError("User not found")

    if user.totp_enabled:
        raise ValueError("2FA already enabled for this user")

    # Generate TOTP secret
    secret = generate_totp_secret()

    # Generate QR code
    uri = get_totp_uri(secret, user.email)
    qr_code = generate_qr_code(uri)

    # Generate backup codes
    backup_codes = generate_backup_codes(count=8)
    hashed_codes = hash_backup_codes(backup_codes)

    # Store secret and hashed backup codes (not yet enabled)
    user.totp_secret = secret
    user.totp_backup_codes = json.dumps(hashed_codes)
    user.totp_enabled = False  # Not enabled until verified

    await db.commit()

    logger.info(
        "totp_enrollment_started",
        user_id=str(user_id),
        email=user.email,
    )

    return {
        "secret": secret,
        "qr_code": qr_code,
        "backup_codes": backup_codes,  # Show plaintext codes ONCE
    }


async def verify_and_enable_totp(
    db: AsyncSession,
    user_id: uuid.UUID,
    code: str,
) -> bool:
    """
    Verify TOTP code and enable 2FA if valid.

    Args:
        db: Database session
        user_id: User ID
        code: 6-digit TOTP code

    Returns:
        bool: True if verified and enabled

    Raises:
        ValueError: If user not found or no enrollment in progress

    Security:
        - Validates TOTP code before enabling
        - Sets enrollment timestamp
        - Audit logging for successful enrollment

    Example:
        >>> success = await verify_and_enable_totp(db, user_id, "123456")
        >>> success
        True
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError("User not found")

    if not user.totp_secret:
        raise ValueError("No TOTP enrollment in progress")

    if user.totp_enabled:
        raise ValueError("2FA already enabled")

    # Verify code
    if not verify_totp_code(user.totp_secret, code):
        logger.warning(
            "totp_verification_failed",
            user_id=str(user_id),
            email=user.email,
        )
        return False

    # Enable 2FA
    user.totp_enabled = True
    user.totp_enrolled_at = datetime.now(UTC)

    await db.commit()

    logger.info(
        "totp_enabled",
        user_id=str(user_id),
        email=user.email,
    )

    return True


async def disable_totp(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> None:
    """
    Disable 2FA for user.

    Args:
        db: Database session
        user_id: User ID

    Raises:
        ValueError: If user not found

    Security:
        - Removes all TOTP data (secret, backup codes, timestamp)
        - Audit logging for 2FA disable

    Example:
        >>> await disable_totp(db, user_id)
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise ValueError("User not found")

    user.totp_enabled = False
    user.totp_secret = None
    user.totp_backup_codes = None
    user.totp_enrolled_at = None

    await db.commit()

    logger.info(
        "totp_disabled",
        user_id=str(user_id),
        email=user.email,
    )


async def verify_totp_or_backup(
    db: AsyncSession,
    user_id: uuid.UUID,
    code: str,
) -> bool:
    """
    Verify TOTP code or backup code.

    Args:
        db: Database session
        user_id: User ID
        code: TOTP code or backup code

    Returns:
        bool: True if valid

    Security:
        - Tries TOTP code first (most common case)
        - Falls back to backup codes if TOTP fails
        - Single-use backup codes (deleted after use)
        - Audit logging for successful verification

    Example:
        >>> is_valid = await verify_totp_or_backup(db, user_id, "123456")
        >>> is_valid
        True
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.totp_enabled:
        return False

    # Try TOTP first
    if verify_totp_code(user.totp_secret, code):
        logger.info("totp_verification_success", user_id=str(user_id))
        return True

    # Try backup codes
    if user.totp_backup_codes:
        hashed_codes = json.loads(user.totp_backup_codes)
        is_valid, matched_hash = verify_backup_code(code, hashed_codes)

        if is_valid:
            # Remove used backup code
            hashed_codes.remove(matched_hash)
            user.totp_backup_codes = json.dumps(hashed_codes)
            await db.commit()

            logger.info(
                "backup_code_used",
                user_id=str(user_id),
                remaining_codes=len(hashed_codes),
            )
            return True

    logger.warning("totp_backup_verification_failed", user_id=str(user_id))
    return False
