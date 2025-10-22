"""Email blacklist utility functions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.logging import get_logger
from pazpaz.models.email_blacklist import EmailBlacklist

logger = get_logger(__name__)


async def is_email_blacklisted(db: AsyncSession, email: str) -> bool:
    """
    Check if an email address is blacklisted (case-insensitive, whitespace-trimmed).

    This function checks if the given email exists in the EmailBlacklist table.
    Email comparison is case-insensitive (normalized to lowercase) and
    whitespace-trimmed to prevent bypass attacks.

    Security: FAILS CLOSED - if database check fails, raises exception
    to prevent blacklisted users from bypassing check.

    Args:
        db: Database session (async)
        email: Email address to check (will be normalized)

    Returns:
        True if email is blacklisted, False if not

    Raises:
        RuntimeError: If database check fails (fail-closed security)

    Example:
        ```python
        try:
            if await is_email_blacklisted(db, "user@example.com"):
                raise HTTPException(403, "This email is blacklisted")
        except RuntimeError as e:
            # Database check failed - fail closed
            raise HTTPException(503, "Service unavailable")
        ```

    Security:
        - Whitespace trimming (prevents bypass via leading/trailing spaces)
        - Case-insensitive comparison (lowercase normalization)
        - Efficient query with indexed lookup
        - No PII logged (only blacklist status)
        - FAILS CLOSED on database errors (raises RuntimeError)
    """
    try:
        # Normalize email: strip whitespace + lowercase
        normalized_email = email.strip().lower()

        # Query blacklist table (indexed on email column)
        result = await db.scalar(
            select(EmailBlacklist.id)
            .where(EmailBlacklist.email == normalized_email)
            .limit(1)
        )

        is_blacklisted = result is not None

        if is_blacklisted:
            logger.warning(
                "blacklisted_email_detected",
                email_hash=hash(normalized_email),  # Log hash, not actual email
            )

        return is_blacklisted

    except Exception as e:
        # FAIL CLOSED: If we can't verify blacklist status, block the request
        logger.critical(
            "blacklist_check_failed_failing_closed",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        # Raise exception to fail closed (caller must handle this)
        raise RuntimeError(
            "Unable to verify email blacklist status. Request blocked for security."
        ) from e
