"""Google Calendar OAuth 2.0 service for authentication and token management."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import google.auth.exceptions
import google.auth.transport.requests
import google.oauth2.credentials
from fastapi import HTTPException
from google_auth_oauthlib.flow import Flow
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger
from pazpaz.models.google_calendar_token import GoogleCalendarToken

logger = get_logger(__name__)

# Google Calendar API scopes
GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]

# SSL Configuration:
# SSL certificate verification is configured via environment variables in Dockerfile:
# - REQUESTS_CA_BUNDLE: Points to certifi CA bundle for requests library
# - SSL_CERT_FILE: Points to certifi CA bundle for other SSL libraries
#
# This is the standard, recommended approach for Python applications in Docker:
# https://requests.readthedocs.io/en/latest/user/advanced/#ssl-cert-verification


def get_authorization_url(state: str, workspace_id: uuid.UUID) -> str:
    """
    Generate OAuth 2.0 authorization URL for Google Calendar access.

    Creates a Google OAuth flow with configured client credentials and generates
    the authorization URL that users should visit to grant calendar access.
    The URL includes CSRF protection via the state parameter.

    Security:
    - State parameter prevents CSRF attacks on OAuth callback
    - Offline access requests refresh token for long-lived access
    - Prompt=consent forces consent screen (ensures refresh token is issued)

    Args:
        state: CSRF protection token (cryptographically random, stored in Redis)
        workspace_id: Workspace ID for workspace scoping (used for logging)

    Returns:
        Google OAuth authorization URL with all required parameters

    Raises:
        HTTPException: 500 if OAuth client configuration is invalid

    Example:
        >>> state = secrets.token_urlsafe(32)
        >>> url = get_authorization_url(state, workspace_id)
        >>> # Redirect user to url for authorization
    """
    try:
        # Build OAuth client config from environment variables
        # Using client_config dict instead of client_secrets.json for security
        # (avoids storing credentials in files)
        client_config = {
            "web": {
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "redirect_uris": [settings.google_oauth_redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }

        # Create OAuth flow
        # redirect_uri must match exactly what's registered in Google Console
        # SSL verification is automatically configured via module-level monkey-patch
        flow = Flow.from_client_config(
            client_config=client_config,
            scopes=GOOGLE_CALENDAR_SCOPES,
            redirect_uri=settings.google_oauth_redirect_uri,
        )

        # Generate authorization URL
        # access_type=offline: Request refresh token for long-lived access
        # prompt=consent: Force consent screen (ensures refresh token is issued)
        # include_granted_scopes=true: Incremental authorization support
        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            prompt="consent",
            state=state,
            include_granted_scopes="true",
        )

        logger.info(
            "oauth_authorization_url_generated",
            workspace_id=str(workspace_id),
            scopes=GOOGLE_CALENDAR_SCOPES,
            has_state=bool(state),
        )

        return authorization_url

    except Exception as e:
        logger.error(
            "oauth_authorization_url_generation_failed",
            workspace_id=str(workspace_id),
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to generate authorization URL. Please check OAuth client configuration.",
        ) from e


async def exchange_code_for_tokens(
    code: str,
    db: AsyncSession,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> GoogleCalendarToken:
    """
    Exchange OAuth authorization code for access and refresh tokens.

    After user authorizes access, Google redirects back with an authorization code.
    This function exchanges that code for access/refresh tokens and stores them
    securely in the database with automatic encryption.

    Token Storage:
    - access_token: Short-lived (1 hour) - encrypted at rest
    - refresh_token: Long-lived (until revoked) - encrypted at rest
    - token_expiry: Calculated from expires_in (typically 3600 seconds)
    - Encryption is automatic via EncryptedString SQLAlchemy type

    Database Behavior:
    - If user already has a token, UPDATE existing record (upsert behavior)
    - Otherwise, INSERT new token record
    - Unique constraint: (workspace_id, user_id)

    Args:
        code: OAuth authorization code from callback URL
        db: Database session for token storage
        user_id: User who is authorizing access
        workspace_id: Workspace for scoping

    Returns:
        Created or updated GoogleCalendarToken instance

    Raises:
        HTTPException: 400 if code is invalid/expired, 500 for other errors

    Example:
        >>> token = await exchange_code_for_tokens(
        ...     code="4/0AY0e-g7...",
        ...     db=db,
        ...     user_id=user.id,
        ...     workspace_id=user.workspace_id,
        ... )
        >>> print(f"Token expires at: {token.token_expiry}")
    """
    try:
        # Build OAuth client config (same as authorization)
        client_config = {
            "web": {
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "redirect_uris": [settings.google_oauth_redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }

        # Create OAuth flow (same redirect_uri as authorization)
        # SSL verification is automatically configured via module-level monkey-patch
        flow = Flow.from_client_config(
            client_config=client_config,
            scopes=GOOGLE_CALENDAR_SCOPES,
            redirect_uri=settings.google_oauth_redirect_uri,
        )

        # Exchange authorization code for tokens
        # This makes a POST request to Google's token endpoint with SSL verification
        # SSL certificate verification uses certifi CA bundle (configured at module level)
        flow.fetch_token(code=code)

        # Extract credentials
        credentials = flow.credentials

        # Calculate token expiry (credentials.expiry is already in UTC)
        token_expiry = credentials.expiry or datetime.now(UTC)

        logger.info(
            "oauth_tokens_exchanged",
            user_id=str(user_id),
            workspace_id=str(workspace_id),
            token_expiry=token_expiry.isoformat(),
            scopes=credentials.scopes,
        )

        # Check if token already exists (upsert behavior)
        query = select(GoogleCalendarToken).where(
            GoogleCalendarToken.workspace_id == workspace_id,
            GoogleCalendarToken.user_id == user_id,
        )
        result = await db.execute(query)
        existing_token = result.scalar_one_or_none()

        if existing_token:
            # Update existing token
            existing_token.access_token = credentials.token
            existing_token.refresh_token = credentials.refresh_token
            existing_token.token_expiry = token_expiry
            existing_token.scopes = credentials.scopes or GOOGLE_CALENDAR_SCOPES
            existing_token.enabled = True  # Re-enable if previously disabled
            token = existing_token

            logger.info(
                "oauth_token_updated",
                token_id=str(token.id),
                user_id=str(user_id),
                workspace_id=str(workspace_id),
            )
        else:
            # Create new token
            token = GoogleCalendarToken(
                workspace_id=workspace_id,
                user_id=user_id,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_expiry=token_expiry,
                scopes=credentials.scopes or GOOGLE_CALENDAR_SCOPES,
                enabled=True,
            )
            db.add(token)

            logger.info(
                "oauth_token_created",
                user_id=str(user_id),
                workspace_id=str(workspace_id),
            )

        await db.commit()
        await db.refresh(token)

        return token

    except google.auth.exceptions.RefreshError as e:
        # Invalid authorization code or code already used
        logger.warning(
            "oauth_code_exchange_failed_invalid_code",
            user_id=str(user_id),
            workspace_id=str(workspace_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired authorization code. Please try again.",
        ) from e
    except Exception as e:
        # Network error, invalid client config, or other issues
        logger.error(
            "oauth_code_exchange_failed",
            user_id=str(user_id),
            workspace_id=str(workspace_id),
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to exchange authorization code for tokens. Please try again.",
        ) from e


async def refresh_access_token(
    token: GoogleCalendarToken, db: AsyncSession
) -> GoogleCalendarToken:
    """
    Refresh an expired access token using the refresh token.

    Access tokens expire after ~1 hour. This function uses the long-lived refresh
    token to obtain a new access token without requiring user interaction.

    Token Refresh Behavior:
    - Google returns a new access_token
    - Refresh token typically remains the same (not rotated)
    - Token expiry is updated to current time + 3600 seconds
    - All tokens are encrypted at rest via EncryptedString

    Args:
        token: Existing GoogleCalendarToken with valid refresh_token
        db: Database session for updating token

    Returns:
        Updated GoogleCalendarToken with new access token

    Raises:
        HTTPException: 401 if refresh token is invalid/revoked, 500 for other errors

    Example:
        >>> if token.is_expired:
        ...     token = await refresh_access_token(token, db)
        >>> # Use token.access_token for API calls
    """
    try:
        # Create credentials from stored tokens
        # Decryption is automatic via EncryptedString type
        credentials = google.oauth2.credentials.Credentials(
            token=token.access_token,
            refresh_token=token.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_oauth_client_id,
            client_secret=settings.google_oauth_client_secret,
            scopes=token.scopes,
        )

        # Refresh the access token
        # This makes a POST request to Google's token endpoint with refresh_token
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)

        # Update token in database
        token.access_token = credentials.token
        # Note: refresh_token may be rotated by Google (though typically isn't)
        if credentials.refresh_token:
            token.refresh_token = credentials.refresh_token
        token.token_expiry = credentials.expiry or datetime.now(UTC)

        await db.commit()
        await db.refresh(token)

        logger.info(
            "oauth_token_refreshed",
            token_id=str(token.id),
            user_id=str(token.user_id),
            workspace_id=str(token.workspace_id),
            new_expiry=token.token_expiry.isoformat(),
        )

        return token

    except google.auth.exceptions.RefreshError as e:
        # Refresh token is invalid, expired, or revoked
        # User must re-authorize
        logger.warning(
            "oauth_token_refresh_failed_invalid_refresh_token",
            token_id=str(token.id),
            user_id=str(token.user_id),
            workspace_id=str(token.workspace_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=401,
            detail=(
                "Refresh token is invalid or has been revoked. "
                "Please reconnect your Google Calendar account."
            ),
        ) from e
    except Exception as e:
        # Network error or other issues
        logger.error(
            "oauth_token_refresh_failed",
            token_id=str(token.id),
            user_id=str(token.user_id),
            workspace_id=str(token.workspace_id),
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to refresh access token. Please try again.",
        ) from e


def get_credentials(
    token: GoogleCalendarToken,
) -> google.oauth2.credentials.Credentials:
    """
    Create Google API credentials object from stored token.

    Helper function to convert our database GoogleCalendarToken model into a
    google.oauth2.credentials.Credentials object that can be used with Google
    Calendar API client libraries.

    Token Decryption:
    - Automatic via EncryptedString SQLAlchemy type
    - No explicit decryption needed in this function

    Args:
        token: GoogleCalendarToken from database

    Returns:
        Google OAuth 2.0 Credentials object ready for API calls

    Example:
        >>> credentials = get_credentials(token)
        >>> from googleapiclient.discovery import build
        >>> service = build('calendar', 'v3', credentials=credentials)
        >>> calendars = service.calendarList().list().execute()
    """
    # Tokens are automatically decrypted when accessed via EncryptedString
    credentials = google.oauth2.credentials.Credentials(
        token=token.access_token,
        refresh_token=token.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
        scopes=token.scopes,
    )

    return credentials
