# FastAPI Dependencies

This directory contains FastAPI dependency injection modules for cross-cutting concerns like authentication, authorization, and permission checks.

## Available Dependencies

### Platform Admin Permission (`platform_admin.py`)

**Function**: `require_platform_admin(current_user: User = Depends(get_current_user)) -> User`

**Purpose**: Restricts endpoint access to platform administrators only.

**Usage**:

```python
from fastapi import APIRouter, Depends
from pazpaz.api.dependencies.platform_admin import require_platform_admin
from pazpaz.models.user import User

# Option 1: Router-level protection (all routes require platform admin)
router = APIRouter(
    prefix="/platform-admin",
    tags=["platform-admin"],
    dependencies=[Depends(require_platform_admin)],  # Apply to all routes
)

@router.get("/workspaces")
async def list_all_workspaces():
    """Only platform admins can access this endpoint."""
    # Implementation
    pass


# Option 2: Endpoint-level protection with user access
@router.post("/workspaces")
async def create_workspace(
    admin: User = Depends(require_platform_admin),  # Get admin user object
    db: AsyncSession = Depends(get_db),
):
    """Create new workspace - platform admin only."""
    logger.info("workspace_creation_requested", admin_id=str(admin.id))
    # admin.id, admin.workspace_id, admin.email available here
    pass
```

**Security Properties**:
- ✅ Requires valid authentication (via `get_current_user`)
- ✅ Checks `is_platform_admin=True` on user object
- ✅ Returns 403 Forbidden (not 401) for authorization failures
- ✅ Logs all authorization attempts for audit trail
- ✅ Generic error messages (no information leakage)
- ✅ Platform admin status does NOT bypass workspace scoping

**Error Responses**:
- `401 Unauthorized`: No valid session (from `get_current_user`)
- `403 Forbidden`: Authenticated but not platform admin

**Access Control Flow**:
1. Request reaches endpoint with `Depends(require_platform_admin)`
2. FastAPI executes `get_current_user` dependency (authentication)
3. If no session: 401 from `get_current_user`
4. If session but not platform admin: 403 from `require_platform_admin`
5. If platform admin: User object passed to endpoint handler

## Testing

Unit tests are located in `tests/unit/api/dependencies/test_platform_admin.py`.

Run tests:
```bash
env PYTHONPATH=src uv run pytest tests/unit/api/dependencies/test_platform_admin.py -v
```

## Implementation Notes

### Integration with Existing Auth

The `require_platform_admin` dependency builds on top of the existing authentication system:
- Uses `get_current_user` from `pazpaz.api.deps` for authentication
- Adds authorization layer on top (checks `is_platform_admin` flag)
- Does not duplicate authentication logic
- Maintains consistency with existing API patterns

### Workspace Scoping

**IMPORTANT**: Platform admin status does NOT bypass workspace scoping.

Platform admins:
- ✅ Can access platform admin endpoints
- ✅ Can perform cross-workspace administrative tasks (create workspaces, etc.)
- ❌ Do NOT automatically have access to all workspace data
- ❌ Must still respect workspace boundaries in database queries

Example:
```python
@router.get("/platform-admin/workspaces/{workspace_id}")
async def get_workspace_details(
    workspace_id: uuid.UUID,
    admin: User = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    """Platform admin can view any workspace by explicit ID."""
    # Explicitly query workspace by ID (not filtered by admin.workspace_id)
    workspace = await db.get(Workspace, workspace_id)

    # NOTE: admin.workspace_id is the admin's own workspace
    # They can access other workspaces via explicit workspace_id parameter
    pass
```

### Audit Logging

All authorization attempts are logged:

**Success** (INFO level):
```python
logger.info(
    "platform_admin_access_granted",
    user_id=str(user_id),
    workspace_id=str(workspace_id),
)
```

**Failure** (WARNING level):
```python
logger.warning(
    "platform_admin_access_denied",
    user_id=str(user_id),
    workspace_id=str(workspace_id),
    reason="user_is_not_platform_admin",
)
```

These logs enable security monitoring and forensic analysis.

## See Also

- `pazpaz.api.deps.get_current_user` - Primary authentication dependency
- `pazpaz.models.user.User` - User model with `is_platform_admin` field
- Platform Admin Implementation Guide: `/docs/PLATFORM_ADMIN_IMPLEMENTATION_GUIDE.md`
