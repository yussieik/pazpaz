"""Integration tests for Google Calendar OAuth API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.google_calendar_token import GoogleCalendarToken
from pazpaz.models.user import User
from pazpaz.models.workspace import Workspace


@pytest.mark.asyncio
async def test_get_status_not_connected(
    authenticated_client: AsyncClient,
    test_user: User,
    db_session: AsyncSession,
):
    """Test GET /status returns connected=False when no integration exists."""
    # Make request
    response = await authenticated_client.get(
        "/api/v1/integrations/google-calendar/status"
    )

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is False
    assert data["last_sync_at"] is None
    assert data["enabled"] is False


@pytest.mark.asyncio
async def test_get_status_connected(
    authenticated_client: AsyncClient,
    test_user: User,
    db_session: AsyncSession,
):
    """Test GET /status returns connected=True when integration exists."""
    # Create a GoogleCalendarToken for the test user
    token = GoogleCalendarToken(
        workspace_id=test_user.workspace_id,
        user_id=test_user.id,
        access_token="ya29.a0test_access_token",
        refresh_token="1//0gtest_refresh_token",
        token_expiry=datetime.now(UTC) + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/calendar"],
        enabled=True,
    )
    db_session.add(token)
    await db_session.commit()

    # Make request
    response = await authenticated_client.get(
        "/api/v1/integrations/google-calendar/status"
    )

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True
    # last_sync_at is None in Phase 1 (sync not implemented yet)
    assert data["last_sync_at"] is None
    assert data["enabled"] is True


@pytest.mark.asyncio
async def test_authorize_generates_url(
    authenticated_client: AsyncClient,
    test_user: User,
    redis_client,
):
    """Test POST /authorize generates valid OAuth URL with state."""
    # Make request
    response = await authenticated_client.post(
        "/api/v1/integrations/google-calendar/authorize"
    )

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "authorization_url" in data
    url = data["authorization_url"]

    # Verify URL structure
    assert url.startswith("https://accounts.google.com/o/oauth2/auth")
    assert "client_id=" in url
    assert "redirect_uri=" in url
    assert "scope=" in url
    assert "state=" in url
    assert "access_type=offline" in url
    assert "prompt=consent" in url

    # Extract state from URL
    state = None
    for param in url.split("&"):
        if param.startswith("state="):
            state = param.split("=")[1]
            break

    assert state is not None

    # Verify state is stored in Redis
    redis_key = f"gcal_oauth_state:{state}"
    stored_workspace_id = await redis_client.get(redis_key)
    assert stored_workspace_id == str(test_user.workspace_id)

    # Verify TTL is set (should be ~600 seconds)
    ttl = await redis_client.ttl(redis_key)
    assert 590 <= ttl <= 600


@pytest.mark.asyncio
@patch("pazpaz.services.google_calendar_oauth_service.Flow")
async def test_callback_success(
    mock_flow_class,
    authenticated_client: AsyncClient,
    test_user: User,
    test_workspace: Workspace,
    db_session: AsyncSession,
    redis_client,
):
    """Test GET /callback successfully exchanges code and stores tokens."""
    # Setup: Store state in Redis
    state = "test_state_token_12345"
    redis_key = f"gcal_oauth_state:{state}"
    await redis_client.setex(redis_key, 600, str(test_workspace.id))

    # Mock OAuth flow
    mock_flow = MagicMock()
    mock_credentials = MagicMock()
    mock_credentials.token = "ya29.a0test_new_access_token"
    mock_credentials.refresh_token = "1//0gtest_new_refresh_token"
    mock_credentials.expiry = datetime.now(UTC) + timedelta(hours=1)
    mock_credentials.scopes = ["https://www.googleapis.com/auth/calendar"]
    mock_flow.credentials = mock_credentials
    mock_flow_class.from_client_config.return_value = mock_flow

    # Make request (no auth cookie needed - this is OAuth callback)
    response = await authenticated_client.get(
        f"/api/v1/integrations/google-calendar/callback?code=test_auth_code&state={state}",
        follow_redirects=False,
    )

    # Verify redirect response
    assert response.status_code == 302
    assert response.headers["location"].endswith("/settings?gcal=success")

    # Verify token was stored in database
    query = select(GoogleCalendarToken).where(
        GoogleCalendarToken.workspace_id == test_workspace.id,
        GoogleCalendarToken.user_id == test_user.id,
    )
    result = await db_session.execute(query)
    token = result.scalar_one_or_none()

    assert token is not None
    assert token.access_token == "ya29.a0test_new_access_token"
    assert token.refresh_token == "1//0gtest_new_refresh_token"
    assert token.enabled is True
    assert token.scopes == ["https://www.googleapis.com/auth/calendar"]

    # Verify state was deleted from Redis
    stored_state = await redis_client.get(redis_key)
    assert stored_state is None

    # Verify OAuth flow was called correctly
    mock_flow.fetch_token.assert_called_once_with(code="test_auth_code")


@pytest.mark.asyncio
async def test_callback_invalid_state(
    authenticated_client: AsyncClient,
    redis_client,
):
    """Test GET /callback returns error for invalid state."""
    # Make request with invalid state (not in Redis)
    response = await authenticated_client.get(
        "/api/v1/integrations/google-calendar/callback?code=test_code&state=invalid_state",
        follow_redirects=False,
    )

    # Verify redirect to error page
    assert response.status_code == 302
    assert response.headers["location"].endswith("/settings?gcal=error")


@pytest.mark.asyncio
@patch("pazpaz.services.google_calendar_oauth_service.Flow")
async def test_callback_invalid_code(
    mock_flow_class,
    authenticated_client: AsyncClient,
    test_workspace: Workspace,
    redis_client,
):
    """Test GET /callback returns error for invalid authorization code."""
    # Setup: Store state in Redis
    state = "test_state_token_67890"
    redis_key = f"gcal_oauth_state:{state}"
    await redis_client.setex(redis_key, 600, str(test_workspace.id))

    # Mock OAuth flow to raise RefreshError (invalid code)
    mock_flow = MagicMock()
    mock_flow.fetch_token.side_effect = Exception("invalid_grant")
    mock_flow_class.from_client_config.return_value = mock_flow

    # Make request
    response = await authenticated_client.get(
        f"/api/v1/integrations/google-calendar/callback?code=invalid_code&state={state}",
        follow_redirects=False,
    )

    # Verify redirect to error page
    assert response.status_code == 302
    assert response.headers["location"].endswith("/settings?gcal=error")


@pytest.mark.asyncio
async def test_disconnect(
    authenticated_client: AsyncClient,
    test_user: User,
    db_session: AsyncSession,
):
    """Test DELETE / successfully deletes integration."""
    # Setup: Create a token
    token = GoogleCalendarToken(
        workspace_id=test_user.workspace_id,
        user_id=test_user.id,
        access_token="ya29.a0test_access_token",
        refresh_token="1//0gtest_refresh_token",
        token_expiry=datetime.now(UTC) + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/calendar"],
        enabled=True,
    )
    db_session.add(token)
    await db_session.commit()
    token_id = token.id

    # Make request
    response = await authenticated_client.delete("/api/v1/integrations/google-calendar")

    # Verify response
    assert response.status_code == 204

    # Verify token was deleted from database
    query = select(GoogleCalendarToken).where(GoogleCalendarToken.id == token_id)
    result = await db_session.execute(query)
    deleted_token = result.scalar_one_or_none()
    assert deleted_token is None


@pytest.mark.asyncio
async def test_disconnect_no_integration(
    authenticated_client: AsyncClient,
    test_user: User,
):
    """Test DELETE / returns 204 even when no integration exists (idempotent)."""
    # Make request (no token exists)
    response = await authenticated_client.delete("/api/v1/integrations/google-calendar")

    # Verify response (idempotent - returns 204 even if nothing to delete)
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_workspace_isolation(
    authenticated_client: AsyncClient,
    test_user: User,
    test_user2: User,
    db_session: AsyncSession,
):
    """Test user from workspace A cannot access workspace B's integration."""
    # Setup: Create token for workspace 2 (different workspace)
    token_ws2 = GoogleCalendarToken(
        workspace_id=test_user2.workspace_id,
        user_id=test_user2.id,
        access_token="ya29.a0workspace2_token",
        refresh_token="1//0gworkspace2_refresh",
        token_expiry=datetime.now(UTC) + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/calendar"],
        enabled=True,
    )
    db_session.add(token_ws2)
    await db_session.commit()

    # User 1 (workspace 1) checks status - should NOT see workspace 2's integration
    response = await authenticated_client.get(
        "/api/v1/integrations/google-calendar/status"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is False  # User 1 has no integration in workspace 1

    # Verify workspace 2 token still exists (not affected)
    query = select(GoogleCalendarToken).where(
        GoogleCalendarToken.workspace_id == test_user2.workspace_id
    )
    result = await db_session.execute(query)
    ws2_token = result.scalar_one_or_none()
    assert ws2_token is not None


@pytest.mark.asyncio
async def test_get_status_unauthenticated(client: AsyncClient):
    """Test GET /status returns 401 when not authenticated."""
    response = await client.get("/api/v1/integrations/google-calendar/status")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_authorize_unauthenticated(client: AsyncClient):
    """Test POST /authorize returns 403 when CSRF token missing (runs before auth)."""
    response = await client.post("/api/v1/integrations/google-calendar/authorize")
    # CSRF middleware runs before auth, so we get 403 instead of 401
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_disconnect_unauthenticated(client: AsyncClient):
    """Test DELETE / returns 403 when CSRF token missing (runs before auth)."""
    response = await client.delete("/api/v1/integrations/google-calendar")
    # CSRF middleware runs before auth, so we get 403 instead of 401
    assert response.status_code == 403


@pytest.mark.asyncio
@patch("pazpaz.services.google_calendar_oauth_service.Flow")
async def test_callback_updates_existing_token(
    mock_flow_class,
    authenticated_client: AsyncClient,
    test_user: User,
    test_workspace: Workspace,
    db_session: AsyncSession,
    redis_client,
):
    """Test callback updates existing token instead of creating duplicate."""
    # Setup: Create existing token
    existing_token = GoogleCalendarToken(
        workspace_id=test_workspace.id,
        user_id=test_user.id,
        access_token="ya29.old_access_token",
        refresh_token="1//old_refresh_token",
        token_expiry=datetime.now(UTC) + timedelta(minutes=30),
        scopes=["https://www.googleapis.com/auth/calendar"],
        enabled=False,  # Disabled
    )
    db_session.add(existing_token)
    await db_session.commit()
    existing_token_id = existing_token.id

    # Setup: Store state in Redis
    state = "test_state_update_token"
    redis_key = f"gcal_oauth_state:{state}"
    await redis_client.setex(redis_key, 600, str(test_workspace.id))

    # Mock OAuth flow
    mock_flow = MagicMock()
    mock_credentials = MagicMock()
    mock_credentials.token = "ya29.new_access_token"
    mock_credentials.refresh_token = "1//new_refresh_token"
    mock_credentials.expiry = datetime.now(UTC) + timedelta(hours=1)
    mock_credentials.scopes = ["https://www.googleapis.com/auth/calendar"]
    mock_flow.credentials = mock_credentials
    mock_flow_class.from_client_config.return_value = mock_flow

    # Make request
    response = await authenticated_client.get(
        f"/api/v1/integrations/google-calendar/callback?code=new_code&state={state}",
        follow_redirects=False,
    )

    # Verify redirect
    assert response.status_code == 302
    assert response.headers["location"].endswith("/settings?gcal=success")

    # Verify token was updated (NOT duplicated)
    query = select(GoogleCalendarToken).where(
        GoogleCalendarToken.workspace_id == test_workspace.id,
        GoogleCalendarToken.user_id == test_user.id,
    )
    result = await db_session.execute(query)
    tokens = result.scalars().all()

    # Should only have 1 token (updated, not duplicated)
    assert len(tokens) == 1
    token = tokens[0]
    assert token.id == existing_token_id  # Same token ID (updated)
    assert token.access_token == "ya29.new_access_token"
    assert token.refresh_token == "1//new_refresh_token"
    assert token.enabled is True  # Re-enabled


@pytest.mark.asyncio
async def test_authorize_redis_failure(
    authenticated_client: AsyncClient,
    test_user: User,
    redis_client,
):
    """Test POST /authorize handles Redis failure gracefully."""
    # Mock Redis to fail
    with patch.object(redis_client, "setex", side_effect=Exception("Redis down")):
        response = await authenticated_client.post(
            "/api/v1/integrations/google-calendar/authorize"
        )

        # Should return 500 with clear error message
        assert response.status_code == 500
        data = response.json()
        assert "Failed to initialize OAuth flow" in data["detail"]


@pytest.mark.asyncio
async def test_update_settings_success(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    """Test updating Google Calendar settings successfully."""
    # Create token
    token = GoogleCalendarToken(
        user_id=test_user.id,
        workspace_id=test_user.workspace_id,
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        token_expiry=datetime.now(UTC) + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/calendar"],
        enabled=False,
        sync_client_names=False,
    )
    db_session.add(token)
    await db_session.commit()

    # Update settings
    response = await authenticated_client.patch(
        "/api/v1/integrations/google-calendar/settings",
        json={"enabled": True, "sync_client_names": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert data["sync_client_names"] is True
    assert data["last_sync_at"] is None
    assert data["last_sync_status"] is None
    assert data["last_sync_error"] is None

    # Verify in database
    await db_session.refresh(token)
    assert token.enabled is True
    assert token.sync_client_names is True


@pytest.mark.asyncio
async def test_update_settings_partial_update(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    """Test partial settings update (only one field)."""
    # Create token with initial values
    token = GoogleCalendarToken(
        user_id=test_user.id,
        workspace_id=test_user.workspace_id,
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        token_expiry=datetime.now(UTC) + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/calendar"],
        enabled=True,
        sync_client_names=False,
    )
    db_session.add(token)
    await db_session.commit()

    # Update only sync_client_names
    response = await authenticated_client.patch(
        "/api/v1/integrations/google-calendar/settings",
        json={"sync_client_names": True},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True  # Unchanged
    assert data["sync_client_names"] is True  # Changed

    # Verify in database
    await db_session.refresh(token)
    assert token.enabled is True
    assert token.sync_client_names is True


@pytest.mark.asyncio
async def test_update_settings_not_connected(
    authenticated_client: AsyncClient,
    test_user: User,
):
    """Test updating settings when Google Calendar not connected."""
    response = await authenticated_client.patch(
        "/api/v1/integrations/google-calendar/settings",
        json={"sync_client_names": True},
    )

    assert response.status_code == 404
    assert "not connected" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_settings_workspace_isolation(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_user2: User,
):
    """Test settings update respects workspace boundaries."""
    # Create token for test_user2 (different workspace)
    token = GoogleCalendarToken(
        user_id=test_user2.id,
        workspace_id=test_user2.workspace_id,
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        token_expiry=datetime.now(UTC) + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/calendar"],
        enabled=False,
        sync_client_names=False,
    )
    db_session.add(token)
    await db_session.commit()

    # Try to update from test_user (authenticated_client) - different workspace
    response = await authenticated_client.patch(
        "/api/v1/integrations/google-calendar/settings",
        json={"sync_client_names": True},
    )

    # Should get 404 because token belongs to test_user2's workspace
    assert response.status_code == 404

    # Verify token unchanged
    await db_session.refresh(token)
    assert token.sync_client_names is False


@pytest.mark.asyncio
async def test_get_status_includes_sync_client_names(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    """Test GET /status returns sync_client_names field."""
    token = GoogleCalendarToken(
        user_id=test_user.id,
        workspace_id=test_user.workspace_id,
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        token_expiry=datetime.now(UTC) + timedelta(hours=1),
        scopes=["https://www.googleapis.com/auth/calendar"],
        enabled=True,
        sync_client_names=True,
    )
    db_session.add(token)
    await db_session.commit()

    response = await authenticated_client.get(
        "/api/v1/integrations/google-calendar/status"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True
    assert data["enabled"] is True
    assert data["sync_client_names"] is True
    assert data["last_sync_at"] is None
