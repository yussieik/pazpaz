"""Google Calendar OAuth 2.0 token storage model."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base
from pazpaz.db.types import EncryptedString

if TYPE_CHECKING:
    from pazpaz.models.user import User
    from pazpaz.models.workspace import Workspace


class GoogleCalendarToken(Base):
    """
    Google Calendar OAuth 2.0 token storage for two-way calendar sync.

    This model securely stores OAuth 2.0 access and refresh tokens for Google Calendar
    integration. It enables PazPaz to sync appointments bidirectionally with users'
    Google Calendar accounts.

    OAuth Token Lifecycle:
    - access_token: Short-lived token (typically 1 hour) for API calls
    - refresh_token: Long-lived token (valid until user revokes access) for
      obtaining new access tokens when they expire
    - token_expiry: Timestamp when current access token expires (UTC)

    Security:
    - Both access_token and refresh_token are encrypted at rest using AES-256-GCM
    - Encryption is transparent via EncryptedString SQLAlchemy type
    - Workspace scoping enforced on all queries
    - One token record per user per workspace (unique constraint)
    - CASCADE delete when workspace or user is deleted

    Sync Management:
    - enabled: Boolean flag to pause/resume sync without deleting tokens
    - calendar_list: Cached list of user's calendars from Google Calendar API
    - scopes: Array of OAuth scopes granted (e.g., ["https://www.googleapis.com/auth/calendar"])

    Performance Considerations:
    - Index on (workspace_id, enabled) for active token lookups
    - JSONB storage for calendar_list and scopes (flexible schema)
    - No indexes on encrypted fields (not searchable by content)

    Token Refresh Flow:
    1. Check if access_token is expired (token_expiry < now)
    2. If expired, use refresh_token to request new access_token from Google
    3. Update access_token and token_expiry in database
    4. If refresh_token is invalid/revoked, user must re-authenticate

    Example Usage:
        # Store tokens after OAuth flow
        token = GoogleCalendarToken(
            workspace_id=workspace.id,
            user_id=user.id,
            access_token="ya29.a0...",  # Encrypted automatically
            refresh_token="1//0gZ...",  # Encrypted automatically
            token_expiry=datetime.now(UTC) + timedelta(hours=1),
            scopes=["https://www.googleapis.com/auth/calendar"],
            enabled=True,
        )
        session.add(token)
        await session.commit()

        # Check if token needs refresh
        if token.token_expiry < datetime.now(UTC):
            new_access_token = await refresh_google_token(token.refresh_token)
            token.access_token = new_access_token
            token.token_expiry = datetime.now(UTC) + timedelta(hours=1)
            await session.commit()
    """

    __tablename__ = "google_calendar_tokens"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign keys (workspace scoping and user ownership)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Workspace this token belongs to (workspace scoping)",
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="User who authorized Google Calendar access",
    )

    # ENCRYPTED OAuth Tokens
    # CRITICAL: Use EncryptedString type for transparent AES-256-GCM encryption
    # These tokens grant access to user's Google Calendar and must be protected
    access_token: Mapped[str] = mapped_column(
        EncryptedString(2000),  # Google access tokens are typically ~200 chars
        nullable=False,
        comment="ENCRYPTED: OAuth 2.0 access token (short-lived, ~1 hour) - AES-256-GCM",
    )
    refresh_token: Mapped[str] = mapped_column(
        EncryptedString(2000),  # Google refresh tokens are typically ~200 chars
        nullable=False,
        comment="ENCRYPTED: OAuth 2.0 refresh token (long-lived, until revoked) - AES-256-GCM",
    )

    # Token metadata (non-encrypted)
    token_expiry: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When the access token expires (timezone-aware UTC)",
    )
    scopes: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        comment='OAuth scopes granted (e.g., ["https://www.googleapis.com/auth/calendar"])',
    )
    calendar_list: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Cached list of user's calendars from Google Calendar API",
    )

    # Sync control
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="Whether sync is active (false = paused, true = active)",
    )
    sync_client_names: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="Whether to sync client names to Google Calendar event titles (privacy setting)",
    )

    # Sync tracking
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of the last successful sync operation",
    )
    last_sync_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Status of the last sync operation (success, error)",
    )
    last_sync_error: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="Error message from the last failed sync operation",
    )

    # Audit columns
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    workspace: Mapped[Workspace] = relationship(
        "Workspace",
        backref="google_calendar_tokens",
    )
    user: Mapped[User] = relationship(
        "User",
        backref="google_calendar_tokens",
    )

    # Constraints and indexes
    __table_args__ = (
        # Unique constraint: One token record per user per workspace
        UniqueConstraint(
            "workspace_id",
            "user_id",
            name="uq_google_calendar_tokens_workspace_user",
        ),
        # Index for active token lookups (workspace + enabled filter)
        Index(
            "ix_google_calendar_tokens_workspace_enabled",
            "workspace_id",
            "enabled",
        ),
        {
            "comment": "OAuth 2.0 tokens for Google Calendar integration with encrypted credentials"
        },
    )

    def __repr__(self) -> str:
        return (
            f"<GoogleCalendarToken(id={self.id}, user_id={self.user_id}, "
            f"enabled={self.enabled}, expires={self.token_expiry})>"
        )

    @property
    def is_expired(self) -> bool:
        """
        Check if the access token is expired.

        Returns:
            True if token_expiry is in the past, False otherwise

        Example:
            >>> token.token_expiry = datetime(2025, 10, 28, 10, 0, 0, tzinfo=UTC)
            >>> token.is_expired  # Assuming current time is after expiry
            True
        """
        return self.token_expiry < datetime.now(UTC)
