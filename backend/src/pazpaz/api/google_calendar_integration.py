"""Google Calendar integration API endpoints."""

from __future__ import annotations

import secrets
import uuid

import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.api.deps import get_current_user, get_db
from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger
from pazpaz.core.redis import get_redis
from pazpaz.models.google_calendar_token import GoogleCalendarToken
from pazpaz.models.user import User
from pazpaz.schemas.google_calendar_integration import (
    GoogleCalendarAuthorizeResponse,
    GoogleCalendarSettingsResponse,
    GoogleCalendarSettingsUpdate,
    GoogleCalendarStatusResponse,
)
from pazpaz.services.google_calendar_oauth_service import (
    exchange_code_for_tokens,
    get_authorization_url,
)

router = APIRouter(prefix="/integrations/google-calendar", tags=["google-calendar"])
logger = get_logger(__name__)

# Redis key prefix for OAuth state tokens
OAUTH_STATE_KEY_PREFIX = "gcal_oauth_state:"
OAUTH_STATE_EXPIRY = 600  # 10 minutes


@router.get("/status", response_model=GoogleCalendarStatusResponse)
async def get_integration_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoogleCalendarStatusResponse:
    """
    Get Google Calendar integration status for the current user.

    Returns whether the user has connected their Google Calendar account,
    when the last sync occurred, and whether sync is currently enabled.

    SECURITY: Only returns status for the authenticated user's workspace
    (from JWT token). Workspace scoping prevents cross-workspace data access.

    Args:
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Integration status with connection state and sync information

    Raises:
        HTTPException: 401 if not authenticated

    Example Response:
        {
            "connected": true,
            "last_sync_at": "2025-10-28T14:30:00Z",
            "enabled": true
        }
    """
    workspace_id = current_user.workspace_id
    user_id = current_user.id

    logger.debug(
        "google_calendar_status_check",
        user_id=str(user_id),
        workspace_id=str(workspace_id),
    )

    # Query for existing token
    query = select(GoogleCalendarToken).where(
        GoogleCalendarToken.workspace_id == workspace_id,
        GoogleCalendarToken.user_id == user_id,
    )
    result = await db.execute(query)
    token = result.scalar_one_or_none()

    if not token:
        # No integration configured
        logger.info(
            "google_calendar_not_connected",
            user_id=str(user_id),
            workspace_id=str(workspace_id),
        )
        return GoogleCalendarStatusResponse(
            connected=False,
            enabled=False,
            sync_client_names=False,
            notify_clients=False,
            has_google_baa=False,
            last_sync_at=None,
        )

    # Integration exists
    logger.info(
        "google_calendar_connected",
        user_id=str(user_id),
        workspace_id=str(workspace_id),
        enabled=token.enabled,
        sync_client_names=token.sync_client_names,
        token_id=str(token.id),
    )

    # TODO: Implement last_sync_at tracking (Phase 2)
    # For now, return None since we haven't implemented sync yet
    return GoogleCalendarStatusResponse(
        connected=True,
        enabled=token.enabled,
        sync_client_names=token.sync_client_names,
        notify_clients=token.notify_clients,
        has_google_baa=token.has_google_baa,
        last_sync_at=None,  # Will be populated in Phase 2 (calendar sync)
    )


@router.post("/authorize", response_model=GoogleCalendarAuthorizeResponse)
async def authorize_google_calendar(
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
) -> GoogleCalendarAuthorizeResponse:
    """
    Generate Google Calendar OAuth authorization URL.

    Creates a cryptographically secure state token for CSRF protection,
    stores it in Redis with short expiration, and generates the OAuth URL
    that the frontend should redirect the user to for authorization.

    SECURITY:
    - State token: 32 bytes of cryptographically secure random data
    - Redis storage: 10-minute expiration prevents replay attacks
    - Workspace scoping: State maps to workspace_id to prevent token stealing

    Flow:
    1. Generate CSRF state token (secrets.token_urlsafe)
    2. Store state → workspace_id mapping in Redis (10min TTL)
    3. Generate OAuth URL with state parameter
    4. Return URL to frontend
    5. Frontend redirects user to URL
    6. Google redirects back to callback with state + code
    7. Callback validates state and exchanges code for tokens

    Args:
        current_user: Authenticated user (from JWT token)
        redis_client: Redis client for state storage

    Returns:
        Authorization URL for user to visit

    Raises:
        HTTPException: 401 if not authenticated, 500 if Redis fails

    Example Response:
        {
            "authorization_url": "https://accounts.google.com/o/oauth2/auth?..."
        }
    """
    workspace_id = current_user.workspace_id
    user_id = current_user.id

    logger.info(
        "google_calendar_authorize_started",
        user_id=str(user_id),
        workspace_id=str(workspace_id),
    )

    # Generate cryptographically secure CSRF state token
    # 32 bytes = 256 bits of entropy (base64url encoded)
    state = secrets.token_urlsafe(32)

    # Store state → workspace_id mapping in Redis
    # This allows us to validate state in callback and get workspace context
    redis_key = f"{OAUTH_STATE_KEY_PREFIX}{state}"
    try:
        # Store workspace_id as string (Redis stores strings)
        # TTL of 10 minutes - user must complete OAuth flow within this time
        await redis_client.setex(
            redis_key,
            OAUTH_STATE_EXPIRY,
            str(workspace_id),
        )
        logger.debug(
            "oauth_state_stored",
            state_preview=state[:8] + "...",
            workspace_id=str(workspace_id),
            ttl_seconds=OAUTH_STATE_EXPIRY,
        )
    except Exception as e:
        logger.error(
            "oauth_state_storage_failed",
            user_id=str(user_id),
            workspace_id=str(workspace_id),
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to initialize OAuth flow. Please try again.",
        ) from e

    # Generate OAuth authorization URL
    authorization_url = get_authorization_url(state, workspace_id)

    logger.info(
        "google_calendar_authorization_url_generated",
        user_id=str(user_id),
        workspace_id=str(workspace_id),
        state_preview=state[:8] + "...",
    )

    return GoogleCalendarAuthorizeResponse(authorization_url=authorization_url)


@router.get("/callback")
async def oauth_callback(
    code: str | None = Query(None, description="OAuth authorization code from Google"),
    state: str | None = Query(None, description="CSRF state token"),
    error: str | None = Query(None, description="OAuth error from Google"),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> RedirectResponse:
    """
    Handle OAuth callback from Google.

    After user authorizes access on Google's consent screen, Google redirects
    back to this endpoint with an authorization code and the state token.
    This endpoint validates the state (CSRF protection), exchanges the code
    for tokens, and redirects the user back to the frontend.

    SECURITY:
    - State validation: Prevents CSRF attacks on OAuth flow
    - Workspace scoping: State maps to workspace_id for proper scoping
    - NO authentication required: This is the OAuth callback URL
    - Redirect validation: Only redirects to configured frontend URL

    Flow:
    1. Validate state token exists in Redis
    2. Retrieve workspace_id from state
    3. Exchange authorization code for access/refresh tokens
    4. Store tokens in database (encrypted)
    5. Delete state from Redis (one-time use)
    6. Redirect to frontend settings page with success/error flag

    Args:
        code: OAuth authorization code from Google
        state: CSRF state token (must match stored value)
        db: Database session for token storage
        redis_client: Redis client for state validation

    Returns:
        RedirectResponse to frontend settings page

    Redirects:
        - Success: {FRONTEND_URL}/settings?gcal=success
        - Error: {FRONTEND_URL}/settings?gcal=error

    Note:
        This endpoint does NOT require authentication because it's the OAuth
        callback URL. Authentication is implicitly validated via the state token
        which maps to a workspace_id from an authenticated session.
    """
    # Handle OAuth error from Google (user denied access, etc.)
    if error:
        logger.warning(
            "google_calendar_oauth_error",
            error=error,
            state_preview=state[:8] + "..." if state else "missing",
        )
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?gcal=error",
            status_code=302,
        )

    # Validate required parameters
    if not code or not state:
        logger.error(
            "google_calendar_callback_missing_parameters",
            has_code=bool(code),
            has_state=bool(state),
        )
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?gcal=error",
            status_code=302,
        )

    logger.info(
        "google_calendar_callback_received",
        state_preview=state[:8] + "...",
        has_code=bool(code),
    )

    # Validate state token and retrieve workspace_id
    redis_key = f"{OAUTH_STATE_KEY_PREFIX}{state}"
    try:
        workspace_id_str = await redis_client.get(redis_key)
        if not workspace_id_str:
            logger.warning(
                "oauth_callback_invalid_state",
                state_preview=state[:8] + "...",
                reason="state_not_found_or_expired",
            )
            return RedirectResponse(
                url=f"{settings.frontend_url}/settings?gcal=error",
                status_code=status.HTTP_302_FOUND,
            )

        workspace_id = uuid.UUID(workspace_id_str)
        logger.debug(
            "oauth_state_validated",
            state_preview=state[:8] + "...",
            workspace_id=str(workspace_id),
        )

    except (ValueError, TypeError) as e:
        # Invalid UUID format in Redis (shouldn't happen, but defensive)
        logger.error(
            "oauth_callback_invalid_workspace_id",
            state_preview=state[:8] + "...",
            error=str(e),
            exc_info=True,
        )
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?gcal=error",
            status_code=status.HTTP_302_FOUND,
        )
    except Exception as e:
        # Redis error or other issues
        logger.error(
            "oauth_state_validation_failed",
            state_preview=state[:8] + "...",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?gcal=error",
            status_code=status.HTTP_302_FOUND,
        )

    # Get user_id from workspace (we need user_id for token storage)
    # For now, we'll use the workspace owner's user_id
    # TODO: In a multi-user workspace, track which user initiated OAuth flow
    try:
        from sqlalchemy.orm import selectinload

        from pazpaz.models.workspace import Workspace

        query = (
            select(Workspace)
            .where(Workspace.id == workspace_id)
            .options(selectinload(Workspace.users))
        )
        result = await db.execute(query)
        workspace = result.scalar_one_or_none()

        if not workspace or not workspace.users:
            logger.error(
                "oauth_callback_workspace_not_found",
                workspace_id=str(workspace_id),
            )
            return RedirectResponse(
                url=f"{settings.frontend_url}/settings?gcal=error",
                status_code=status.HTTP_302_FOUND,
            )

        # Use the first user in workspace (typically the owner)
        # TODO: Track user_id in state for multi-user support
        user_id = workspace.users[0].id
        logger.debug(
            "oauth_callback_user_identified",
            user_id=str(user_id),
            workspace_id=str(workspace_id),
        )

    except Exception as e:
        logger.error(
            "oauth_callback_user_lookup_failed",
            workspace_id=str(workspace_id),
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?gcal=error",
            status_code=status.HTTP_302_FOUND,
        )

    # Exchange authorization code for tokens
    try:
        token = await exchange_code_for_tokens(
            code=code,
            db=db,
            user_id=user_id,
            workspace_id=workspace_id,
        )
        logger.info(
            "google_calendar_oauth_success",
            token_id=str(token.id),
            user_id=str(user_id),
            workspace_id=str(workspace_id),
        )

    except HTTPException as e:
        # exchange_code_for_tokens already logged the error
        logger.warning(
            "oauth_code_exchange_failed_redirecting",
            workspace_id=str(workspace_id),
            status_code=e.status_code,
        )
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?gcal=error",
            status_code=status.HTTP_302_FOUND,
        )
    except Exception as e:
        logger.error(
            "oauth_callback_unexpected_error",
            workspace_id=str(workspace_id),
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        return RedirectResponse(
            url=f"{settings.frontend_url}/settings?gcal=error",
            status_code=status.HTTP_302_FOUND,
        )

    # Delete state from Redis (one-time use token)
    try:
        await redis_client.delete(redis_key)
        logger.debug(
            "oauth_state_deleted",
            state_preview=state[:8] + "...",
        )
    except Exception as e:
        # Log error but don't fail the flow - state will expire anyway
        logger.warning(
            "oauth_state_deletion_failed",
            state_preview=state[:8] + "...",
            error=str(e),
        )

    # Redirect to frontend settings page with success flag
    return RedirectResponse(
        url=f"{settings.frontend_url}/settings?gcal=success",
        status_code=status.HTTP_302_FOUND,
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_google_calendar(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Disconnect Google Calendar integration.

    Permanently deletes the OAuth tokens for the current user, effectively
    disconnecting their Google Calendar account from PazPaz. This action
    cannot be undone - user must re-authorize to reconnect.

    SECURITY:
    - Workspace scoping: Only deletes tokens for authenticated user's workspace
    - Idempotent: Returns 204 even if no integration exists (prevents info leakage)

    Token Revocation:
    - Deletes tokens from PazPaz database
    - Does NOT revoke tokens with Google (user can do this in Google Account)
    - Deleted tokens are encrypted at rest, so secure even if backups exist

    Args:
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        No content (204) on success

    Raises:
        HTTPException: 401 if not authenticated

    Example:
        DELETE /api/v1/integrations/google-calendar
        Response: 204 No Content
    """
    workspace_id = current_user.workspace_id
    user_id = current_user.id

    logger.info(
        "google_calendar_disconnect_started",
        user_id=str(user_id),
        workspace_id=str(workspace_id),
    )

    # Query for existing token
    query = select(GoogleCalendarToken).where(
        GoogleCalendarToken.workspace_id == workspace_id,
        GoogleCalendarToken.user_id == user_id,
    )
    result = await db.execute(query)
    token = result.scalar_one_or_none()

    if not token:
        # No integration exists - return 204 anyway (idempotent)
        logger.info(
            "google_calendar_disconnect_no_integration",
            user_id=str(user_id),
            workspace_id=str(workspace_id),
        )
        return

    # Delete token
    await db.delete(token)
    await db.commit()

    logger.info(
        "google_calendar_disconnected",
        token_id=str(token.id),
        user_id=str(user_id),
        workspace_id=str(workspace_id),
    )


@router.patch("/settings", response_model=GoogleCalendarSettingsResponse)
async def update_settings(
    settings: GoogleCalendarSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GoogleCalendarSettingsResponse:
    """
    Update Google Calendar sync settings.

    Allows users to enable/disable sync and control whether client names
    are included in calendar event titles.

    SECURITY:
    - Workspace scoping: Only updates settings for authenticated user's workspace
    - Partial updates: Only provided fields are updated (PATCH semantics)

    Args:
        settings: Settings to update (partial updates supported)
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Updated settings with sync status

    Raises:
        HTTPException: 404 if Google Calendar not connected

    Example Request:
        PATCH /api/v1/integrations/google-calendar/settings
        {
            "sync_client_names": true
        }

    Example Response:
        {
            "enabled": true,
            "sync_client_names": true,
            "last_sync_at": "2025-10-28T14:30:00Z",
            "last_sync_status": "success",
            "last_sync_error": null
        }
    """
    workspace_id = current_user.workspace_id
    user_id = current_user.id

    logger.info(
        "google_calendar_settings_update_requested",
        user_id=str(user_id),
        workspace_id=str(workspace_id),
        settings=settings.model_dump(exclude_none=True),
    )

    # Fetch token with workspace scoping
    query = select(GoogleCalendarToken).where(
        GoogleCalendarToken.workspace_id == workspace_id,
        GoogleCalendarToken.user_id == user_id,
    )
    result = await db.execute(query)
    token = result.scalar_one_or_none()

    if not token:
        logger.warning(
            "google_calendar_settings_update_failed_not_connected",
            user_id=str(user_id),
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Google Calendar not connected. Please connect first.",
        )

    # Update fields (partial update support)
    updated_fields = []
    if settings.enabled is not None:
        token.enabled = settings.enabled
        updated_fields.append(f"enabled={settings.enabled}")

    if settings.sync_client_names is not None:
        token.sync_client_names = settings.sync_client_names
        updated_fields.append(f"sync_client_names={settings.sync_client_names}")

    if settings.has_google_baa is not None:
        token.has_google_baa = settings.has_google_baa
        updated_fields.append(f"has_google_baa={settings.has_google_baa}")

    if settings.notify_clients is not None:
        # SECURITY: Validate BAA requirement before enabling client notifications
        if settings.notify_clients and not token.has_google_baa:
            logger.warning(
                "google_calendar_notify_clients_blocked_no_baa",
                user_id=str(user_id),
                workspace_id=str(workspace_id),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google Workspace Business Associate Agreement (BAA) required to send notifications to clients. "
                       "Please confirm you have signed a BAA with Google before enabling client notifications.",
            )
        token.notify_clients = settings.notify_clients
        updated_fields.append(f"notify_clients={settings.notify_clients}")

    # Commit changes
    await db.commit()
    await db.refresh(token)

    logger.info(
        "google_calendar_settings_updated",
        user_id=str(user_id),
        workspace_id=str(workspace_id),
        updated_fields=updated_fields,
    )

    # Return updated settings
    return GoogleCalendarSettingsResponse(
        enabled=token.enabled,
        sync_client_names=token.sync_client_names,
        notify_clients=token.notify_clients,
        has_google_baa=token.has_google_baa,
        last_sync_at=token.last_sync_at,
        last_sync_status=token.last_sync_status,
        last_sync_error=token.last_sync_error,
    )
