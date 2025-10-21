"""Platform admin API endpoints for therapist onboarding."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.api.dependencies.platform_admin import require_platform_admin
from pazpaz.core.logging import get_logger
from pazpaz.db.base import get_db
from pazpaz.models.user import User
from pazpaz.services.platform_onboarding_service import (
    DuplicateEmailError,
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

        # Generate invitation URL
        # In production, this would be the frontend URL
        invitation_url = f"https://app.pazpaz.com/accept-invitation?token={token}"

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

        # Generate invitation URL
        invitation_url = f"https://app.pazpaz.com/accept-invitation?token={token}"

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
