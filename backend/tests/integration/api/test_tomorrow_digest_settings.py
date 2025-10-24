"""Test Tomorrow's Digest notification settings.

This test suite validates the new tomorrow_digest_* fields added to
user_notification_settings table to support independent tomorrow's digest
functionality.

Tests cover:
- Schema validation (columns exist, correct types, defaults)
- API integration (GET/PUT endpoints)
- Independence from today's digest
- Database constraints and validation
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.user import User
from pazpaz.models.user_notification_settings import UserNotificationSettings
from pazpaz.models.workspace import Workspace
from tests.conftest import add_csrf_to_client, get_auth_headers

pytestmark = pytest.mark.asyncio


class TestTomorrowDigestSchema:
    """Test tomorrow's digest database schema."""

    async def test_tomorrow_digest_columns_exist(
        self,
        db_session: AsyncSession,
    ):
        """Verify tomorrow_digest_* columns exist with correct types."""
        # Query column information
        query = text("""
            SELECT
                column_name,
                data_type,
                column_default,
                is_nullable
            FROM information_schema.columns
            WHERE table_name = 'user_notification_settings'
            AND column_name LIKE '%tomorrow%'
            ORDER BY ordinal_position
        """)

        result = await db_session.execute(query)
        columns = {row.column_name: row for row in result}

        # Verify all three columns exist
        assert "tomorrow_digest_enabled" in columns
        assert "tomorrow_digest_time" in columns
        assert "tomorrow_digest_days" in columns

        # Verify types
        assert columns["tomorrow_digest_enabled"].data_type == "boolean"
        assert columns["tomorrow_digest_time"].data_type == "character varying"
        assert columns["tomorrow_digest_days"].data_type == "ARRAY"

        # Verify nullability
        assert columns["tomorrow_digest_enabled"].is_nullable == "NO"
        assert columns["tomorrow_digest_time"].is_nullable == "YES"
        assert columns["tomorrow_digest_days"].is_nullable == "NO"

        # Verify defaults
        assert "false" in columns["tomorrow_digest_enabled"].column_default
        assert "20:00" in columns["tomorrow_digest_time"].column_default
        assert "{0,1,2,3,4}" in columns["tomorrow_digest_days"].column_default

    async def test_tomorrow_digest_time_check_constraint_exists(
        self,
        db_session: AsyncSession,
    ):
        """Verify CHECK constraint for tomorrow_digest_time format."""
        query = text("""
            SELECT
                conname,
                pg_get_constraintdef(c.oid) AS constraint_def
            FROM pg_constraint c
            JOIN pg_namespace n ON n.oid = c.connamespace
            WHERE contype = 'c'
            AND conname = 'ck_tomorrow_digest_time_format'
        """)

        result = await db_session.execute(query)
        constraint = result.first()

        assert constraint is not None
        assert "tomorrow_digest_time" in constraint.constraint_def
        assert "~" in constraint.constraint_def  # Regex operator
        assert "([0-1][0-9]|2[0-3]):[0-5][0-9]" in constraint.constraint_def

    async def test_tomorrow_digest_partial_index_exists(
        self,
        db_session: AsyncSession,
    ):
        """Verify partial index for tomorrow's digest batch queries."""
        query = text("""
            SELECT
                indexname,
                indexdef
            FROM pg_indexes
            WHERE tablename = 'user_notification_settings'
            AND indexname = 'idx_user_notification_settings_tomorrow_digest'
        """)

        result = await db_session.execute(query)
        index = result.first()

        assert index is not None
        assert "tomorrow_digest_enabled" in index.indexdef
        assert "tomorrow_digest_time" in index.indexdef
        # Verify partial index WHERE clause
        assert "email_enabled = true" in index.indexdef
        assert "tomorrow_digest_enabled = true" in index.indexdef


class TestTomorrowDigestDefaults:
    """Test default values for tomorrow's digest fields."""

    async def test_new_settings_have_correct_defaults(
        self,
        db_session: AsyncSession,
        workspace_1: Workspace,
        test_user_ws1: User,
    ):
        """New notification settings have correct tomorrow's digest defaults."""
        # Create settings (let DB apply defaults)
        settings = UserNotificationSettings(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
        )
        db_session.add(settings)
        await db_session.commit()
        await db_session.refresh(settings)

        # Verify defaults
        assert settings.tomorrow_digest_enabled is False  # Default OFF
        assert settings.tomorrow_digest_time == "20:00"  # Default 8 PM
        assert settings.tomorrow_digest_days == [0, 1, 2, 3, 4]  # Default Mon-Fri

    async def test_tomorrow_digest_independent_from_today_digest(
        self,
        db_session: AsyncSession,
        workspace_1: Workspace,
        test_user_ws1: User,
    ):
        """Tomorrow's digest and today's digest can be configured independently."""
        # Create settings with different digest configurations
        settings = UserNotificationSettings(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            # Today's digest: ON, 7 AM, Mon-Fri
            digest_enabled=True,
            digest_time="07:00",
            digest_days=[1, 2, 3, 4, 5],
            # Tomorrow's digest: OFF, 8 PM, Mon-Fri
            tomorrow_digest_enabled=False,
            tomorrow_digest_time="20:00",
            tomorrow_digest_days=[0, 1, 2, 3, 4],
        )
        db_session.add(settings)
        await db_session.commit()
        await db_session.refresh(settings)

        # Verify both digests are independent
        assert settings.digest_enabled is True
        assert settings.tomorrow_digest_enabled is False
        assert settings.digest_time == "07:00"
        assert settings.tomorrow_digest_time == "20:00"


class TestTomorrowDigestAPI:
    """Test API endpoints for tomorrow's digest settings."""

    async def test_get_settings_includes_tomorrow_digest(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """GET endpoint returns tomorrow's digest fields."""
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

        response = await client.get(
            "/api/v1/users/me/notification-settings",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify tomorrow's digest fields exist
        assert "tomorrow_digest_enabled" in data
        assert "tomorrow_digest_time" in data
        assert "tomorrow_digest_days" in data

        # Verify default values
        assert data["tomorrow_digest_enabled"] is False
        assert data["tomorrow_digest_time"] == "20:00"
        assert data["tomorrow_digest_days"] == [0, 1, 2, 3, 4]

    async def test_update_tomorrow_digest_settings(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """PUT endpoint can update tomorrow's digest settings."""
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
                "tomorrow_digest_enabled": True,
                "tomorrow_digest_time": "19:00",
                "tomorrow_digest_days": [1, 2, 3, 4, 5],  # Mon-Fri
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["tomorrow_digest_enabled"] is True
        assert data["tomorrow_digest_time"] == "19:00"
        assert data["tomorrow_digest_days"] == [1, 2, 3, 4, 5]

    async def test_update_tomorrow_digest_independent(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Updating tomorrow's digest doesn't affect today's digest."""
        settings = UserNotificationSettings(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            digest_enabled=True,
            digest_time="08:00",
            digest_days=[1, 2, 3, 4, 5],
        )
        db_session.add(settings)
        await db_session.commit()

        csrf_token = await add_csrf_to_client(
            client, workspace_1.id, test_user_ws1.id, redis_client
        )
        headers = get_auth_headers(workspace_1.id, csrf_cookie=csrf_token)
        headers["X-CSRF-Token"] = csrf_token

        # Update only tomorrow's digest
        response = await client.put(
            "/api/v1/users/me/notification-settings",
            headers=headers,
            json={
                "tomorrow_digest_enabled": True,
                "tomorrow_digest_time": "20:00",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Verify tomorrow's digest updated
        assert data["tomorrow_digest_enabled"] is True
        assert data["tomorrow_digest_time"] == "20:00"

        # Verify today's digest unchanged
        assert data["digest_enabled"] is True
        assert data["digest_time"] == "08:00"
        assert data["digest_days"] == [1, 2, 3, 4, 5]


class TestTomorrowDigestValidation:
    """Test validation for tomorrow's digest fields."""

    async def test_invalid_tomorrow_digest_time_format(
        self,
        client: AsyncClient,
        workspace_1: Workspace,
        test_user_ws1: User,
        redis_client,
        db_session: AsyncSession,
    ):
        """Invalid time format for tomorrow_digest_time returns 422."""
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

        invalid_times = [
            "25:00",  # Invalid hour
            "23:60",  # Invalid minute
            "8:00",  # Missing leading zero
            "20:0",  # Missing trailing zero
        ]

        for invalid_time in invalid_times:
            response = await client.put(
                "/api/v1/users/me/notification-settings",
                headers=headers,
                json={"tomorrow_digest_time": invalid_time},
            )

            assert response.status_code == 422

    async def test_model_validation_tomorrow_digest_time(
        self,
        db_session: AsyncSession,
        workspace_1: Workspace,
        test_user_ws1: User,
    ):
        """Model validation catches invalid tomorrow_digest_time format."""
        settings = UserNotificationSettings(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            tomorrow_digest_time="25:00",  # Invalid
        )

        errors = settings.validate()
        assert len(errors) > 0
        assert any("tomorrow_digest_time" in err for err in errors)


class TestTomorrowDigestHelperMethods:
    """Test helper methods for tomorrow's digest."""

    async def test_should_send_tomorrow_digest_property(
        self,
        db_session: AsyncSession,
        workspace_1: Workspace,
        test_user_ws1: User,
    ):
        """Test should_send_tomorrow_digest helper property."""
        # Test when both email and tomorrow digest enabled
        settings = UserNotificationSettings(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email_enabled=True,
            tomorrow_digest_enabled=True,
        )
        assert settings.should_send_tomorrow_digest is True

        # Test when email disabled
        settings.email_enabled = False
        assert settings.should_send_tomorrow_digest is False

        # Test when tomorrow digest disabled
        settings.email_enabled = True
        settings.tomorrow_digest_enabled = False
        assert settings.should_send_tomorrow_digest is False

        # Test when both disabled
        settings.email_enabled = False
        settings.tomorrow_digest_enabled = False
        assert settings.should_send_tomorrow_digest is False


class TestBothDigestsCoexistence:
    """Test that both today's and tomorrow's digests can coexist."""

    async def test_both_digests_enabled(
        self,
        db_session: AsyncSession,
        workspace_1: Workspace,
        test_user_ws1: User,
    ):
        """Both digests can be enabled simultaneously."""
        settings = UserNotificationSettings(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email_enabled=True,
            # Today's digest
            digest_enabled=True,
            digest_time="07:00",
            digest_days=[1, 2, 3, 4, 5],
            # Tomorrow's digest
            tomorrow_digest_enabled=True,
            tomorrow_digest_time="20:00",
            tomorrow_digest_days=[0, 1, 2, 3, 4, 5, 6],
        )
        db_session.add(settings)
        await db_session.commit()
        await db_session.refresh(settings)

        # Verify both helpers return True
        assert settings.should_send_digest is True
        assert settings.should_send_tomorrow_digest is True

        # Verify different configurations
        assert settings.digest_time != settings.tomorrow_digest_time
        assert settings.digest_days != settings.tomorrow_digest_days

    async def test_only_tomorrow_digest_enabled(
        self,
        db_session: AsyncSession,
        workspace_1: Workspace,
        test_user_ws1: User,
    ):
        """Only tomorrow's digest enabled, today's disabled."""
        settings = UserNotificationSettings(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email_enabled=True,
            digest_enabled=False,
            tomorrow_digest_enabled=True,
        )
        db_session.add(settings)
        await db_session.commit()
        await db_session.refresh(settings)

        assert settings.should_send_digest is False
        assert settings.should_send_tomorrow_digest is True

    async def test_only_today_digest_enabled(
        self,
        db_session: AsyncSession,
        workspace_1: Workspace,
        test_user_ws1: User,
    ):
        """Only today's digest enabled, tomorrow's disabled."""
        settings = UserNotificationSettings(
            user_id=test_user_ws1.id,
            workspace_id=workspace_1.id,
            email_enabled=True,
            digest_enabled=True,
            tomorrow_digest_enabled=False,
        )
        db_session.add(settings)
        await db_session.commit()
        await db_session.refresh(settings)

        assert settings.should_send_digest is True
        assert settings.should_send_tomorrow_digest is False
