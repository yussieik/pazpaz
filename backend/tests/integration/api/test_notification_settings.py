"""Test User Notification Settings API endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.user import User
from pazpaz.models.user_notification_settings import UserNotificationSettings
from pazpaz.models.workspace import Workspace
from tests.conftest import add_csrf_to_client, get_auth_headers

pytestmark = pytest.mark.asyncio


class TestGetNotificationSettings:
    """Test GET /api/v1/users/me/notification-settings endpoint."""

    async def test_get_settings_success(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Happy path: Get notification settings for authenticated user."""
        # Create settings for the user
        settings = UserNotificationSettings(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
        )
        db_session.add(settings)
        await db_session.commit()
        await db_session.refresh(settings)

        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)

        response = await client.get(
            "/api/v1/users/me/notification-settings",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "id" in data
        assert data["user_id"] == str(test_user_ws1.id)
        assert data["workspace_id"] == str(workspace_1.id)

        # Verify default values
        assert data["email_enabled"] is True
        assert data["notify_appointment_booked"] is True
        assert data["notify_appointment_cancelled"] is True
        assert data["notify_appointment_rescheduled"] is True
        assert data["notify_appointment_confirmed"] is True
        assert data["digest_enabled"] is False
        assert data["digest_time"] == "08:00"
        assert data["digest_skip_weekends"] is True
        assert data["reminder_enabled"] is True
        assert data["reminder_minutes"] == 60
        assert data["notes_reminder_enabled"] is True
        assert data["notes_reminder_time"] == "18:00"

        # Verify audit fields
        assert "created_at" in data
        assert "updated_at" in data

    async def test_get_settings_creates_defaults_if_missing(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Get settings automatically creates defaults if they don't exist."""
        # Delete any existing settings
        query = select(UserNotificationSettings).where(
            UserNotificationSettings.user_id == test_user_ws1.id
        )
        result = await db_session.execute(query)
        existing = result.scalar_one_or_none()
        if existing:
            await db_session.delete(existing)
            await db_session.commit()

        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)

        response = await client.get(
            "/api/v1/users/me/notification-settings",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == str(test_user_ws1.id)

        # Verify settings were created in database
        query = select(UserNotificationSettings).where(
            UserNotificationSettings.user_id == test_user_ws1.id
        )
        result = await db_session.execute(query)
        settings = result.scalar_one_or_none()
        assert settings is not None

    async def test_get_settings_requires_authentication(
        self,
        client: AsyncClient,
    ):
        """Get settings requires authentication."""
        response = await client.get(
            "/api/v1/users/me/notification-settings",
        )

        assert response.status_code == 401


class TestUpdateNotificationSettings:
    """Test PUT /api/v1/users/me/notification-settings endpoint."""

    async def test_update_master_toggle(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Update master email toggle."""
        # Create settings
        settings = UserNotificationSettings(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
        )
        db_session.add(settings)
        await db_session.commit()

        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.put(
            "/api/v1/users/me/notification-settings",
            headers=headers,
            json={"email_enabled": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email_enabled"] is False

    async def test_update_event_notifications(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Update event notification toggles."""
        settings = UserNotificationSettings(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
        )
        db_session.add(settings)
        await db_session.commit()

        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.put(
            "/api/v1/users/me/notification-settings",
            headers=headers,
            json={
                "notify_appointment_booked": False,
                "notify_appointment_cancelled": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["notify_appointment_booked"] is False
        assert data["notify_appointment_cancelled"] is False
        # Other settings unchanged
        assert data["notify_appointment_rescheduled"] is True

    async def test_update_digest_settings(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Update daily digest settings."""
        settings = UserNotificationSettings(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
        )
        db_session.add(settings)
        await db_session.commit()

        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.put(
            "/api/v1/users/me/notification-settings",
            headers=headers,
            json={
                "digest_enabled": True,
                "digest_time": "09:30",
                "digest_skip_weekends": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["digest_enabled"] is True
        assert data["digest_time"] == "09:30"
        assert data["digest_skip_weekends"] is False

    async def test_update_reminder_settings(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Update appointment reminder settings."""
        settings = UserNotificationSettings(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
        )
        db_session.add(settings)
        await db_session.commit()

        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.put(
            "/api/v1/users/me/notification-settings",
            headers=headers,
            json={
                "reminder_enabled": False,
                "reminder_minutes": 1440,  # 1 day
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["reminder_enabled"] is False
        assert data["reminder_minutes"] == 1440

    async def test_update_partial_update(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Partial updates work correctly (only update provided fields)."""
        settings = UserNotificationSettings(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
        )
        db_session.add(settings)
        await db_session.commit()

        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Update only one field
        response = await client.put(
            "/api/v1/users/me/notification-settings",
            headers=headers,
            json={"digest_enabled": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["digest_enabled"] is True
        # Verify other fields remain at defaults
        assert data["email_enabled"] is True
        assert data["reminder_enabled"] is True

    async def test_update_creates_settings_if_missing(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Update creates settings with defaults if they don't exist."""
        # Delete any existing settings
        query = select(UserNotificationSettings).where(
            UserNotificationSettings.user_id == test_user_ws1.id
        )
        result = await db_session.execute(query)
        existing = result.scalar_one_or_none()
        if existing:
            await db_session.delete(existing)
            await db_session.commit()

        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        response = await client.put(
            "/api/v1/users/me/notification-settings",
            headers=headers,
            json={"digest_enabled": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["digest_enabled"] is True
        assert data["email_enabled"] is True  # Default value

    async def test_update_invalid_time_format(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Update with invalid time format returns 422 (Pydantic validation)."""
        settings = UserNotificationSettings(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
        )
        db_session.add(settings)
        await db_session.commit()

        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Test various invalid time formats
        invalid_times = [
            "25:00",  # Invalid hour
            "23:60",  # Invalid minute
            "8:00",  # Missing leading zero
            "08:0",  # Missing trailing zero
            "8:0",  # Both missing
            "abc",  # Not a time
        ]

        for invalid_time in invalid_times:
            response = await client.put(
                "/api/v1/users/me/notification-settings",
                headers=headers,
                json={"digest_time": invalid_time},
            )

            # Pydantic validation returns 422
            # Note: The exact error format may vary, but we expect validation failure
            assert response.status_code == 422

    async def test_update_invalid_reminder_minutes(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Update with invalid reminder minutes returns 422 (Pydantic validation)."""
        settings = UserNotificationSettings(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
        )
        db_session.add(settings)
        await db_session.commit()

        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Test various invalid reminder minutes
        invalid_minutes = [5, 10, 45, 90, 100, 2880]

        for invalid_min in invalid_minutes:
            response = await client.put(
                "/api/v1/users/me/notification-settings",
                headers=headers,
                json={"reminder_minutes": invalid_min},
            )

            # Pydantic validation returns 422
            # Note: The exact error format may vary, but we expect validation failure
            assert response.status_code == 422

    async def test_update_valid_reminder_minutes(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Update with all valid reminder minutes presets."""
        settings = UserNotificationSettings(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
        )
        db_session.add(settings)
        await db_session.commit()

        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Test all valid presets
        valid_minutes = [15, 30, 60, 120, 1440]

        for valid_min in valid_minutes:
            response = await client.put(
                "/api/v1/users/me/notification-settings",
                headers=headers,
                json={"reminder_minutes": valid_min},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["reminder_minutes"] == valid_min

    async def test_update_requires_authentication(
        self,
        client: AsyncClient,
    ):
        """Update settings requires authentication (no access_token cookie)."""
        # Don't set any cookies or headers - completely unauthenticated request
        response = await client.put(
            "/api/v1/users/me/notification-settings",
            json={"email_enabled": False},
        )

        # Should return 401 for missing authentication
        # Note: Without access_token cookie, authentication fails before CSRF check
        assert response.status_code in [401, 403]  # Both are acceptable for unauthenticated requests

    async def test_update_requires_csrf_token(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
    ):
        """Update settings requires CSRF token."""
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        # Don't include X-CSRF-Token header

        response = await client.put(
            "/api/v1/users/me/notification-settings",
            headers=headers,
            json={"email_enabled": False},
        )

        assert response.status_code == 403


class TestWorkspaceIsolation:
    """Test workspace isolation for notification settings."""

    async def test_user_cannot_access_other_workspace_settings(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        workspace_2: Workspace,
        test_user_ws1: User,
        test_user_ws2: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """User can only access their own workspace's settings."""
        # Create settings for both users
        settings_ws1 = UserNotificationSettings(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
        )
        settings_ws2 = UserNotificationSettings(
            user_id=test_user_ws2.id,
            workspace_id=workspace_2.id,
        )
        db_session.add(settings_ws1)
        db_session.add(settings_ws2)
        await db_session.commit()

        # Authenticate as user from workspace 1
        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)

        # Get settings (should return workspace 1 settings)
        response = await client.get(
            "/api/v1/users/me/notification-settings",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["workspace_id"] == str(workspace_1.id)
        assert data["user_id"] == str(test_user_ws1.id)


class TestUserOnboarding:
    """Test that new users get default notification settings."""

    async def test_new_user_has_default_settings(
        self,
        db_session: AsyncSession,
        workspace_1: Workspace,
    ):
        """New users created through onboarding get default notification settings."""
        from pazpaz.services.platform_onboarding_service import (
            PlatformOnboardingService,
        )

        service = PlatformOnboardingService()

        # Create new workspace and user
        workspace, user, token = await service.create_workspace_and_invite_therapist(
            db=db_session,
            workspace_name="Test Clinic",
            therapist_email="test@example.com",
            therapist_full_name="Test User",
        )

        # Verify notification settings were created
        query = select(UserNotificationSettings).where(
            UserNotificationSettings.user_id == user.id
        )
        result = await db_session.execute(query)
        settings = result.scalar_one_or_none()

        assert settings is not None
        assert settings.user_id == user.id
        assert settings.workspace_id == workspace.id
        assert settings.email_enabled is True
        assert settings.digest_enabled is False
        assert settings.reminder_enabled is True
