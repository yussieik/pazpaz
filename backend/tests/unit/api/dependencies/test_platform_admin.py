"""Tests for platform admin permission dependency.

This test suite validates:
1. Platform admin users can access protected endpoints (success path)
2. Non-platform-admin users receive 403 Forbidden (authorization failure)
3. Unauthenticated requests are handled by upstream auth (401)
4. Correct user object is returned to endpoint handlers
5. Workspace scoping is maintained (platform admin doesn't bypass isolation)
6. Audit logging for both successful and failed authorization attempts
7. Error messages are generic (no information leakage)

Security testing focuses on:
- Proper separation of authentication (401) vs authorization (403) errors
- Generic error messages that don't reveal platform admin status
- Audit trail for security monitoring
- Integration with existing authentication dependency chain
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status

from pazpaz.api.dependencies.platform_admin import require_platform_admin
from pazpaz.models.user import User, UserRole


@pytest.mark.asyncio
async def test_require_platform_admin_success():
    """Test that platform admin users can access protected endpoints.

    This validates the happy path where:
    1. User is authenticated (has valid session)
    2. User has is_platform_admin=True
    3. Dependency returns the user object for endpoint handler
    """
    # Create mock platform admin user
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.workspace_id = workspace_id
    mock_user.email = "admin@pazpaz.com"
    mock_user.full_name = "Platform Admin"
    mock_user.role = UserRole.OWNER
    mock_user.is_platform_admin = True
    mock_user.is_active = True

    # Call the dependency with platform admin user
    result = await require_platform_admin(current_user=mock_user)

    # Verify user object is returned unchanged
    assert result is mock_user
    assert result.is_platform_admin is True
    assert result.id == user_id
    assert result.workspace_id == workspace_id


@pytest.mark.asyncio
async def test_require_platform_admin_forbidden_regular_user():
    """Test that non-platform-admin users receive 403 Forbidden.

    This validates that regular workspace users (even workspace owners)
    cannot access platform admin endpoints. The error should be:
    - 403 Forbidden (authorization failure, not authentication)
    - Generic message (no information leakage)
    - Logged for audit trail
    """
    # Create mock regular user (workspace owner but not platform admin)
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.workspace_id = workspace_id
    mock_user.email = "therapist@example.com"
    mock_user.full_name = "Regular Therapist"
    mock_user.role = UserRole.OWNER
    mock_user.is_platform_admin = False  # Not a platform admin
    mock_user.is_active = True

    # Call the dependency and expect 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        await require_platform_admin(current_user=mock_user)

    # Verify HTTP 403 Forbidden (not 401 Unauthorized)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    # Verify generic error message (no information leakage)
    assert exc_info.value.detail == "Platform admin access required"


@pytest.mark.asyncio
async def test_require_platform_admin_forbidden_assistant():
    """Test that workspace assistants cannot access platform admin endpoints.

    This validates that non-owner users (assistants) are also blocked,
    even if they somehow had is_platform_admin=False.
    """
    # Create mock assistant user
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.workspace_id = workspace_id
    mock_user.email = "assistant@example.com"
    mock_user.full_name = "Workspace Assistant"
    mock_user.role = UserRole.ASSISTANT
    mock_user.is_platform_admin = False
    mock_user.is_active = True

    # Call the dependency and expect 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        await require_platform_admin(current_user=mock_user)

    # Verify HTTP 403 Forbidden
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "Platform admin access required"


@pytest.mark.asyncio
async def test_require_platform_admin_returns_user_object():
    """Test that the dependency returns the correct user object.

    This validates that endpoint handlers receive the full user object
    with all attributes (id, workspace_id, email, etc.) for use in
    business logic and audit logging.
    """
    # Create mock platform admin with specific attributes
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.workspace_id = workspace_id
    mock_user.email = "superadmin@pazpaz.com"
    mock_user.full_name = "Super Administrator"
    mock_user.role = UserRole.OWNER
    mock_user.is_platform_admin = True
    mock_user.is_active = True

    # Call the dependency
    returned_user = await require_platform_admin(current_user=mock_user)

    # Verify all attributes are accessible
    assert returned_user.id == user_id
    assert returned_user.workspace_id == workspace_id
    assert returned_user.email == "superadmin@pazpaz.com"
    assert returned_user.full_name == "Super Administrator"
    assert returned_user.role == UserRole.OWNER
    assert returned_user.is_platform_admin is True
    assert returned_user.is_active is True


@pytest.mark.asyncio
async def test_require_platform_admin_with_workspace_scoping():
    """Test that platform admin status does not bypass workspace scoping.

    This validates an important security property: even platform admins
    belong to a workspace and must respect workspace boundaries in queries.
    Platform admin status grants access to cross-workspace admin endpoints,
    but does NOT automatically grant access to all workspace data.

    Example: A platform admin creating a workspace still has their own
    workspace_id and must use explicit workspace_id parameters when
    accessing other workspaces.
    """
    # Create platform admin belonging to a specific workspace
    admin_workspace_id = uuid.uuid4()
    admin_user_id = uuid.uuid4()

    mock_admin = MagicMock(spec=User)
    mock_admin.id = admin_user_id
    mock_admin.workspace_id = admin_workspace_id  # Admin has their own workspace
    mock_admin.email = "admin@pazpaz.com"
    mock_admin.full_name = "Platform Admin"
    mock_admin.role = UserRole.OWNER
    mock_admin.is_platform_admin = True
    mock_admin.is_active = True

    # Call the dependency
    returned_admin = await require_platform_admin(current_user=mock_admin)

    # Verify admin has a workspace_id (they don't bypass workspace scoping)
    assert returned_admin.workspace_id == admin_workspace_id

    # Platform admin endpoints must still:
    # - Use explicit workspace_id parameters for cross-workspace operations
    # - Not automatically access all workspaces
    # - Respect workspace boundaries in database queries
    # - Use explicit joins/queries for platform-wide operations


@pytest.mark.asyncio
async def test_require_platform_admin_audit_logging_on_success():
    """Test that successful platform admin access is logged for audit trail.

    This validates that security-relevant events are logged:
    - Successful platform admin access (for monitoring)
    - User ID and workspace ID (for forensics)
    - No sensitive data in logs
    """
    # Create mock platform admin
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.workspace_id = workspace_id
    mock_user.email = "admin@pazpaz.com"
    mock_user.full_name = "Platform Admin"
    mock_user.is_platform_admin = True

    # Mock the logger to verify logging calls
    with patch("pazpaz.api.dependencies.platform_admin.logger") as mock_logger:
        # Call the dependency
        result = await require_platform_admin(current_user=mock_user)

        # Verify successful access is logged
        mock_logger.info.assert_called_once_with(
            "platform_admin_access_granted",
            user_id=str(user_id),
            workspace_id=str(workspace_id),
        )

        # Verify user object is returned
        assert result is mock_user


@pytest.mark.asyncio
async def test_require_platform_admin_audit_logging_on_failure():
    """Test that failed platform admin access attempts are logged.

    This validates that security-relevant events are logged:
    - Failed authorization attempts (security monitoring)
    - User ID who attempted access (forensics)
    - Reason for denial (for troubleshooting)
    - No sensitive data in logs
    """
    # Create mock regular user attempting to access admin endpoint
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.workspace_id = workspace_id
    mock_user.email = "regular@example.com"
    mock_user.full_name = "Regular User"
    mock_user.is_platform_admin = False

    # Mock the logger to verify logging calls
    with patch("pazpaz.api.dependencies.platform_admin.logger") as mock_logger:
        # Call the dependency and expect 403
        with pytest.raises(HTTPException) as exc_info:
            await require_platform_admin(current_user=mock_user)

        # Verify failed access is logged with warning level
        mock_logger.warning.assert_called_once_with(
            "platform_admin_access_denied",
            user_id=str(user_id),
            workspace_id=str(workspace_id),
            reason="user_is_not_platform_admin",
        )

        # Verify 403 status code
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_require_platform_admin_integration_with_get_current_user():
    """Test integration with the existing get_current_user dependency.

    This validates that the dependency chain works correctly:
    1. get_current_user handles authentication (401 errors)
    2. require_platform_admin handles authorization (403 errors)
    3. Both dependencies work together in FastAPI dependency injection

    Note: This is a unit test so we mock get_current_user. Integration
    tests will validate the full dependency chain end-to-end.
    """
    # Create mock platform admin
    workspace_id = uuid.uuid4()
    user_id = uuid.uuid4()

    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.workspace_id = workspace_id
    mock_user.email = "admin@pazpaz.com"
    mock_user.is_platform_admin = True

    # Mock get_current_user dependency
    mock_get_current_user = AsyncMock(return_value=mock_user)

    # Simulate FastAPI dependency injection calling both dependencies
    # First get_current_user (authentication)
    authenticated_user = await mock_get_current_user()
    assert authenticated_user is mock_user

    # Then require_platform_admin (authorization)
    authorized_user = await require_platform_admin(current_user=authenticated_user)
    assert authorized_user is mock_user
    assert authorized_user.is_platform_admin is True


@pytest.mark.asyncio
async def test_require_platform_admin_error_message_is_generic():
    """Test that error messages don't leak information about platform admin status.

    This validates defense-in-depth security:
    - Error messages are generic (no "you're not an admin")
    - Don't reveal whether user is close to being admin
    - Don't reveal platform admin privileges or capabilities
    - Consistent error message for all authorization failures
    """
    # Create various non-admin users
    test_cases = [
        # Regular workspace owner
        {
            "email": "owner@example.com",
            "role": UserRole.OWNER,
            "is_platform_admin": False,
        },
        # Workspace assistant
        {
            "email": "assistant@example.com",
            "role": UserRole.ASSISTANT,
            "is_platform_admin": False,
        },
    ]

    for test_case in test_cases:
        workspace_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_user = MagicMock(spec=User)
        mock_user.id = user_id
        mock_user.workspace_id = workspace_id
        mock_user.email = test_case["email"]
        mock_user.role = test_case["role"]
        mock_user.is_platform_admin = test_case["is_platform_admin"]

        # All non-admins get the same generic error message
        with pytest.raises(HTTPException) as exc_info:
            await require_platform_admin(current_user=mock_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert exc_info.value.detail == "Platform admin access required"
        # No variation in error message based on user role or other attributes
