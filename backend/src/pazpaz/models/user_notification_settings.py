"""UserNotificationSettings model - user notification preferences."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pazpaz.db.base import Base

if TYPE_CHECKING:
    from pazpaz.models.user import User
    from pazpaz.models.workspace import Workspace


class UserNotificationSettings(Base):
    """
    UserNotificationSettings stores notification preferences for each user.

    This model uses a hybrid approach:
    - Typed columns for core Phase 1 email notification settings
    - JSONB column (extended_settings) for future channels (SMS, push, in-app)

    Design rationale:
    - Typed columns enable efficient batch queries for background jobs
      (e.g., "find all users wanting daily digest at 08:00")
    - JSONB provides extensibility without migrations for experimental features
    - CHECK constraints enforce data integrity at database level

    Relationship: One-to-one with User (each user has exactly one settings record)

    Workspace scoping: All queries must filter by workspace_id for privacy isolation.

    Time handling: Times are stored as strings in "HH:MM" 24-hour format and
    interpreted in the workspace's timezone. This avoids DST complexity.

    Future extensions:
    - SMS notifications: Add to extended_settings["sms"]
    - Push notifications: Add to extended_settings["push"]
    - Quiet hours: Add to extended_settings["quiet_hours"]
    - When features mature, promote to typed columns via migration

    See also: /docs/backend/database/NOTIFICATION_SETTINGS_SCHEMA.md
    """

    __tablename__ = "user_notification_settings"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        comment="Unique identifier for notification settings",
    )

    # Foreign keys (workspace scoping + user relationship)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="User who owns these notification settings (one-to-one)",
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Workspace context for privacy isolation",
    )

    # Master toggle
    email_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        comment="Master toggle - disable all email notifications",
    )

    # Event notifications (appointment lifecycle)
    notify_appointment_booked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        comment="Send email when new appointment is booked",
    )

    notify_appointment_cancelled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        comment="Send email when appointment is cancelled",
    )

    notify_appointment_rescheduled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        comment="Send email when appointment is rescheduled",
    )

    notify_appointment_confirmed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        comment="Send email when client confirms appointment",
    )

    # Daily digest settings
    digest_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
        comment="Enable daily digest email (opt-in)",
    )

    digest_time: Mapped[str | None] = mapped_column(
        String(5),
        nullable=True,
        server_default=text("'08:00'"),
        comment="Time to send digest in HH:MM format (24-hour, workspace timezone)",
    )

    digest_days: Mapped[list[int]] = mapped_column(
        ARRAY(Integer),
        nullable=False,
        server_default=text("'{1,2,3,4,5}'"),
        comment="Days of week to send digest (0=Sunday, 1=Monday, ..., 6=Saturday)",
    )

    # Appointment reminder settings
    reminder_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        comment="Enable appointment reminder emails",
    )

    reminder_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        server_default=text("60"),
        comment="Minutes before appointment to send reminder (15, 30, 60, 120, 1440)",
    )

    # Session notes reminder settings
    notes_reminder_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
        comment="Enable draft session notes reminders",
    )

    notes_reminder_time: Mapped[str | None] = mapped_column(
        String(5),
        nullable=True,
        server_default=text("'18:00'"),
        comment="Time to send notes reminder in HH:MM format (24-hour, workspace timezone)",
    )

    # Future extensibility (JSONB)
    extended_settings: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        server_default=text("'{}'"),
        comment="Future notification preferences (SMS, push, quiet hours, etc.)",
    )

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="When settings were created",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        onupdate=lambda: datetime.now(UTC),
        comment="When settings were last modified",
    )

    # Relationships
    user: Mapped[User] = relationship(
        "User",
        back_populates="notification_settings",
    )

    workspace: Mapped[Workspace] = relationship(
        "Workspace",
        back_populates="notification_settings",
    )

    # Constraints and indexes
    __table_args__ = (
        # Unique constraints (one-to-one with user)
        UniqueConstraint(
            "user_id",
            name="uq_user_notification_settings_user_id",
        ),
        UniqueConstraint(
            "workspace_id",
            "user_id",
            name="uq_user_notification_settings_workspace_user",
        ),
        # CHECK constraints for data validation
        CheckConstraint(
            "digest_time IS NULL OR digest_time ~ '^([0-1][0-9]|2[0-3]):[0-5][0-9]$'",
            name="ck_digest_time_format",
        ),
        CheckConstraint(
            "notes_reminder_time IS NULL OR notes_reminder_time ~ '^([0-1][0-9]|2[0-3]):[0-5][0-9]$'",
            name="ck_notes_reminder_time_format",
        ),
        CheckConstraint(
            "reminder_minutes IS NULL OR reminder_minutes IN (15, 30, 60, 120, 1440)",
            name="ck_reminder_minutes_valid",
        ),
        # Index for workspace scoping queries
        Index(
            "idx_user_notification_settings_workspace_id",
            "workspace_id",
        ),
        # Composite index for user lookup (most common query)
        Index(
            "idx_user_notification_settings_workspace_user",
            "workspace_id",
            "user_id",
        ),
        # Partial index for daily digest batch queries (background jobs)
        Index(
            "idx_user_notification_settings_digest",
            "digest_enabled",
            "digest_time",
            postgresql_where=text("email_enabled = true AND digest_enabled = true"),
        ),
        # Partial index for appointment reminder batch queries (background jobs)
        Index(
            "idx_user_notification_settings_reminder",
            "reminder_enabled",
            "reminder_minutes",
            postgresql_where=text("email_enabled = true AND reminder_enabled = true"),
        ),
        {
            "comment": (
                "User notification preferences with hybrid typed/JSONB approach"
            )
        },
    )

    def __repr__(self) -> str:
        """Return string representation of notification settings."""
        return (
            f"<UserNotificationSettings(id={self.id}, "
            f"user_id={self.user_id}, "
            f"email_enabled={self.email_enabled})>"
        )

    # Validation methods

    @staticmethod
    def is_valid_time_format(time_str: str | None) -> bool:
        """
        Validate time string is in HH:MM 24-hour format.

        Args:
            time_str: Time string to validate (e.g., "08:00", "18:30")

        Returns:
            True if valid format, False otherwise

        Examples:
            >>> UserNotificationSettings.is_valid_time_format("08:00")
            True
            >>> UserNotificationSettings.is_valid_time_format("23:59")
            True
            >>> UserNotificationSettings.is_valid_time_format("24:00")
            False
            >>> UserNotificationSettings.is_valid_time_format("8:00")
            False
            >>> UserNotificationSettings.is_valid_time_format(None)
            True
        """
        if time_str is None:
            return True

        # Regex: ^([0-1][0-9]|2[0-3]):[0-5][0-9]$
        # Matches: 00:00 to 23:59
        pattern = r"^([0-1][0-9]|2[0-3]):[0-5][0-9]$"
        return bool(re.match(pattern, time_str))

    @staticmethod
    def is_valid_reminder_minutes(minutes: int | None) -> bool:
        """
        Validate reminder minutes is one of the allowed presets.

        Args:
            minutes: Minutes before appointment (15, 30, 60, 120, 1440)

        Returns:
            True if valid preset, False otherwise

        Examples:
            >>> UserNotificationSettings.is_valid_reminder_minutes(60)
            True
            >>> UserNotificationSettings.is_valid_reminder_minutes(1440)
            True
            >>> UserNotificationSettings.is_valid_reminder_minutes(90)
            False
            >>> UserNotificationSettings.is_valid_reminder_minutes(None)
            True
        """
        if minutes is None:
            return True

        # Valid presets: 15, 30, 60, 120, 1440 (1 day)
        return minutes in {15, 30, 60, 120, 1440}

    def validate(self) -> list[str]:
        """
        Validate notification settings and return list of errors.

        Returns:
            List of validation error messages (empty if valid)

        Examples:
            >>> settings = UserNotificationSettings(
            ...     digest_time="25:00",
            ...     reminder_minutes=90
            ... )
            >>> settings.validate()
            ['digest_time must be in HH:MM format (00:00 to 23:59)',
             'reminder_minutes must be one of: 15, 30, 60, 120, 1440']
        """
        errors = []

        # Validate digest_time format
        if not self.is_valid_time_format(self.digest_time):
            errors.append(
                f"digest_time must be in HH:MM format (00:00 to 23:59), got: {self.digest_time}"
            )

        # Validate notes_reminder_time format
        if not self.is_valid_time_format(self.notes_reminder_time):
            errors.append(
                f"notes_reminder_time must be in HH:MM format (00:00 to 23:59), got: {self.notes_reminder_time}"
            )

        # Validate reminder_minutes preset
        if not self.is_valid_reminder_minutes(self.reminder_minutes):
            errors.append(
                f"reminder_minutes must be one of: 15, 30, 60, 120, 1440, got: {self.reminder_minutes}"
            )

        return errors

    # Helper methods for common queries

    @property
    def should_send_emails(self) -> bool:
        """
        Check if any emails should be sent (master toggle check).

        Returns:
            True if email_enabled is True, False otherwise

        Examples:
            >>> settings = UserNotificationSettings(email_enabled=True)
            >>> settings.should_send_emails
            True
            >>> settings = UserNotificationSettings(email_enabled=False)
            >>> settings.should_send_emails
            False
        """
        return self.email_enabled

    @property
    def should_send_digest(self) -> bool:
        """
        Check if daily digest should be sent.

        Returns:
            True if email_enabled AND digest_enabled, False otherwise

        Examples:
            >>> settings = UserNotificationSettings(
            ...     email_enabled=True,
            ...     digest_enabled=True
            ... )
            >>> settings.should_send_digest
            True
            >>> settings = UserNotificationSettings(
            ...     email_enabled=False,
            ...     digest_enabled=True
            ... )
            >>> settings.should_send_digest
            False
        """
        return self.email_enabled and self.digest_enabled

    @property
    def should_send_reminder(self) -> bool:
        """
        Check if appointment reminders should be sent.

        Returns:
            True if email_enabled AND reminder_enabled, False otherwise

        Examples:
            >>> settings = UserNotificationSettings(
            ...     email_enabled=True,
            ...     reminder_enabled=True
            ... )
            >>> settings.should_send_reminder
            True
        """
        return self.email_enabled and self.reminder_enabled

    @property
    def should_send_notes_reminder(self) -> bool:
        """
        Check if session notes reminders should be sent.

        Returns:
            True if email_enabled AND notes_reminder_enabled, False otherwise

        Examples:
            >>> settings = UserNotificationSettings(
            ...     email_enabled=True,
            ...     notes_reminder_enabled=True
            ... )
            >>> settings.should_send_notes_reminder
            True
        """
        return self.email_enabled and self.notes_reminder_enabled

    # Extended settings helpers (JSONB access)

    def get_extended_setting(self, key_path: str, default: Any = None) -> Any:
        """
        Get value from extended_settings JSONB using dot notation.

        Args:
            key_path: Dot-separated path (e.g., "sms.enabled")
            default: Default value if key not found

        Returns:
            Value from JSONB or default

        Examples:
            >>> settings = UserNotificationSettings(
            ...     extended_settings={"sms": {"enabled": true}}
            ... )
            >>> settings.get_extended_setting("sms.enabled")
            True
            >>> settings.get_extended_setting("sms.phone_number", None)
            None
        """
        if not self.extended_settings:
            return default

        keys = key_path.split(".")
        value = self.extended_settings

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def set_extended_setting(self, key_path: str, value: Any) -> None:
        """
        Set value in extended_settings JSONB using dot notation.

        Args:
            key_path: Dot-separated path (e.g., "sms.enabled")
            value: Value to set

        Examples:
            >>> settings = UserNotificationSettings()
            >>> settings.set_extended_setting("sms.enabled", True)
            >>> settings.extended_settings
            {"sms": {"enabled": True}}
        """
        if not self.extended_settings:
            self.extended_settings = {}

        keys = key_path.split(".")
        current = self.extended_settings

        # Navigate to parent dict, creating nested dicts as needed
        for key in keys[:-1]:
            if key not in current or not isinstance(current[key], dict):
                current[key] = {}
            current = current[key]

        # Set final value
        current[keys[-1]] = value
