"""Security utilities for JWT token generation and validation."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)

# Password hashing context with Argon2id (OWASP recommended)
# Argon2id provides best resistance against:
# - GPU cracking attacks (memory-hard)
# - ASIC attacks (memory-hard with timing resistance)
# - Side-channel attacks (time-constant verification)
#
# Parameters tuned for ~500ms hashing time on modern hardware (2024):
# - memory_cost: 65536 KB (64 MB) - recommended OWASP minimum
# - time_cost: 3 iterations
# - parallelism: 4 threads
#
# Bcrypt is retained for backward compatibility and will auto-rehash
# to Argon2id on next successful login (transparent migration)
pwd_context = CryptContext(
    schemes=["argon2", "bcrypt"],  # Argon2id primary, bcrypt for migration
    deprecated=["bcrypt"],  # Mark bcrypt for auto-rehashing
    argon2__memory_cost=65536,  # 64 MB memory (OWASP minimum)
    argon2__time_cost=3,  # 3 iterations
    argon2__parallelism=4,  # 4 threads
    argon2__type="ID",  # Use Argon2id variant (hybrid resistance)
)

"""
Password Hashing Migration Strategy
===================================

The application currently uses passwordless authentication (magic links),
but maintains password hashing for future use.

Migration from bcrypt to Argon2id:
1. New passwords: Always hashed with Argon2id
2. Existing passwords: Verified with bcrypt, auto-rehashed to Argon2id on next login
3. Transparent migration: No user action required

If password authentication is enabled in the future:
1. Verify password with verify_password() (handles both algorithms)
2. Check needs_rehash() after successful verification
3. If True, rehash with get_password_hash() and update database
4. This provides transparent migration from bcrypt to Argon2id

Example migration code:
```python
if verify_password(plain_password, user.hashed_password):
    # Password is correct
    if needs_rehash(user.hashed_password):
        # Upgrade from bcrypt to Argon2id
        user.hashed_password = get_password_hash(plain_password)
        await db.commit()
    # ... proceed with authentication
```
"""


def create_access_token(
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    email: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: User's UUID
        workspace_id: User's workspace UUID
        email: User's email address
        expires_delta: Token expiration time (defaults to 7 days)

    Returns:
        Encoded JWT token string
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

    expire = datetime.now(UTC) + expires_delta

    to_encode = {
        "sub": str(user_id),  # Subject (standard JWT claim)
        "user_id": str(user_id),
        "workspace_id": str(workspace_id),
        "email": email,
        "exp": expire,
        "iat": datetime.now(UTC),  # Issued at
        "jti": str(uuid.uuid4()),  # JWT ID for blacklisting
    }

    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm="HS256",
    )

    return encoded_jwt


def decode_access_token(token: str) -> dict[str, str]:
    """
    Decode and validate JWT access token with comprehensive security checks.

    Security hardening:
    - Explicitly verify algorithm matches expected (prevents alg: none)
    - Require all expected claims (prevents claim omission)
    - Validate signature (prevents unsigned tokens)
    - Defense-in-depth expiration checking

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        HTTPException: 401 Unauthorized if token is invalid, expired, or malformed
    """
    try:
        # STEP 1: Verify algorithm header BEFORE decoding
        # This prevents algorithm confusion attacks (alg: none, RS256 key confusion)
        unverified_header = jwt.get_unverified_header(token)
        expected_algorithm = "HS256"

        if unverified_header.get("alg") != expected_algorithm:
            logger.warning(
                "jwt_algorithm_mismatch",
                expected=expected_algorithm,
                got=unverified_header.get("alg"),
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # STEP 2: Decode with strict validation
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[expected_algorithm],  # Explicit algorithm whitelist
            options={
                "verify_signature": True,  # Explicitly require signature
                "verify_exp": True,  # Explicitly require expiration check
            },
        )

        # STEP 3: Validate all required claims are present
        # Note: python-jose doesn't support 'require' option for custom claims,
        # so we validate manually
        required_claims = ["exp", "sub", "user_id", "workspace_id", "email", "jti"]
        missing_claims = [claim for claim in required_claims if claim not in payload]

        if missing_claims:
            logger.warning(
                "jwt_missing_required_claims",
                missing_claims=missing_claims,
                token_preview=token[:20],
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # STEP 4: Defense-in-depth: Additional expiration check
        exp = payload.get("exp")
        if not exp:
            logger.warning("jwt_missing_expiration", token_preview=token[:20])
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verify expiration hasn't been tampered with
        exp_datetime = datetime.fromtimestamp(exp, tz=UTC)
        if exp_datetime < datetime.now(UTC):
            logger.info("jwt_expired", exp=exp_datetime.isoformat())
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return payload

    except HTTPException:
        # Re-raise HTTPException as-is
        raise
    except ExpiredSignatureError as e:
        # Handle expired tokens specifically
        logger.info("jwt_expired_signature", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except JWTError as e:
        logger.warning("jwt_decode_failed", error=str(e), error_type=type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except Exception as e:
        logger.error("jwt_decode_unexpected_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


def validate_password_strength(password: str) -> tuple[bool, str | None]:
    """
    Validate password meets security requirements.

    Requirements based on NIST SP 800-63B and OWASP:
    - Minimum 12 characters (OWASP recommendation)
    - No sequential characters (e.g., "12345", "abcde")
    - No keyboard patterns (e.g., "qwerty", "asdfgh")
    - No excessive character repetition (e.g., "aaaaaaa")

    Args:
        password: Plain text password to validate

    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if password meets requirements
        - error_message: None if valid, error string if invalid

    Examples:
        >>> validate_password_strength("short")
        (False, "Password must be at least 12 characters")

        >>> validate_password_strength("MySecurePassword123!")
        (True, None)
    """
    # Minimum length check
    if len(password) < 12:
        return False, "Password must be at least 12 characters"

    # Maximum length check (prevent DoS)
    if len(password) > 128:
        return False, "Password must be less than 128 characters"

    # Check for common sequential patterns
    sequential_patterns = [
        "0123456789",
        "abcdefghijklmnopqrstuvwxyz",
        "qwertyuiop",
        "asdfghjkl",
        "zxcvbnm",
    ]

    lower_pw = password.lower()
    for pattern in sequential_patterns:
        # Check for 4+ consecutive chars from pattern
        for i in range(len(pattern) - 3):
            if pattern[i : i + 4] in lower_pw:
                return False, "Password contains sequential characters"

    # Check for repeated characters (e.g., "aaaaaaa")
    if re.search(r"(.)\1{5,}", password):
        return False, "Password contains too many repeated characters"

    # Optional: Check for common passwords (implement with wordlist if needed)
    # For now, just check for obvious ones
    common_passwords = {
        "password1234",
        "password12345",
        "password123456",
        "admin1234567",
        "welcome1234567",
        "123456789012",
        "letmein12345",
    }
    if password.lower() in common_passwords:
        return False, "Password is too common"

    return True, None


def get_password_hash(password: str) -> str:
    """
    Hash a password with strength validation using Argon2id.

    Args:
        password: Plain text password

    Returns:
        Hashed password string (Argon2id format)

    Raises:
        ValueError: If password doesn't meet strength requirements

    Examples:
        >>> hash = get_password_hash("MySecurePassword123!")
        >>> verify_password("MySecurePassword123!", hash)
        True
    """
    # Validate password strength before hashing
    is_valid, error = validate_password_strength(password)
    if not is_valid:
        raise ValueError(f"Weak password: {error}")

    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    This function handles both Argon2id and bcrypt hashes for
    backward compatibility during migration.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password (Argon2id or bcrypt)

    Returns:
        True if password matches hash, False otherwise

    Examples:
        >>> hash = get_password_hash("MySecurePassword123!")
        >>> verify_password("MySecurePassword123!", hash)
        True
        >>> verify_password("WrongPassword", hash)
        False
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        # Handle invalid hash format gracefully
        # This can happen with malformed hashes or unsupported formats
        return False


def needs_rehash(hashed_password: str) -> bool:
    """
    Check if a password hash needs to be rehashed.

    This will return True for bcrypt hashes, indicating they should
    be upgraded to Argon2id on next successful login.

    Args:
        hashed_password: Hashed password to check

    Returns:
        True if hash should be upgraded, False otherwise

    Examples:
        >>> bcrypt_hash = "$2b$12$..."
        >>> needs_rehash(bcrypt_hash)
        True
        >>> argon2_hash = "$argon2id$v=19$..."
        >>> needs_rehash(argon2_hash)
        False
    """
    return pwd_context.needs_update(hashed_password)
