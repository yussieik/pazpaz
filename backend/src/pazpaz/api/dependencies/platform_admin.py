"""Platform admin permission dependencies for FastAPI.

This module provides FastAPI dependency functions for restricting access
to platform admin endpoints. Platform admins have elevated privileges beyond
normal workspace users and can perform cross-workspace administrative tasks.

Security:
    - Uses existing authentication (get_current_user)
    - Checks is_platform_admin flag on authenticated user
    - Returns 403 Forbidden (not 401) for authorization failures
    - Logs authorization failures for audit trail
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from pazpaz.api.deps import get_current_user
from pazpaz.core.logging import get_logger
from pazpaz.models.user import User

logger = get_logger(__name__)


async def require_platform_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require user to be a platform admin.

    This dependency checks that the authenticated user has platform admin
    privileges (is_platform_admin=True). Use this dependency on endpoints
    that should only be accessible to platform administrators.

    Platform admins can:
        - Create new workspaces and invite therapists
        - View all workspaces and their details
        - Suspend or delete workspaces
        - View platform-wide analytics and metrics
        - Manage platform configuration

    Access Control Flow:
        1. Request reaches endpoint with this dependency
        2. FastAPI executes get_current_user (authentication)
        3. If no valid session: 401 Unauthorized (from get_current_user)
        4. If authenticated but not platform admin: 403 Forbidden (from here)
        5. If platform admin: Pass user object to endpoint handler

    Security Considerations:
        - This dependency MUST follow get_current_user in the dependency chain
        - Never bypass authentication to check platform admin status
        - Always use 403 (not 401) for authorization failures
        - Log all authorization failures for security audit trail
        - Platform admin access does NOT bypass workspace scoping
          (admins still must respect workspace boundaries in queries)

    Args:
        current_user: Authenticated user from session (injected by FastAPI via
            get_current_user dependency)

    Returns:
        User: The authenticated platform admin user object. This can be used
            in the endpoint handler to access user.id, user.workspace_id, etc.

    Raises:
        HTTPException: 403 Forbidden if user is not a platform admin.
            The error message is intentionally generic to avoid information
            leakage about platform admin status.

    Example:
        Basic usage with router-level dependency:
        ```python
        from fastapi import APIRouter, Depends
        from pazpaz.api.dependencies.platform_admin import require_platform_admin

        router = APIRouter(
            prefix="/platform-admin",
            tags=["platform-admin"],
            dependencies=[Depends(require_platform_admin)],  # All routes protected
        )

        @router.get("/workspaces")
        async def list_workspaces():
            # Only platform admins can reach here
            pass
        ```

        Endpoint-level dependency with user access:
        ```python
        @router.post("/platform-admin/workspaces")
        async def create_workspace(
            admin: User = Depends(require_platform_admin),
            db: AsyncSession = Depends(get_db),
        ):
            # admin is guaranteed to be a platform admin user
            logger.info("workspace_creation", admin_id=str(admin.id))
            # ... create workspace logic
        ```

        Mixed access (some endpoints platform admin, others regular users):
        ```python
        @router.get("/workspaces")  # Regular users can view their workspace
        async def get_my_workspace(
            current_user: User = Depends(get_current_user),
        ):
            return current_user.workspace

        @router.get("/workspaces/all")  # Only admins see all workspaces
        async def list_all_workspaces(
            admin: User = Depends(require_platform_admin),
        ):
            return await fetch_all_workspaces()
        ```
    """
    if not current_user.is_platform_admin:
        # Log authorization failure for audit trail
        # Include user_id for forensics but no sensitive data
        logger.warning(
            "platform_admin_access_denied",
            user_id=str(current_user.id),
            workspace_id=str(current_user.workspace_id),
            reason="user_is_not_platform_admin",
        )

        # Return generic error message (don't reveal platform admin status)
        # Use 403 Forbidden (authorization failure) not 401 (authentication failure)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform admin access required",
        )

    # Log successful platform admin access for audit trail
    logger.info(
        "platform_admin_access_granted",
        user_id=str(current_user.id),
        workspace_id=str(current_user.workspace_id),
    )

    return current_user
