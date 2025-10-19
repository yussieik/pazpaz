"""Security utilities for JWT token generation and validation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)

# Password hashing context (for future password-based auth if needed)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


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


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hashed password.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password for storage.

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    return pwd_context.hash(password)
