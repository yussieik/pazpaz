"""Service layer for user notification settings management."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.logging import get_logger
from pazpaz.models.user_notification_settings import UserNotificationSettings
from pazpaz.schemas.notification_settings import NotificationSettingsUpdate

logger = get_logger(__name__)


async def get_notification_settings(
    db: AsyncSession,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> UserNotificationSettings | None:
    """
    Get notification settings for a user.

    Args:
        db: Database session
        user_id: User ID
        workspace_id: Workspace ID (for workspace scoping)

    Returns:
        UserNotificationSettings instance or None if not found

    Example:
        ```python
        settings = await get_notification_settings(db, user_id, workspace_id)
        if settings is None:
            # Settings don't exist yet - create defaults
            settings = await create_default_settings(db, user_id, workspace_id)
        ```
    """
    query = select(UserNotificationSettings).where(
        UserNotificationSettings.user_id == user_id,
        UserNotificationSettings.workspace_id == workspace_id,
    )
    result = await db.execute(query)
    settings = result.scalar_one_or_none()

    if settings:
        logger.debug(
            "notification_settings_retrieved",
            user_id=str(user_id),
            workspace_id=str(workspace_id),
        )
    else:
        logger.debug(
            "notification_settings_not_found",
            user_id=str(user_id),
            workspace_id=str(workspace_id),
        )

    return settings


async def create_default_settings(
    db: AsyncSession,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> UserNotificationSettings:
    """
    Create default notification settings for a new user.

    This function creates a new UserNotificationSettings record with server defaults.
    All default values are defined in the database model and will be applied automatically.

    Args:
        db: Database session
        user_id: User ID
        workspace_id: Workspace ID

    Returns:
        Newly created UserNotificationSettings instance

    Raises:
        Exception: If settings already exist or database operation fails

    Example:
        ```python
        # After creating a new user
        settings = await create_default_settings(db, user.id, user.workspace_id)
        await db.commit()
        ```
    """
    settings = UserNotificationSettings(
        user_id=user_id,
        workspace_id=workspace_id,
        # All other fields use server defaults from the model
    )

    db.add(settings)
    await db.flush()  # Flush to get server defaults applied
    await db.refresh(settings)

    logger.info(
        "notification_settings_created",
        user_id=str(user_id),
        workspace_id=str(workspace_id),
    )

    return settings


async def update_notification_settings(
    db: AsyncSession,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
    updates: NotificationSettingsUpdate,
) -> UserNotificationSettings:
    """
    Update notification settings for a user.

    Performs a partial update - only provided fields are modified.
    If settings don't exist, creates them with defaults first.

    Args:
        db: Database session
        user_id: User ID
        workspace_id: Workspace ID (for workspace scoping)
        updates: Update schema with fields to modify

    Returns:
        Updated UserNotificationSettings instance

    Raises:
        ValueError: If validation fails (invalid time format or reminder minutes)

    Example:
        ```python
        updates = NotificationSettingsUpdate(
            email_enabled=True,
            digest_enabled=True,
            digest_time="08:00",
        )
        settings = await update_notification_settings(
            db, user_id, workspace_id, updates
        )
        await db.commit()
        ```
    """
    # Get existing settings or create defaults
    settings = await get_notification_settings(db, user_id, workspace_id)

    if settings is None:
        logger.info(
            "notification_settings_not_found_creating_defaults",
            user_id=str(user_id),
            workspace_id=str(workspace_id),
        )
        settings = await create_default_settings(db, user_id, workspace_id)

    # Apply partial updates
    update_data = updates.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(settings, field, value)

    # Validate settings
    validation_errors = settings.validate()
    if validation_errors:
        error_msg = "; ".join(validation_errors)
        logger.warning(
            "notification_settings_validation_failed",
            user_id=str(user_id),
            workspace_id=str(workspace_id),
            errors=validation_errors,
        )
        raise ValueError(f"Validation failed: {error_msg}")

    await db.flush()
    await db.refresh(settings)

    logger.info(
        "notification_settings_updated",
        user_id=str(user_id),
        workspace_id=str(workspace_id),
        updated_fields=list(update_data.keys()),
    )

    return settings


async def get_or_create_notification_settings(
    db: AsyncSession,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> UserNotificationSettings:
    """
    Get notification settings for a user, creating defaults if they don't exist.

    This is a convenience function that combines get and create operations.
    Useful for endpoints that should always return settings.

    Args:
        db: Database session
        user_id: User ID
        workspace_id: Workspace ID

    Returns:
        UserNotificationSettings instance (existing or newly created)

    Example:
        ```python
        # Always returns settings, creating defaults if needed
        settings = await get_or_create_notification_settings(
            db, user_id, workspace_id
        )
        ```
    """
    settings = await get_notification_settings(db, user_id, workspace_id)

    if settings is None:
        logger.info(
            "notification_settings_auto_creating",
            user_id=str(user_id),
            workspace_id=str(workspace_id),
        )
        settings = await create_default_settings(db, user_id, workspace_id)
        await db.commit()

    return settings
