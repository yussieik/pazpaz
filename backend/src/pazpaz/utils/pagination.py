"""Pagination utilities for API endpoints."""

from __future__ import annotations

import math
from typing import TypeVar

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

T = TypeVar("T")


def calculate_pagination_offset(page: int, page_size: int) -> int:
    """
    Calculate database query offset from page number and page size.

    Args:
        page: Page number (1-indexed)
        page_size: Number of items per page

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
