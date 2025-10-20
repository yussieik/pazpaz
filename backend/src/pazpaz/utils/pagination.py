"""Pagination utilities for API endpoints.

Security Controls:
- Integer overflow protection: Validates pagination parameters against safe limits
- Prevents database crashes from oversized integers (2**128, 2**63, etc.)
- Validates page and page_size fit within PostgreSQL int64 range
- Prevents memory exhaustion from large offset calculations

OWASP Reference:
- OWASP API Security Top 10 - API4:2023 Unrestricted Resource Consumption
- CWE-190: Integer Overflow or Wraparound
- CWE-1284: Improper Validation of Specified Quantity in Input
"""

from __future__ import annotations

import math
import sys
from typing import TypeVar

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from pazpaz.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

# PostgreSQL int64 range: -2^63 to 2^63-1
# We use signed 32-bit int max for safer bounds (supports up to 2 billion records)
# This prevents offset calculation from overflowing int64
MAX_SAFE_PAGE = 2**31 - 1  # 2,147,483,647
MAX_SAFE_PAGE_SIZE = 1000  # Reasonable limit for API pagination

# Python's sys.maxsize is platform-dependent (typically 2^63-1 on 64-bit systems)
# We ensure calculations don't exceed this to prevent Python integer overflow
MAX_SAFE_OFFSET = min(sys.maxsize, 2**63 - 1)


def validate_pagination_params(page: int, page_size: int) -> None:
    """
    Validate pagination parameters are within safe integer bounds.

    This prevents integer overflow attacks that can crash the database or
    cause unexpected behavior.

    Security Validations:
    - page must be >= 1 (enforced by Pydantic)
    - page must be <= MAX_SAFE_PAGE (2^31-1)
    - page_size must be >= 1 (enforced by Pydantic)
    - page_size must be <= MAX_SAFE_PAGE_SIZE (1000)
    - offset calculation must not exceed MAX_SAFE_OFFSET (2^63-1)

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page

    Raises:
        HTTPException: 422 if parameters exceed safe limits

    Example:
        >>> validate_pagination_params(1, 50)  # OK
        >>> validate_pagination_params(2**63, 50)  # Raises HTTPException
    """
    # Validate page is within safe range
    if page > MAX_SAFE_PAGE:
        logger.warning(
            "pagination_page_overflow",
            page=page,
            max_safe_page=MAX_SAFE_PAGE,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Page number {page} exceeds maximum safe value of {MAX_SAFE_PAGE}. "
                "Please use a smaller page number."
            ),
        )

    # Validate page_size is within safe range
    if page_size > MAX_SAFE_PAGE_SIZE:
        logger.warning(
            "pagination_page_size_overflow",
            page_size=page_size,
            max_safe_page_size=MAX_SAFE_PAGE_SIZE,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Page size {page_size} exceeds maximum safe value of {MAX_SAFE_PAGE_SIZE}. "
                "Please use a smaller page size."
            ),
        )

    # Validate offset calculation won't overflow
    # Calculate offset safely and check if it exceeds limit
    offset = (page - 1) * page_size
    if offset > MAX_SAFE_OFFSET:
        logger.warning(
            "pagination_offset_overflow",
            page=page,
            page_size=page_size,
            calculated_offset=offset,
            max_safe_offset=MAX_SAFE_OFFSET,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Calculated offset ({offset}) exceeds maximum safe value. "
                "Please use smaller page number or page size."
            ),
        )

    logger.debug(
        "pagination_params_validated",
        page=page,
        page_size=page_size,
        offset=offset,
    )


def calculate_pagination_offset(page: int, page_size: int) -> int:
    """
    Calculate database query offset from page number and page size.

    Security Note: This function assumes pagination parameters have already
    been validated by validate_pagination_params(). Always call
    validate_pagination_params() before this function to prevent integer overflow.

    Args:
        page: Page number (1-indexed, must be validated)
        page_size: Number of items per page (must be validated)

    Returns:
        Offset for database query (0-indexed)

    Example:
        >>> calculate_pagination_offset(1, 50)
        0
        >>> calculate_pagination_offset(2, 50)
        50
        >>> calculate_pagination_offset(3, 25)
        50
    """
    # Note: No validation here - caller MUST call validate_pagination_params() first
    return (page - 1) * page_size


def calculate_total_pages(total: int, page_size: int) -> int:
    """
    Calculate total number of pages from total items and page size.

    Args:
        total: Total number of items
        page_size: Number of items per page

    Returns:
        Total number of pages (0 if total is 0)

    Example:
        >>> calculate_total_pages(100, 50)
        2
        >>> calculate_total_pages(75, 25)
        3
        >>> calculate_total_pages(0, 50)
        0
        >>> calculate_total_pages(1, 50)
        1
    """
    return math.ceil(total / page_size) if total > 0 else 0


async def get_query_total_count(db: AsyncSession, base_query: Select) -> int:
    """
    Get total count of results from a base query.

    This is optimized for counting results from filtered queries without
    loading the actual data.

    Args:
        db: Database session
        base_query: Base SQLAlchemy query to count results from

    Returns:
        Total count of results

    Example:
        >>> base_query = select(Client).where(Client.workspace_id == workspace_id)
        >>> total = await get_query_total_count(db, base_query)
        >>> print(f"Found {total} clients")
    """
    count_query = select(func.count()).select_from(base_query.subquery())
    result = await db.execute(count_query)
    return result.scalar_one()


class PaginatedResponse(BaseModel):
    """
    Generic paginated response schema.

    This eliminates duplicate list response schemas across entities.

    Type Parameters:
        T: The type of items in the response

    Example:
        >>> from pazpaz.schemas.client import ClientResponse
        >>> ClientListResponse = PaginatedResponse[ClientResponse]
    """

    items: list[T]  # type: ignore[valid-type]
    total: int
    page: int
    page_size: int
    total_pages: int
