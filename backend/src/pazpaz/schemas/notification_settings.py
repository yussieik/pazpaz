"""Pydantic schemas for user notification settings API."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError


class NotificationSettingsResponse(BaseModel):
    """Response schema for user notification settings.

    This schema represents the complete notification settings for a user,
    including all email notification preferences, digest settings, and reminders.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    workspace_id: uuid.UUID

    # Master toggle
    email_enabled: bool = Field(
        ...,
        description="Master toggle - when false, no emails are sent",
    )

    # Event notifications
    notify_appointment_booked: bool = Field(
        ...,
        description="Send email when new appointment is booked",
    )
    notify_appointment_cancelled: bool = Field(
        ...,
        description="Send email when appointment is cancelled",
    )
    notify_appointment_rescheduled: bool = Field(
        ...,
        description="Send email when appointment is rescheduled",
    )
    notify_appointment_confirmed: bool = Field(
        ...,
        description="Send email when client confirms appointment",
    )

    # Daily digest settings
    digest_enabled: bool = Field(
        ...,
        description="Enable daily digest email (opt-in)",
    )
    digest_time: str | None = Field(
        None,
        description="Time to send digest in HH:MM format (24-hour, workspace timezone)",
        examples=["08:00", "18:30"],
    )
    digest_skip_weekends: bool = Field(
        ...,
        description="Skip digest on Saturdays and Sundays",
    )

    # Appointment reminder settings
    reminder_enabled: bool = Field(
        ...,
        description="Enable appointment reminder emails",
    )
    reminder_minutes: int | None = Field(
        None,
        description="Minutes before appointment to send reminder (15, 30, 60, 120, 1440)",
        examples=[60, 1440],
    )

    # Session notes reminder settings
    notes_reminder_enabled: bool = Field(
        ...,
        description="Enable draft session notes reminders",
    )
    notes_reminder_time: str | None = Field(
        None,
        description="Time to send notes reminder in HH:MM format (24-hour, workspace timezone)",
        examples=["18:00", "20:00"],
    )

    # Future extensibility
    extended_settings: dict[str, Any] | None = Field(
        None,
        description="Future notification preferences (SMS, push, quiet hours, etc.)",
    )

    # Audit fields
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationSettingsUpdate(BaseModel):
    """Request schema for updating user notification settings.

    All fields are optional to support partial updates.
    Only provided fields will be updated.
    """

    # Master toggle
    email_enabled: bool | None = Field(
        None,
        description="Master toggle - when false, no emails are sent",
    )

    # Event notifications
    notify_appointment_booked: bool | None = Field(
        None,
        description="Send email when new appointment is booked",
    )
    notify_appointment_cancelled: bool | None = Field(
        None,
        description="Send email when appointment is cancelled",
    )
    notify_appointment_rescheduled: bool | None = Field(
        None,
        description="Send email when appointment is rescheduled",
    )
    notify_appointment_confirmed: bool | None = Field(
        None,
        description="Send email when client confirms appointment",
    )

    # Daily digest settings
    digest_enabled: bool | None = Field(
        None,
        description="Enable daily digest email (opt-in)",
    )
    digest_time: str | None = Field(
        None,
        description="Time to send digest in HH:MM format (24-hour, workspace timezone)",
        examples=["08:00", "18:30"],
    )
    digest_skip_weekends: bool | None = Field(
        None,
        description="Skip digest on Saturdays and Sundays",
    )

    # Appointment reminder settings
    reminder_enabled: bool | None = Field(
        None,
        description="Enable appointment reminder emails",
    )
    reminder_minutes: int | None = Field(
        None,
        description="Minutes before appointment to send reminder (15, 30, 60, 120, 1440)",
        examples=[60, 1440],
    )

    # Session notes reminder settings
    notes_reminder_enabled: bool | None = Field(
        None,
        description="Enable draft session notes reminders",
    )
    notes_reminder_time: str | None = Field(
        None,
        description="Time to send notes reminder in HH:MM format (24-hour, workspace timezone)",
        examples=["18:00", "20:00"],
    )

    # Future extensibility
    extended_settings: dict[str, Any] | None = Field(
        None,
        description="Future notification preferences (SMS, push, quiet hours, etc.)",
    )

    @field_validator("digest_time", "notes_reminder_time")
    @classmethod
    def validate_time_format(cls, v: str | None) -> str | None:
        """
        Validate time format is HH:MM in 24-hour format.

        Args:
            v: Time string to validate

        Returns:
            Validated time string

        Raises:
            PydanticCustomError: If time format is invalid
        """
        if v is None:
            return v

        # Import validation from model
        from pazpaz.models.user_notification_settings import UserNotificationSettings

        if not UserNotificationSettings.is_valid_time_format(v):
            raise PydanticCustomError(
                "time_format",
                "Time must be in HH:MM format (00:00 to 23:59), got: {time}",
                {"time": v},
            )

        return v

    @field_validator("reminder_minutes")
    @classmethod
    def validate_reminder_minutes(cls, v: int | None) -> int | None:
        """
        Validate reminder minutes is one of the allowed presets.

        Args:
            v: Minutes value to validate

        Returns:
            Validated minutes value

        Raises:
            PydanticCustomError: If minutes is not an allowed preset
        """
        if v is None:
            return v

        # Import validation from model
        from pazpaz.models.user_notification_settings import UserNotificationSettings

        if not UserNotificationSettings.is_valid_reminder_minutes(v):
            raise PydanticCustomError(
                "reminder_minutes_invalid",
                "reminder_minutes must be one of: 15, 30, 60, 120, 1440, got: {minutes}",
                {"minutes": v},
            )

        return v
