"""Platform admin API endpoints for therapist onboarding."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.api.dependencies.platform_admin import require_platform_admin
from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger
from pazpaz.db.base import get_db
from pazpaz.models.audit_event import AuditAction, AuditEvent, ResourceType
from pazpaz.models.email_blacklist import EmailBlacklist
from pazpaz.models.user import User
from pazpaz.models.workspace import Workspace, WorkspaceStatus
from pazpaz.services.email_service import send_invitation_email
from pazpaz.services.platform_onboarding_service import (
    DuplicateEmailError,
    EmailBlacklistedError,
    InvitationNotFoundError,
    PlatformOnboardingService,
    UserAlreadyActiveError,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/platform-admin",
    tags=["platform-admin"],
    dependencies=[Depends(require_platform_admin)],
)


# ============================================================================
# Request/Response Schemas
# ============================================================================


class InviteTherapistRequest(BaseModel):
    """Request schema for inviting a therapist.

    Example:
        ```json
        {
            "workspace_name": "Sarah's Massage Therapy",
            "therapist_email": "sarah@example.com",
            "therapist_full_name": "Sarah Chen"
        }
        ```
    """

    workspace_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Name of the workspace to create",
        examples=["Sarah's Massage Therapy"],
    )
    therapist_email: EmailStr = Field(
        ...,
        description="Email address of the therapist (must be unique)",
        examples=["sarah@example.com"],
    )
    therapist_full_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Full name of the therapist",
        examples=["Sarah Chen"],
    )

    @field_validator("workspace_name", "therapist_full_name")
    @classmethod
    def validate_not_empty(cls, v: str, info) -> str:
        """Validate that string fields are not empty or whitespace-only."""
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} cannot be empty or whitespace-only")
        return v.strip()


class InviteTherapistResponse(BaseModel):
    """Response schema for therapist invitation.

    Example:
        ```json
        {
            "workspace_id": "123e4567-e89b-12d3-a456-426614174000",
            "user_id": "987e6543-e21b-34c5-b678-123456789012",
            "invitation_url": "https://app.pazpaz.com/accept-invitation?token=..."
        }
        ```
    """

    workspace_id: uuid.UUID = Field(
        ...,
        description="UUID of the created workspace",
    )
    user_id: uuid.UUID = Field(
        ...,
        description="UUID of the created user (therapist)",
    )
    invitation_url: str = Field(
        ...,
        description="Magic link URL to send to therapist via email",
        examples=["https://app.pazpaz.com/accept-invitation?token=abc123..."],
    )


class ResendInvitationResponse(BaseModel):
    """Response schema for resending invitation.

    Example:
        ```json
        {
            "invitation_url": "https://app.pazpaz.com/accept-invitation?token=..."
        }
        ```
    """

    invitation_url: str = Field(
        ...,
        description="New magic link URL to send to therapist via email",
        examples=["https://app.pazpaz.com/accept-invitation?token=def456..."],
    )


class PendingInvitation(BaseModel):
    """Single pending invitation details.

    Example:
        ```json
        {
            "user_id": "987e6543-e21b-34c5-b678-123456789012",
            "email": "sarah@example.com",
            "full_name": "Sarah Chen",
            "workspace_name": "Sarah's Massage Therapy",
            "invited_at": "2025-10-15T10:30:00Z",
            "expires_at": "2025-10-22T10:30:00Z"
        }
        ```
    """

    user_id: uuid.UUID = Field(..., description="UUID of the user")
    email: str = Field(..., description="Email address of the therapist")
    full_name: str = Field(..., description="Full name of the therapist")
    workspace_name: str = Field(..., description="Name of the workspace")
    invited_at: datetime = Field(
        ..., description="When invitation was sent (UTC timezone)"
    )
    expires_at: datetime = Field(
        ..., description="When invitation expires (UTC timezone)"
    )


class PendingInvitationsResponse(BaseModel):
    """Response schema for listing pending invitations.

    Example:
        ```json
        {
            "invitations": [
                {
                    "user_id": "987e6543-e21b-34c5-b678-123456789012",
                    "email": "sarah@example.com",
                    "full_name": "Sarah Chen",
                    "workspace_name": "Sarah's Massage Therapy",
                    "invited_at": "2025-10-15T10:30:00Z",
                    "expires_at": "2025-10-22T10:30:00Z"
                }
            ]
        }
        ```
    """

    invitations: list[PendingInvitation] = Field(
        default_factory=list,
        description="List of pending invitations (not yet accepted)",
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/invite-therapist",
    response_model=InviteTherapistResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite a new therapist",
    description="""
    Create a new workspace and invite a therapist to join the platform.

    Security:
    - Requires platform admin authentication
    - Email uniqueness enforced (400 if duplicate)
    - Invitation token SHA256 hashed in database
    - Token expires in 7 days
    - Audit logging for all invitations

    Flow:
    1. Platform admin provides workspace name, therapist email, and full name
    2. System creates workspace and inactive user account
    3. System generates invitation token (256-bit entropy)
    4. Platform admin receives invitation URL to send via email
    5. Therapist clicks link and accepts invitation to activate account

    Error Responses:
    - 400: Email already exists (duplicate)
    - 401: Not authenticated
    - 403: Not platform admin
    - 422: Validation error (invalid email, empty fields)
    """,
)
async def invite_therapist(
    request_data: InviteTherapistRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_platform_admin)],
) -> InviteTherapistResponse:
    """
    Invite a new therapist by creating workspace and user account.

    The invitation URL must be sent to the therapist via email.
    The therapist must accept the invitation within 7 days to activate their account.

    Args:
        request_data: Workspace and therapist details
        db: Database session (injected)
        admin: Authenticated platform admin (injected)

    Returns:
        InviteTherapistResponse with workspace_id, user_id, and invitation_url

    Raises:
        HTTPException: 400 if email already exists, 422 if validation fails
    """
    service = PlatformOnboardingService()

    try:
        workspace, user, token = await service.create_workspace_and_invite_therapist(
            db=db,
            workspace_name=request_data.workspace_name,
            therapist_email=request_data.therapist_email,
            therapist_full_name=request_data.therapist_full_name,
        )

        # Generate invitation URL with frontend URL
        invitation_url = f"{settings.frontend_url}/accept-invitation?token={token}"

        # Send invitation email
        # Handle email errors gracefully - invitation is already created
        try:
            await send_invitation_email(
                email=user.email,
                invitation_url=invitation_url,
            )
            logger.info(
                "invitation_email_sent_successfully",
                admin_id=str(admin.id),
                user_id=str(user.id),
                email=user.email,
            )
        except Exception as e:
            # Log error but don't block the response
            # The invitation is valid, admin can manually send the URL
            logger.error(
                "invitation_email_failed",
                admin_id=str(admin.id),
                user_id=str(user.id),
                email=user.email,
                error=str(e),
                exc_info=True,
            )

        logger.info(
            "therapist_invited",
            admin_id=str(admin.id),
            workspace_id=str(workspace.id),
            user_id=str(user.id),
            email=user.email,
        )

        return InviteTherapistResponse(
            workspace_id=workspace.id,
            user_id=user.id,
            invitation_url=invitation_url,
        )

    except EmailBlacklistedError as e:
        logger.warning(
            "invite_therapist_blacklisted_email",
            admin_id=str(admin.id),
            email=request_data.therapist_email,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This email address is blacklisted and cannot receive invitations",
        ) from e

    except DuplicateEmailError as e:
        logger.warning(
            "invite_therapist_duplicate_email",
            admin_id=str(admin.id),
            email=request_data.therapist_email,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists",
        ) from e

    except ValueError as e:
        logger.warning(
            "invite_therapist_validation_error",
            admin_id=str(admin.id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e


@router.post(
    "/resend-invitation/{user_id}",
    response_model=ResendInvitationResponse,
    status_code=status.HTTP_200_OK,
    summary="Resend invitation to pending user",
    description="""
    Generate a new invitation token for a user who has not yet accepted
    their invitation.

    Security:
    - Requires platform admin authentication
    - Only works for inactive users (is_active=False)
    - Old token is invalidated (replaced with new one)
    - New 7-day expiration window
    - Audit logging for resends

    Use Cases:
    - Original invitation expired (>7 days)
    - Therapist lost invitation email
    - Invitation token compromised

    Error Responses:
    - 400: User is already active (invitation already accepted)
    - 401: Not authenticated
    - 403: Not platform admin
    - 404: User not found
    - 422: Invalid UUID format
    """,
)
async def resend_invitation(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_platform_admin)],
) -> ResendInvitationResponse:
    """
    Resend invitation to a user who has not yet accepted.

    Generates a new invitation token and invalidates the old one.
    The new invitation URL must be sent to the therapist via email.

    Args:
        user_id: UUID of the user to resend invitation to
        db: Database session (injected)
        admin: Authenticated platform admin (injected)

    Returns:
        ResendInvitationResponse with new invitation_url

    Raises:
        HTTPException: 404 if user not found, 400 if already active
    """
    service = PlatformOnboardingService()

    try:
        token = await service.resend_invitation(db=db, user_id=user_id)

        # Get user email for sending email
        user_result = await db.get(User, user_id)
        if not user_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Generate invitation URL with frontend URL
        invitation_url = f"{settings.frontend_url}/accept-invitation?token={token}"

        # Send invitation email
        # Handle email errors gracefully - invitation token is already regenerated
        try:
            await send_invitation_email(
                email=user_result.email,
                invitation_url=invitation_url,
            )
            logger.info(
                "resend_invitation_email_sent_successfully",
                admin_id=str(admin.id),
                user_id=str(user_id),
                email=user_result.email,
            )
        except Exception as e:
            # Log error but don't block the response
            # The new token is valid, admin can manually send the URL
            logger.error(
                "resend_invitation_email_failed",
                admin_id=str(admin.id),
                user_id=str(user_id),
                email=user_result.email,
                error=str(e),
                exc_info=True,
            )

        logger.info(
            "invitation_resent",
            admin_id=str(admin.id),
            user_id=str(user_id),
        )

        return ResendInvitationResponse(invitation_url=invitation_url)

    except InvitationNotFoundError as e:
        logger.warning(
            "resend_invitation_user_not_found",
            admin_id=str(admin.id),
            user_id=str(user_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        ) from e

    except UserAlreadyActiveError as e:
        logger.warning(
            "resend_invitation_already_active",
            admin_id=str(admin.id),
            user_id=str(user_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has already accepted invitation and is active",
        ) from e


@router.get(
    "/pending-invitations",
    response_model=PendingInvitationsResponse,
    status_code=status.HTTP_200_OK,
    summary="List all pending invitations",
    description="""
    Get a list of all users who have been invited but have not yet accepted
    their invitation.

    Security:
    - Requires platform admin authentication
    - Returns only inactive users (is_active=False)
    - Includes expiration status (calculated from invited_at + 7 days)
    - Sorted by invited_at (newest first)

    Response includes:
    - user_id: UUID of the user
    - email: Email address
    - full_name: Full name
    - workspace_name: Name of workspace user will join
    - invited_at: When invitation was sent (UTC)
    - expires_at: When invitation expires (UTC)

    Use Cases:
    - Monitor pending onboarding
    - Identify expired invitations for cleanup
    - Follow up with therapists who haven't accepted

    Error Responses:
    - 401: Not authenticated
    - 403: Not platform admin
    """,
)
async def get_pending_invitations(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_platform_admin)],
) -> PendingInvitationsResponse:
    """
    List all pending therapist invitations.

    Returns users who have been invited but have not yet accepted
    (is_active=False and invitation_token_hash is not None).

    Args:
        db: Database session (injected)
        admin: Authenticated platform admin (injected)

    Returns:
        PendingInvitationsResponse with list of pending invitations
    """
    # Query for inactive users with pending invitations
    # Join with workspace to get workspace name
    from pazpaz.models.workspace import Workspace

    query = (
        select(User, Workspace)
        .join(Workspace, User.workspace_id == Workspace.id)
        .where(
            User.is_active == False,  # noqa: E712 - SQLAlchemy requires == for boolean
            User.invitation_token_hash.is_not(None),
            User.invited_at.is_not(None),
        )
        .order_by(User.invited_at.desc())  # Newest first
    )

    result = await db.execute(query)
    rows = result.all()

    # Build response
    invitations = []
    for user, workspace in rows:
        # Calculate expiration date (7 days from invited_at)
        expires_at = user.invited_at + timedelta(days=7)

        invitations.append(
            PendingInvitation(
                user_id=user.id,
                email=user.email,
                full_name=user.full_name,
                workspace_name=workspace.name,
                invited_at=user.invited_at,
                expires_at=expires_at,
            )
        )

    logger.info(
        "pending_invitations_listed",
        admin_id=str(admin.id),
        count=len(invitations),
    )

    return PendingInvitationsResponse(invitations=invitations)


# ============================================================================
# New Platform Admin Endpoints
# ============================================================================


# Metrics schemas
class PlatformMetrics(BaseModel):
    """Platform-wide metrics.

    Example:
        ```json
        {
            "total_workspaces": 24,
            "active_users": 23,
            "pending_invitations": 3,
            "blacklisted_users": 2
        }
        ```
    """

    total_workspaces: int = Field(..., description="Total number of workspaces")
    active_users: int = Field(..., description="Total number of active users")
    pending_invitations: int = Field(
        ..., description="Number of pending invitations (not yet accepted)"
    )
    blacklisted_users: int = Field(
        ..., description="Number of blacklisted email addresses"
    )


# Activity schemas
class Activity(BaseModel):
    """Single activity event.

    Example:
        ```json
        {
            "type": "workspace.created",
            "timestamp": "2025-10-22T10:30:00Z",
            "description": "New workspace created: Sarah's Massage Therapy",
            "metadata": {"workspace_id": "123e4567-...", "user_id": "987e6543-..."}
        }
        ```
    """

    type: str = Field(..., description="Activity type (e.g., workspace.created)")
    timestamp: datetime = Field(..., description="When activity occurred (UTC)")
    description: str = Field(..., description="Human-readable activity description")
    metadata: dict | None = Field(
        default=None, description="Additional activity context"
    )


class ActivityResponse(BaseModel):
    """Response schema for activity timeline.

    Example:
        ```json
        {
            "activities": [
                {
                    "type": "workspace.created",
                    "timestamp": "2025-10-22T10:30:00Z",
                    "description": "New workspace created",
                    "metadata": {}
                }
            ]
        }
        ```
    """

    activities: list[Activity] = Field(
        default_factory=list, description="Recent platform activities"
    )


# Workspace management schemas
class WorkspaceInfo(BaseModel):
    """Workspace information for platform admin.

    Example:
        ```json
        {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "name": "Sarah's Massage Therapy",
            "owner_email": "sarah@example.com",
            "status": "active",
            "created_at": "2025-10-01T00:00:00Z",
            "user_count": 1,
            "session_count": 12
        }
        ```
    """

    id: uuid.UUID = Field(..., description="Workspace UUID")
    name: str = Field(..., description="Workspace name")
    owner_email: str = Field(..., description="Workspace owner email")
    status: str = Field(
        ..., description="Workspace status (active, suspended, deleted)"
    )
    created_at: datetime = Field(..., description="When workspace was created (UTC)")
    user_count: int = Field(..., description="Number of users in workspace")
    session_count: int = Field(..., description="Number of sessions in workspace")


class WorkspacesResponse(BaseModel):
    """Response schema for workspaces list.

    Example:
        ```json
        {
            "workspaces": [
                {
                    "id": "123e4567-...",
                    "name": "Sarah's Massage Therapy",
                    "owner_email": "sarah@example.com",
                    "status": "active",
                    "created_at": "2025-10-01T00:00:00Z",
                    "user_count": 1,
                    "session_count": 12
                }
            ]
        }
        ```
    """

    workspaces: list[WorkspaceInfo] = Field(
        default_factory=list, description="List of workspaces"
    )


class SuspendWorkspaceRequest(BaseModel):
    """Request schema for suspending workspace.

    Example:
        ```json
        {
            "reason": "Terms of service violation"
        }
        ```
    """

    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Reason for suspension (required for audit)",
    )


class WorkspaceActionResponse(BaseModel):
    """Response schema for workspace actions.

    Example:
        ```json
        {
            "message": "Workspace suspended successfully",
            "workspace_id": "123e4567-...",
            "status": "suspended"
        }
        ```
    """

    message: str = Field(..., description="Action result message")
    workspace_id: uuid.UUID = Field(..., description="Workspace UUID")
    status: str = Field(..., description="New workspace status")


class DeleteWorkspaceRequest(BaseModel):
    """Request schema for deleting workspace.

    Example:
        ```json
        {
            "reason": "User requested account deletion"
        }
        ```
    """

    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Reason for deletion (required for audit)",
    )


# Blacklist schemas
class BlacklistEntry(BaseModel):
    """Single blacklist entry.

    Example:
        ```json
        {
            "email": "blocked@example.com",
            "reason": "Spam account",
            "added_at": "2025-10-22T10:30:00Z",
            "added_by": "admin@example.com"
        }
        ```
    """

    email: str = Field(..., description="Blacklisted email address")
    reason: str = Field(..., description="Reason for blacklisting")
    added_at: datetime = Field(..., description="When email was blacklisted (UTC)")
    added_by: str | None = Field(
        default=None, description="Email of admin who added entry"
    )


class BlacklistResponse(BaseModel):
    """Response schema for blacklist.

    Example:
        ```json
        {
            "blacklist": [
                {
                    "email": "blocked@example.com",
                    "reason": "Spam account",
                    "added_at": "2025-10-22T10:30:00Z",
                    "added_by": "admin@example.com"
                }
            ]
        }
        ```
    """

    blacklist: list[BlacklistEntry] = Field(
        default_factory=list, description="Blacklisted emails"
    )


class AddToBlacklistRequest(BaseModel):
    """Request schema for adding email to blacklist.

    Example:
        ```json
        {
            "email": "spam@example.com",
            "reason": "Repeated spam signups"
        }
        ```
    """

    email: EmailStr = Field(..., description="Email address to blacklist")
    reason: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Reason for blacklisting (required for audit)",
    )


class BlacklistActionResponse(BaseModel):
    """Response schema for blacklist actions.

    Example:
        ```json
        {
            "message": "Email added to blacklist",
            "email": "spam@example.com"
        }
        ```
    """

    message: str = Field(..., description="Action result message")
    email: str = Field(..., description="Affected email address")


# ============================================================================
# New Endpoints
# ============================================================================


@router.get(
    "/metrics",
    response_model=PlatformMetrics,
    summary="Get platform metrics",
    description="""
    Get platform-wide metrics for dashboard.

    Returns:
    - total_workspaces: Count of all workspaces (excluding deleted)
    - active_users: Count of active users across all workspaces
    - pending_invitations: Count of users with pending invitations
    - blacklisted_users: Count of blacklisted email addresses

    Security:
    - Requires platform admin authentication
    - Cross-workspace access allowed for metrics

    Error Responses:
    - 401: Not authenticated
    - 403: Not platform admin
    """,
)
async def get_metrics(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_platform_admin)],
) -> PlatformMetrics:
    """
    Get platform-wide metrics.

    Counts workspaces, active users, pending invitations, and blacklisted emails.

    Args:
        db: Database session (injected)
        admin: Authenticated platform admin (injected)

    Returns:
        PlatformMetrics with current counts
    """
    # Count workspaces (excluding deleted)
    workspace_count = await db.scalar(
        select(func.count(Workspace.id)).where(
            Workspace.status != WorkspaceStatus.DELETED
        )
    )

    # Count active users
    active_user_count = await db.scalar(
        select(func.count(User.id)).where(User.is_active == True)  # noqa: E712
    )

    # Count pending invitations (inactive users with invitation token)
    pending_invitation_count = await db.scalar(
        select(func.count(User.id)).where(
            and_(
                User.is_active == False,  # noqa: E712
                User.invitation_token_hash.is_not(None),
            )
        )
    )

    # Count blacklisted emails
    blacklist_count = await db.scalar(select(func.count(EmailBlacklist.id)))

    logger.info(
        "platform_metrics_retrieved",
        admin_id=str(admin.id),
        workspaces=workspace_count or 0,
        active_users=active_user_count or 0,
        pending_invitations=pending_invitation_count or 0,
        blacklisted=blacklist_count or 0,
    )

    return PlatformMetrics(
        total_workspaces=workspace_count or 0,
        active_users=active_user_count or 0,
        pending_invitations=pending_invitation_count or 0,
        blacklisted_users=blacklist_count or 0,
    )


@router.get(
    "/activity",
    response_model=ActivityResponse,
    summary="Get recent platform activity",
    description="""
    Get recent platform activity from audit events.

    Query Parameters:
    - limit: Number of activities to return (default 50, max 100)

    Returns recent audit events related to:
    - Workspace creation/suspension/deletion
    - User invitations accepted
    - Blacklist changes

    Security:
    - Requires platform admin authentication
    - Cross-workspace access allowed for activity feed

    Error Responses:
    - 401: Not authenticated
    - 403: Not platform admin
    - 422: Invalid limit parameter
    """,
)
async def get_activity(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_platform_admin)],
    limit: int = Query(default=50, ge=1, le=100, description="Number of activities"),
) -> ActivityResponse:
    """
    Get recent platform activity.

    Fetches recent audit events and formats them as activity feed.

    Args:
        db: Database session (injected)
        admin: Authenticated platform admin (injected)
        limit: Number of activities to return (1-100)

    Returns:
        ActivityResponse with recent activities
    """
    # Query recent audit events related to platform admin actions
    query = (
        select(AuditEvent)
        .where(
            AuditEvent.resource_type.in_(
                [
                    ResourceType.WORKSPACE,
                    ResourceType.USER,
                ]
            )
        )
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    audit_events = result.scalars().all()

    # Convert audit events to activities
    activities = []
    for event in audit_events:
        # Determine activity type and description
        resource_type = (
            event.resource_type
            if isinstance(event.resource_type, str)
            else event.resource_type.value
            if event.resource_type
            else "unknown"
        )
        action = (
            event.action.value if hasattr(event.action, "value") else str(event.action)
        )
        activity_type = f"{resource_type}.{action.lower()}"
        description = _format_activity_description(event)

        activities.append(
            Activity(
                type=activity_type,
                timestamp=event.created_at,
                description=description,
                metadata=event.event_metadata or {},
            )
        )

    logger.info(
        "platform_activity_retrieved",
        admin_id=str(admin.id),
        count=len(activities),
        limit=limit,
    )

    return ActivityResponse(activities=activities)


def _format_activity_description(event: AuditEvent) -> str:
    """Format audit event as human-readable activity description."""
    action = event.action.value if hasattr(event.action, "value") else str(event.action)
    resource = (
        event.resource_type
        if isinstance(event.resource_type, str)
        else event.resource_type.value
        if event.resource_type
        else "unknown"
    )

    metadata = event.event_metadata or {}

    if resource == "workspace":
        if action == "CREATE":
            workspace_name = metadata.get("workspace_name", "Unknown")
            return f"New workspace created: {workspace_name}"
        elif action == "UPDATE":
            if "status" in metadata.get("changed_fields", []):
                status = metadata.get("new_status", "unknown")
                workspace_name = metadata.get("workspace_name", "Unknown")
                return f"Workspace {status}: {workspace_name}"
            return "Workspace updated"
        elif action == "DELETE":
            return f"Workspace deleted: {metadata.get('workspace_name', 'Unknown')}"
    elif resource == "user":
        if action == "CREATE":
            return f"User invited: {metadata.get('email', 'Unknown')}"
        elif action == "UPDATE":
            if metadata.get("is_active"):
                return f"Invitation accepted: {metadata.get('email', 'Unknown')}"
            return "User updated"

    return f"{resource} {action.lower()}"


@router.get(
    "/workspaces",
    response_model=WorkspacesResponse,
    summary="List all workspaces",
    description="""
    List all workspaces with stats.

    Query Parameters:
    - search: Optional search query (filters by workspace name or owner email)

    Returns workspace information including:
    - Workspace details (id, name, status)
    - Owner email
    - User count
    - Session count
    - Created date

    Security:
    - Requires platform admin authentication
    - Cross-workspace access allowed

    Error Responses:
    - 401: Not authenticated
    - 403: Not platform admin
    """,
)
async def list_workspaces(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_platform_admin)],
    search: str | None = Query(
        default=None, description="Search workspace name or owner email"
    ),
) -> WorkspacesResponse:
    """
    List all workspaces.

    Args:
        db: Database session (injected)
        admin: Authenticated platform admin (injected)
        search: Optional search query

    Returns:
        WorkspacesResponse with list of workspaces
    """
    from sqlalchemy.orm import selectinload

    from pazpaz.models.session import Session

    # Build base query with owner (first user in workspace)
    query = select(Workspace).where(Workspace.status != WorkspaceStatus.DELETED)

    # Apply search filter if provided
    if search:
        # Left join with users to search by owner email
        # (LEFT JOIN so workspaces without users are included)
        query = (
            query.outerjoin(User, Workspace.id == User.workspace_id)
            .where(
                or_(
                    Workspace.name.ilike(f"%{search}%"),
                    User.email.ilike(f"%{search}%"),
                )
            )
            .distinct()
        )

    # Load workspaces
    result = await db.execute(query.options(selectinload(Workspace.users)))
    workspaces = result.scalars().all()

    # Build response with counts
    workspace_list = []
    for workspace in workspaces:
        # Get owner:
        # - If searching by email, prefer the matching user
        # - Otherwise, prefer the first active user
        owner = None
        if search and "@" in search:
            # Searching by email - prefer matching user
            owner = next(
                (u for u in workspace.users if u.email.lower() == search.lower()), None
            )
        if not owner:
            # Fall back to first active user
            owner = next(
                (u for u in workspace.users if u.is_active),
                workspace.users[0] if workspace.users else None,
            )

        # Count users
        user_count = len(workspace.users)

        # Count sessions
        session_count = await db.scalar(
            select(func.count(Session.id)).where(Session.workspace_id == workspace.id)
        )

        workspace_list.append(
            WorkspaceInfo(
                id=workspace.id,
                name=workspace.name,
                owner_email=owner.email if owner else "No owner",
                status=workspace.status.value,
                created_at=workspace.created_at,
                user_count=user_count,
                session_count=session_count or 0,
            )
        )

    logger.info(
        "workspaces_listed",
        admin_id=str(admin.id),
        count=len(workspace_list),
        search=search,
    )

    return WorkspacesResponse(workspaces=workspace_list)


@router.get(
    "/workspaces/{workspace_id}",
    response_model=WorkspaceInfo,
    summary="Get workspace details",
    description="""
    Get detailed information about a specific workspace.

    Returns workspace information including:
    - Workspace details (id, name, status)
    - Owner email
    - User count
    - Session count
    - Created date

    Security:
    - Requires platform admin authentication
    - Cross-workspace access allowed

    Error Responses:
    - 401: Not authenticated
    - 403: Not platform admin
    - 404: Workspace not found
    """,
)
async def get_workspace_details(
    workspace_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_platform_admin)],
) -> WorkspaceInfo:
    """
    Get detailed information about a specific workspace.

    Args:
        workspace_id: Workspace UUID
        db: Database session (injected)
        admin: Authenticated platform admin (injected)

    Returns:
        WorkspaceInfo with workspace details

    Raises:
        HTTPException: 404 if workspace not found
    """
    from sqlalchemy.orm import selectinload

    from pazpaz.models.session import Session

    # Get workspace with users
    query = (
        select(Workspace)
        .where(Workspace.id == workspace_id)
        .options(selectinload(Workspace.users))
    )

    result = await db.execute(query)
    workspace = result.scalar_one_or_none()

    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    # Get owner (first active user, or any user if no active users)
    owner = next(
        (u for u in workspace.users if u.is_active),
        workspace.users[0] if workspace.users else None,
    )

    # Count users
    user_count = len(workspace.users)

    # Count sessions
    session_count = await db.scalar(
        select(func.count(Session.id)).where(Session.workspace_id == workspace.id)
    )

    logger.info(
        "workspace_details_retrieved",
        admin_id=str(admin.id),
        workspace_id=str(workspace.id),
    )

    return WorkspaceInfo(
        id=workspace.id,
        name=workspace.name,
        owner_email=owner.email if owner else "No owner",
        status=workspace.status.value,
        created_at=workspace.created_at,
        user_count=user_count,
        session_count=session_count or 0,
    )


@router.post(
    "/workspaces/{workspace_id}/suspend",
    response_model=WorkspaceActionResponse,
    summary="Suspend workspace",
    description="""
    Suspend a workspace.

    Actions performed:
    - Set workspace status to 'suspended'
    - Create audit event with reason
    - Log suspension

    Note: This does NOT invalidate user sessions. Users will be blocked
    on next request when workspace status is checked.

    Security:
    - Requires platform admin authentication
    - Creates audit trail

    Error Responses:
    - 400: Workspace already suspended or deleted
    - 401: Not authenticated
    - 403: Not platform admin
    - 404: Workspace not found
    """,
)
async def suspend_workspace(
    workspace_id: uuid.UUID,
    request_data: SuspendWorkspaceRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_platform_admin)],
) -> WorkspaceActionResponse:
    """
    Suspend a workspace.

    Args:
        workspace_id: Workspace UUID
        request_data: Suspension details (reason)
        db: Database session (injected)
        admin: Authenticated platform admin (injected)

    Returns:
        WorkspaceActionResponse with result

    Raises:
        HTTPException: 404 if workspace not found, 400 if already suspended
    """
    # Get workspace
    workspace = await db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    # Check if already suspended or deleted
    if workspace.status == WorkspaceStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workspace is already suspended",
        )
    if workspace.status == WorkspaceStatus.DELETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot suspend deleted workspace",
        )

    # Suspend workspace
    workspace.status = WorkspaceStatus.SUSPENDED

    # Create audit event
    audit_event = AuditEvent(
        workspace_id=workspace.id,
        user_id=admin.id,
        event_type="workspace.suspended",
        action=AuditAction.UPDATE,
        resource_type=ResourceType.WORKSPACE,
        resource_id=str(workspace.id),
        event_metadata={
            "reason": request_data.reason,
            "workspace_name": workspace.name,
            "admin_email": admin.email,
            "changed_fields": ["status"],
            "new_status": "suspended",
        },
    )
    db.add(audit_event)

    await db.commit()

    logger.warning(
        "workspace_suspended",
        admin_id=str(admin.id),
        workspace_id=str(workspace.id),
        reason=request_data.reason,
    )

    return WorkspaceActionResponse(
        message="Workspace suspended successfully",
        workspace_id=workspace.id,
        status=workspace.status.value,
    )


@router.post(
    "/workspaces/{workspace_id}/reactivate",
    response_model=WorkspaceActionResponse,
    summary="Reactivate suspended workspace",
    description="""
    Reactivate a suspended workspace.

    Actions performed:
    - Set workspace status to 'active'
    - Create audit event
    - Log reactivation

    Security:
    - Requires platform admin authentication
    - Creates audit trail

    Error Responses:
    - 400: Workspace not suspended (already active or deleted)
    - 401: Not authenticated
    - 403: Not platform admin
    - 404: Workspace not found
    """,
)
async def reactivate_workspace(
    workspace_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_platform_admin)],
) -> WorkspaceActionResponse:
    """
    Reactivate a suspended workspace.

    Args:
        workspace_id: Workspace UUID
        db: Database session (injected)
        admin: Authenticated platform admin (injected)

    Returns:
        WorkspaceActionResponse with result

    Raises:
        HTTPException: 404 if workspace not found, 400 if not suspended
    """
    # Get workspace
    workspace = await db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    # Check if suspended
    if workspace.status != WorkspaceStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only suspended workspaces can be reactivated",
        )

    # Reactivate workspace
    workspace.status = WorkspaceStatus.ACTIVE

    # Create audit event
    audit_event = AuditEvent(
        workspace_id=workspace.id,
        user_id=admin.id,
        event_type="workspace.reactivated",
        action=AuditAction.UPDATE,
        resource_type=ResourceType.WORKSPACE,
        resource_id=str(workspace.id),
        event_metadata={
            "workspace_name": workspace.name,
            "admin_email": admin.email,
            "changed_fields": ["status"],
            "new_status": "active",
        },
    )
    db.add(audit_event)

    await db.commit()

    logger.info(
        "workspace_reactivated",
        admin_id=str(admin.id),
        workspace_id=str(workspace.id),
    )

    return WorkspaceActionResponse(
        message="Workspace reactivated successfully",
        workspace_id=workspace.id,
        status=workspace.status.value,
    )


@router.delete(
    "/workspaces/{workspace_id}",
    response_model=WorkspaceActionResponse,
    summary="Delete workspace (soft delete)",
    description="""
    Soft delete a workspace.

    Actions performed:
    - Set workspace status to 'deleted'
    - Set deleted_at timestamp
    - Set all users to inactive
    - Create audit event with reason

    Note: This is a SOFT DELETE. Data is preserved for audit trail.
    Hard deletion (if needed) must be done manually in database.

    Security:
    - Requires platform admin authentication
    - Creates audit trail
    - Preserves data for compliance

    Error Responses:
    - 400: Workspace already deleted
    - 401: Not authenticated
    - 403: Not platform admin
    - 404: Workspace not found
    """,
)
async def delete_workspace(
    workspace_id: uuid.UUID,
    request_data: DeleteWorkspaceRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_platform_admin)],
) -> WorkspaceActionResponse:
    """
    Soft delete a workspace.

    Args:
        workspace_id: Workspace UUID
        request_data: Deletion details (reason)
        db: Database session (injected)
        admin: Authenticated platform admin (injected)

    Returns:
        WorkspaceActionResponse with result

    Raises:
        HTTPException: 404 if workspace not found, 400 if already deleted
    """
    # Get workspace
    workspace = await db.get(Workspace, workspace_id)
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )

    # Check if already deleted
    if workspace.status == WorkspaceStatus.DELETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workspace is already deleted",
        )

    # Soft delete workspace
    workspace.status = WorkspaceStatus.DELETED
    workspace.deleted_at = datetime.now(UTC)

    # Deactivate all users in workspace
    result = await db.execute(
        select(User).where(User.workspace_id == workspace.id, User.is_active == True)  # noqa: E712
    )
    users = result.scalars().all()
    for user in users:
        user.is_active = False

    # Create audit event
    audit_event = AuditEvent(
        workspace_id=workspace.id,
        user_id=admin.id,
        event_type="workspace.deleted",
        action=AuditAction.DELETE,
        resource_type=ResourceType.WORKSPACE,
        resource_id=str(workspace.id),
        event_metadata={
            "reason": request_data.reason,
            "workspace_name": workspace.name,
            "admin_email": admin.email,
            "user_count": len(users),
            "changed_fields": ["status", "deleted_at"],
            "new_status": "deleted",
        },
    )
    db.add(audit_event)

    await db.commit()

    logger.warning(
        "workspace_deleted",
        admin_id=str(admin.id),
        workspace_id=str(workspace.id),
        reason=request_data.reason,
        user_count=len(users),
    )

    return WorkspaceActionResponse(
        message="Workspace deleted successfully (soft delete)",
        workspace_id=workspace.id,
        status=workspace.status.value,
    )


@router.get(
    "/blacklist",
    response_model=BlacklistResponse,
    summary="List blacklisted emails",
    description="""
    Get list of all blacklisted email addresses.

    Returns:
    - email: Blacklisted email address
    - reason: Why it was blacklisted
    - added_at: When it was blacklisted
    - added_by: Admin who added it

    Security:
    - Requires platform admin authentication

    Error Responses:
    - 401: Not authenticated
    - 403: Not platform admin
    """,
)
async def get_blacklist(
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_platform_admin)],
) -> BlacklistResponse:
    """
    Get all blacklisted emails.

    Args:
        db: Database session (injected)
        admin: Authenticated platform admin (injected)

    Returns:
        BlacklistResponse with blacklist entries
    """
    from sqlalchemy.orm import selectinload

    # Query blacklist with admin user
    query = (
        select(EmailBlacklist)
        .options(selectinload(EmailBlacklist.added_by_user))
        .order_by(EmailBlacklist.added_at.desc())
    )

    result = await db.execute(query)
    entries = result.scalars().all()

    # Build response
    blacklist = []
    for entry in entries:
        blacklist.append(
            BlacklistEntry(
                email=entry.email,
                reason=entry.reason,
                added_at=entry.added_at,
                added_by=entry.added_by_user.email if entry.added_by_user else None,
            )
        )

    logger.info(
        "blacklist_retrieved",
        admin_id=str(admin.id),
        count=len(blacklist),
    )

    return BlacklistResponse(blacklist=blacklist)


@router.post(
    "/blacklist",
    response_model=BlacklistActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add email to blacklist",
    description="""
    Add an email address to the blacklist.

    Actions performed:
    - Add email to blacklist table
    - Create audit event
    - Revoke any pending invitations for this email

    Security:
    - Requires platform admin authentication
    - Email is normalized to lowercase
    - Duplicate check performed

    Error Responses:
    - 400: Email already blacklisted
    - 401: Not authenticated
    - 403: Not platform admin
    - 422: Invalid email format
    """,
)
async def add_to_blacklist(
    request_data: AddToBlacklistRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_platform_admin)],
) -> BlacklistActionResponse:
    """
    Add email to blacklist.

    Args:
        request_data: Email and reason
        db: Database session (injected)
        admin: Authenticated platform admin (injected)

    Returns:
        BlacklistActionResponse with result

    Raises:
        HTTPException: 400 if email already blacklisted
    """
    # Normalize email: strip whitespace + lowercase
    email = request_data.email.strip().lower()

    # Check if already blacklisted
    existing = await db.scalar(
        select(EmailBlacklist).where(EmailBlacklist.email == email)
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already blacklisted",
        )

    # Add to blacklist
    entry = EmailBlacklist(
        email=email,
        reason=request_data.reason,
        added_by=admin.id,
    )
    db.add(entry)

    # Revoke pending invitations for this email
    result = await db.execute(
        select(User).where(
            User.email == email,
            User.is_active == False,  # noqa: E712
            User.invitation_token_hash.is_not(None),
        )
    )
    pending_users = result.scalars().all()
    for user in pending_users:
        user.invitation_token_hash = None

    # Create audit event
    audit_event = AuditEvent(
        workspace_id=admin.workspace_id,
        user_id=admin.id,
        event_type="email.blacklisted",
        action=AuditAction.CREATE,
        resource_type=ResourceType.USER,
        resource_id=str(entry.id),
        event_metadata={
            "email": email,
            "reason": request_data.reason,
            "admin_email": admin.email,
            "revoked_invitations": len(pending_users),
        },
    )
    db.add(audit_event)

    await db.commit()

    logger.warning(
        "email_blacklisted",
        admin_id=str(admin.id),
        email=email,
        reason=request_data.reason,
        revoked_invitations=len(pending_users),
    )

    return BlacklistActionResponse(
        message=f"Email '{email}' added to blacklist",
        email=email,
    )


@router.delete(
    "/blacklist/{email}",
    response_model=BlacklistActionResponse,
    summary="Remove email from blacklist",
    description="""
    Remove an email address from the blacklist.

    Actions performed:
    - Remove email from blacklist table
    - Create audit event

    Security:
    - Requires platform admin authentication

    Error Responses:
    - 401: Not authenticated
    - 403: Not platform admin
    - 404: Email not found in blacklist
    """,
)
async def remove_from_blacklist(
    email: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_platform_admin)],
) -> BlacklistActionResponse:
    """
    Remove email from blacklist.

    Args:
        email: Email address to remove
        db: Database session (injected)
        admin: Authenticated platform admin (injected)

    Returns:
        BlacklistActionResponse with result

    Raises:
        HTTPException: 404 if email not in blacklist
    """
    # Normalize email: strip whitespace + lowercase
    email = email.strip().lower()

    # Find entry
    entry = await db.scalar(select(EmailBlacklist).where(EmailBlacklist.email == email))
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email not found in blacklist",
        )

    # Remove from blacklist
    await db.delete(entry)

    # Create audit event
    audit_event = AuditEvent(
        workspace_id=admin.workspace_id,
        user_id=admin.id,
        event_type="email.unblacklisted",
        action=AuditAction.DELETE,
        resource_type=ResourceType.USER,
        resource_id=str(entry.id),
        event_metadata={
            "email": email,
            "admin_email": admin.email,
        },
    )
    db.add(audit_event)

    await db.commit()

    logger.info(
        "email_unblacklisted",
        admin_id=str(admin.id),
        email=email,
    )

    return BlacklistActionResponse(
        message=f"Email '{email}' removed from blacklist",
        email=email,
    )
