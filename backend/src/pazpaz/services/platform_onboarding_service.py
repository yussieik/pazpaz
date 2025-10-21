"""Platform onboarding service for therapist invitations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.core.invitation_tokens import (
    generate_invitation_token,
    is_invitation_expired,
    verify_invitation_token,
)
from pazpaz.core.logging import get_logger
from pazpaz.models.user import User, UserRole
from pazpaz.models.workspace import Workspace

logger = get_logger(__name__)


# Custom Exceptions
class InvalidInvitationTokenError(Exception):
    """Raised when invitation token is invalid or does not match stored hash."""

    pass


class ExpiredInvitationTokenError(Exception):
    """Raised when invitation token has expired (older than 7 days)."""

    pass


class InvitationAlreadyAcceptedError(Exception):
    """Raised when attempting to accept an invitation that was already accepted."""

    pass


class InvitationNotFoundError(Exception):
    """Raised when invitation cannot be found for the given user."""

    pass


class UserAlreadyActiveError(Exception):
    """Raised when attempting to resend invitation to an already active user."""

    pass


class DuplicateEmailError(Exception):
    """Raised when attempting to create user with email that already exists."""

    pass


class PlatformOnboardingService:
    """
    Service for platform admin to onboard therapists.

    This service handles the complete onboarding flow:
    1. Platform admin creates workspace + therapist account
    2. Generates invitation token (sent via email)
    3. Therapist accepts invitation to activate account
    4. Optional: Resend invitation if not accepted

    Security features:
    - SHA256 hash storage (never plaintext tokens)
    - 7-day expiration on invitations
    - Single-use tokens (deleted after acceptance)
    - Transaction-safe operations
    - Timezone-aware datetimes (UTC)
    """

    async def create_workspace_and_invite_therapist(
        self,
        db: AsyncSession,
        workspace_name: str,
        therapist_email: str,
        therapist_full_name: str,
    ) -> tuple[Workspace, User, str]:
        """
        Create workspace and invite therapist.

        This is the primary method for platform admin to onboard new therapists.
        It creates a new workspace, creates an owner user for that workspace,
        and generates an invitation token that must be sent via email.

        Flow:
        1. Validate inputs (workspace name, email, full name)
        2. Check for duplicate email
        3. Create workspace
        4. Generate invitation token
        5. Create user with invitation metadata
        6. Commit transaction
        7. Return workspace, user, and token (for email sending)

        Args:
            db: Database session (async)
            workspace_name: Name of the workspace (e.g., "Sarah's Massage Therapy")
            therapist_email: Email address of the therapist (must be unique)
            therapist_full_name: Full name of the therapist (e.g., "Sarah Chen")

        Returns:
            Tuple of (workspace, user, invitation_token):
            - workspace: Created Workspace instance
            - user: Created User instance (inactive, pending invitation acceptance)
            - invitation_token: Token to send in email magic link (256-bit)

        Raises:
            DuplicateEmailError: If email already exists in database
            ValueError: If inputs are invalid (empty strings)

        Example:
            ```python
            service = PlatformOnboardingService()
            (
                workspace,
                user,
                token,
            ) = await service.create_workspace_and_invite_therapist(
                db=db,
                workspace_name="Downtown Wellness",
                therapist_email="dr.smith@example.com",
                therapist_full_name="Dr. Jane Smith",
            )

            # Send token via email (not handled by this service)
            await send_invitation_email(user.email, token)
            ```

        Security:
        - Token hash stored in database (SHA256)
        - User created as inactive (is_active=False)
        - User activated only after accepting invitation
        - Transaction ensures atomicity (workspace + user created together)
        """
        # Validate inputs
        if not workspace_name or not workspace_name.strip():
            raise ValueError("workspace_name cannot be empty")
        if not therapist_email or not therapist_email.strip():
            raise ValueError("therapist_email cannot be empty")
        if not therapist_full_name or not therapist_full_name.strip():
            raise ValueError("therapist_full_name cannot be empty")

        try:
            # Check if email already exists
            query = select(User).where(User.email == therapist_email)
            result = await db.execute(query)
            existing_user = result.scalar_one_or_none()

            if existing_user:
                raise DuplicateEmailError(
                    f"User with email {therapist_email} already exists"
                )

            # Create workspace
            workspace = Workspace(
                id=uuid.uuid4(),
                name=workspace_name.strip(),
            )
            db.add(workspace)

            # Generate invitation token
            token, token_hash = generate_invitation_token()

            # Create therapist user (inactive, pending invitation acceptance)
            user = User(
                id=uuid.uuid4(),
                workspace_id=workspace.id,
                email=therapist_email.strip(),
                full_name=therapist_full_name.strip(),
                role=UserRole.OWNER,
                is_active=False,  # Activated when they accept invitation
                is_platform_admin=False,
                invitation_token_hash=token_hash,
                invited_by_platform_admin=True,
                invited_at=datetime.now(UTC),
            )
            db.add(user)

            # Commit transaction
            await db.commit()
            await db.refresh(workspace)
            await db.refresh(user)

            logger.info(
                "workspace_and_therapist_created",
                workspace_id=str(workspace.id),
                user_id=str(user.id),
                email=therapist_email,
            )

            return workspace, user, token

        except DuplicateEmailError:
            await db.rollback()
            raise
        except ValueError:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(
                "create_workspace_and_invite_therapist_failed",
                workspace_name=workspace_name,
                email=therapist_email,
                error=str(e),
                exc_info=True,
            )
            raise

    async def accept_invitation(
        self,
        db: AsyncSession,
        token: str,
    ) -> User:
        """
        Accept therapist invitation and activate account.

        Verifies the invitation token, checks expiration, and activates the user
        account. This is called when the therapist clicks the magic link in their
        invitation email.

        Flow:
        1. Verify token matches stored hash
        2. Find user by token hash
        3. Check if invitation already accepted
        4. Check if invitation expired
        5. Activate user (is_active=True)
        6. Clear invitation token (single-use)
        7. Commit transaction
        8. Return activated user

        Args:
            db: Database session (async)
            token: Invitation token from email magic link

        Returns:
            Activated User instance

        Raises:
            InvalidInvitationTokenError: If token is invalid or does not match
            ExpiredInvitationTokenError: If token has expired (>7 days old)
            InvitationAlreadyAcceptedError: If user is already active

        Example:
            ```python
            service = PlatformOnboardingService()
            try:
                user = await service.accept_invitation(db, token)
                # Generate JWT and log user in
                jwt_token = create_access_token(user.id, user.workspace_id)
            except ExpiredInvitationTokenError:
                # Show error: invitation expired
                pass
            ```

        Security:
        - Token verification uses timing-safe comparison
        - Token is single-use (deleted after acceptance)
        - Validates user exists and invitation not already accepted
        - Checks expiration (7-day window)
        - Transaction ensures atomicity
        """
        try:
            # Find user by token hash
            # We need to hash the provided token to compare with stored hash

            # We can't use verify_invitation_token directly here because we need to
            # query the database first. Instead, we'll hash the token and query.
            import hashlib

            token_hash = hashlib.sha256(token.encode()).hexdigest()

            query = select(User).where(User.invitation_token_hash == token_hash)
            result = await db.execute(query)
            user = result.scalar_one_or_none()

            if not user:
                raise InvalidInvitationTokenError("Invalid invitation token")

            # Verify token matches (timing-safe comparison)
            if not verify_invitation_token(token, user.invitation_token_hash):
                raise InvalidInvitationTokenError("Invalid invitation token")

            # Check if already accepted
            if user.is_active:
                raise InvitationAlreadyAcceptedError(
                    "Invitation has already been accepted"
                )

            # Check if expired
            if user.invited_at and is_invitation_expired(user.invited_at):
                raise ExpiredInvitationTokenError("Invitation has expired")

            # Activate user and clear token (single-use)
            user.is_active = True
            user.invitation_token_hash = None

            await db.commit()
            await db.refresh(user)

            logger.info(
                "invitation_accepted",
                user_id=str(user.id),
                workspace_id=str(user.workspace_id),
                email=user.email,
            )

            return user

        except (
            InvalidInvitationTokenError,
            ExpiredInvitationTokenError,
            InvitationAlreadyAcceptedError,
        ):
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(
                "accept_invitation_failed",
                error=str(e),
                exc_info=True,
            )
            raise

    async def resend_invitation(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> str:
        """
        Resend invitation to therapist (generate new token).

        Generates a new invitation token for a user who has not yet accepted
        their invitation. This is useful if the original invitation expired
        or was lost.

        Flow:
        1. Get user by ID
        2. Validate user exists and is not already active
        3. Generate new invitation token
        4. Update user with new token hash and timestamp
        5. Commit transaction
        6. Return new token (for email sending)

        Args:
            db: Database session (async)
            user_id: UUID of the user to resend invitation to

        Returns:
            New invitation token (256-bit, URL-safe)

        Raises:
            InvitationNotFoundError: If user does not exist
            UserAlreadyActiveError: If user is already active

        Example:
            ```python
            service = PlatformOnboardingService()
            try:
                new_token = await service.resend_invitation(db, user_id)
                # Send new token via email
                await send_invitation_email(user.email, new_token)
            except UserAlreadyActiveError:
                # Show error: user already active
                pass
            ```

        Security:
        - New token hash replaces old one (old token invalidated)
        - Updated invited_at timestamp resets expiration window
        - Only works for inactive users
        - Transaction ensures atomicity
        """
        try:
            # Get user
            user = await db.get(User, user_id)

            if not user:
                raise InvitationNotFoundError(f"User {user_id} not found")

            if user.is_active:
                raise UserAlreadyActiveError(
                    f"User {user_id} is already active, cannot resend invitation"
                )

            # Generate new token
            token, token_hash = generate_invitation_token()

            # Update user
            user.invitation_token_hash = token_hash
            user.invited_at = datetime.now(UTC)

            await db.commit()

            logger.info(
                "invitation_resent",
                user_id=str(user.id),
                workspace_id=str(user.workspace_id),
                email=user.email,
            )

            return token

        except (InvitationNotFoundError, UserAlreadyActiveError):
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.error(
                "resend_invitation_failed",
                user_id=str(user_id),
                error=str(e),
                exc_info=True,
            )
            raise
