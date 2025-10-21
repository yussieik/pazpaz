"""Invitation token utilities for platform admin."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

# Constants
TOKEN_BYTES = 32  # 256-bit tokens (32 bytes = 256 bits)
TOKEN_EXPIRY_DAYS = 7


def generate_invitation_token() -> tuple[str, str]:
    """
    Generate invitation token and its hash.

    Creates a cryptographically strong random token using the secrets module
    (recommended by OWASP for security-sensitive operations). The token is
    URL-safe and can be safely included in email magic links.

    Security properties:
    - 256-bit entropy (32 bytes) prevents brute force attacks
    - URL-safe base64 encoding (no special characters in URLs)
    - SHA256 hash stored in database (token never persisted)
    - Timing-safe verification prevents timing attacks

    Returns:
        Tuple of (token, token_hash):
        - token: URL-safe string to send in email
        - token_hash: SHA256 hex digest to store in database

    Examples:
        >>> token, token_hash = generate_invitation_token()
        >>> len(token_hash)
        64
        >>> verify_invitation_token(token, token_hash)
        True
    """
    token = secrets.token_urlsafe(TOKEN_BYTES)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token, token_hash


def verify_invitation_token(provided_token: str, stored_hash: str) -> bool:
    """
    Verify invitation token matches stored hash.

    Uses timing-safe comparison to prevent timing attacks. Timing attacks
    could potentially allow an attacker to deduce the hash by measuring
    how long the comparison takes (byte-by-byte comparison would reveal
    matching prefixes).

    Security considerations:
    - Uses secrets.compare_digest() for constant-time comparison
    - Prevents timing attacks on token verification
    - Compares hash, not plaintext token (defense in depth)

    Args:
        provided_token: Token from magic link URL parameter
        stored_hash: SHA256 hash stored in database (64 hex characters)

    Returns:
        True if token matches hash, False otherwise

    Examples:
        >>> token, token_hash = generate_invitation_token()
        >>> verify_invitation_token(token, token_hash)
        True
        >>> verify_invitation_token("wrong-token", token_hash)
        False
    """
    computed_hash = hashlib.sha256(provided_token.encode()).hexdigest()
    return secrets.compare_digest(computed_hash, stored_hash)


def is_invitation_expired(invited_at: datetime) -> bool:
    """
    Check if invitation has expired.

    Invitations expire after TOKEN_EXPIRY_DAYS (7 days by default).
    This prevents stale invitations from being used and limits the
    window for potential token compromise.

    Args:
        invited_at: When invitation was sent (timezone-aware datetime in UTC)

    Returns:
        True if invitation is older than TOKEN_EXPIRY_DAYS, False otherwise

    Raises:
        TypeError: If invited_at is not timezone-aware

    Examples:
        >>> from datetime import UTC, datetime, timedelta
        >>> now = datetime.now(UTC)
        >>> is_invitation_expired(now)
        False
        >>> old_date = now - timedelta(days=8)
        >>> is_invitation_expired(old_date)
        True
    """
    # Ensure we're working with timezone-aware datetimes
    if invited_at.tzinfo is None:
        msg = "invited_at must be timezone-aware (use datetime.now(UTC))"
        raise TypeError(msg)

    expiry = invited_at + timedelta(days=TOKEN_EXPIRY_DAYS)
    return datetime.now(UTC) > expiry
