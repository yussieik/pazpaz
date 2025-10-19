"""Security utilities for JWT token generation and validation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from pazpaz.core.config import settings

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
    Decode and validate a JWT access token with expiration checking.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        JWTError: If token is invalid, expired, or malformed
    """
    try:
        # Decode JWT with expiration validation explicitly enabled
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=["HS256"],
            options={"verify_exp": True},  # Explicitly enforce expiration validation
        )

        # Defense-in-depth: Additional expiration check
        exp = payload.get("exp")
        if not exp:
            raise JWTError("Token missing expiration claim")

        # Verify expiration hasn't been tampered with
        exp_datetime = datetime.fromtimestamp(exp, tz=UTC)
        if exp_datetime < datetime.now(UTC):
            raise JWTError("Token has expired")

        return payload
    except JWTError as e:
        raise JWTError("Invalid or expired token") from e


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
