"""Email blacklist utility functions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.logging import get_logger
from pazpaz.models.email_blacklist import EmailBlacklist

logger = get_logger(__name__)


async def is_email_blacklisted(db: AsyncSession, email: str) -> bool:
    """
    Check if an email address is blacklisted (case-insensitive).

    This function checks if the given email exists in the EmailBlacklist table.
    Email comparison is case-insensitive (normalized to lowercase).

    Args:
        db: Database session (async)
        email: Email address to check

    Returns:
        True if email is blacklisted, False otherwise

    Example:
        ```python
        if await is_email_blacklisted(db, "user@example.com"):
            raise HTTPException(403, "This email is blacklisted")
        ```

    Security:
        - Case-insensitive comparison (lowercase normalization)
        - Efficient query with indexed lookup
        - No PII logged (only blacklist status)
    """
    # Normalize email to lowercase for case-insensitive comparison
    normalized_email = email.lower()

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
