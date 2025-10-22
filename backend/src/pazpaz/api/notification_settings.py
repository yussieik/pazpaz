"""API endpoints for user notification settings.

This module provides endpoints for users to manage their notification preferences:
- GET /api/v1/users/me/notification-settings - Get current settings
- PUT /api/v1/users/me/notification-settings - Update settings

All endpoints require authentication and enforce workspace scoping.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.api.deps import get_current_user, get_db
from pazpaz.core.logging import get_logger
from pazpaz.models.user import User
from pazpaz.schemas.notification_settings import (
    NotificationSettingsResponse,
    NotificationSettingsUpdate,
)
from pazpaz.services import notification_settings_service

router = APIRouter(prefix="/users/me", tags=["notification-settings"])
logger = get_logger(__name__)


@router.get(
    "/notification-settings",
    response_model=NotificationSettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_notification_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationSettingsResponse:
    """
    Get notification settings for the authenticated user.

    Returns the user's current notification preferences including email toggles,
    digest settings, and reminder configurations. If settings don't exist yet,
    returns defaults.

    Args:
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        NotificationSettingsResponse with current settings

    Raises:
        HTTPException:
            - 401 if not authenticated
            - 500 if database error occurs

    Example:
        ```
        GET /api/v1/users/me/notification-settings
        Authorization: Bearer <jwt_token>

        Response 200 OK:
        {
            "id": "uuid",
            "user_id": "uuid",
            "workspace_id": "uuid",
            "email_enabled": true,
            "notify_appointment_booked": true,
            "digest_enabled": false,
            "digest_time": "08:00",
            ...
        }
        ```
    """
    logger.info(
        "get_notification_settings_requested",
        user_id=str(current_user.id),
        workspace_id=str(current_user.workspace_id),
    )

    try:
        # Get or create settings (ensures settings always exist)
        settings = await notification_settings_service.get_or_create_notification_settings(
            db=db,
            user_id=current_user.id,
            workspace_id=current_user.workspace_id,
        )

        logger.info(
            "get_notification_settings_success",
            user_id=str(current_user.id),
            workspace_id=str(current_user.workspace_id),
        )

        return NotificationSettingsResponse.model_validate(settings)

    except Exception as e:
        logger.error(
            "get_notification_settings_failed",
            user_id=str(current_user.id),
            workspace_id=str(current_user.workspace_id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notification settings",
        ) from e


@router.put(
    "/notification-settings",
    response_model=NotificationSettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def update_notification_settings(
    updates: NotificationSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationSettingsResponse:
    """
    Update notification settings for the authenticated user.

    Performs a partial update - only provided fields are modified.
    If settings don't exist, creates them with defaults and applies updates.

    Validates:
    - Time format (HH:MM in 24-hour format, e.g., "08:00", "18:30")
    - Reminder minutes (must be one of: 15, 30, 60, 120, 1440)

    Args:
        updates: NotificationSettingsUpdate with fields to modify
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        NotificationSettingsResponse with updated settings

    Raises:
        HTTPException:
            - 401 if not authenticated
            - 400 if validation fails (invalid time format or reminder minutes)
            - 500 if database error occurs

    Example:
        ```
        PUT /api/v1/users/me/notification-settings
        Authorization: Bearer <jwt_token>
        Content-Type: application/json

        {
            "email_enabled": true,
            "digest_enabled": true,
            "digest_time": "08:00"
        }

        Response 200 OK:
        {
            "id": "uuid",
            "user_id": "uuid",
            "workspace_id": "uuid",
            "email_enabled": true,
            "digest_enabled": true,
            "digest_time": "08:00",
            ...
        }
        ```

        Validation Error Example:
        ```
        PUT /api/v1/users/me/notification-settings
        {
            "digest_time": "25:00"  # Invalid time
        }

        Response 400 Bad Request:
        {
            "detail": "Time must be in HH:MM format (00:00 to 23:59), got: 25:00"
        }
        ```
    """
    logger.info(
        "update_notification_settings_requested",
        user_id=str(current_user.id),
        workspace_id=str(current_user.workspace_id),
        update_fields=list(updates.model_dump(exclude_unset=True).keys()),
    )

    try:
        # Update settings (creates defaults if they don't exist)
        settings = await notification_settings_service.update_notification_settings(
            db=db,
            user_id=current_user.id,
            workspace_id=current_user.workspace_id,
            updates=updates,
        )

        # Commit transaction
        await db.commit()
        await db.refresh(settings)

        logger.info(
            "update_notification_settings_success",
            user_id=str(current_user.id),
            workspace_id=str(current_user.workspace_id),
        )

        return NotificationSettingsResponse.model_validate(settings)

    except ValueError as e:
        # Validation errors (invalid time format or reminder minutes)
        logger.warning(
            "update_notification_settings_validation_error",
            user_id=str(current_user.id),
            workspace_id=str(current_user.workspace_id),
            error=str(e),
        )
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    except Exception as e:
        logger.error(
            "update_notification_settings_failed",
            user_id=str(current_user.id),
            workspace_id=str(current_user.workspace_id),
            error=str(e),
            exc_info=True,
        )
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification settings",
        ) from e
