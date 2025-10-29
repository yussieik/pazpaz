"""Pydantic schemas for Google Calendar Integration API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GoogleCalendarStatusResponse(BaseModel):
    """
    Response schema for Google Calendar integration status.

    Indicates whether the current user has connected their Google Calendar account,
    when the last sync occurred, and whether sync is currently enabled.

    Attributes:
        connected: True if user has authorized Google Calendar access
        enabled: True if sync is active, False if paused
        sync_client_names: Whether client names are included in calendar events
        notify_clients: Whether client notifications are enabled
        last_sync_at: Timestamp of most recent calendar sync (None if never synced)
    """

    connected: bool = Field(
        ..., description="Whether Google Calendar is connected for this user"
    )
    enabled: bool = Field(
        False, description="Whether calendar sync is currently enabled"
    )
    sync_client_names: bool = Field(
        False, description="Whether client names are included in calendar events"
    )
    notify_clients: bool = Field(
        False, description="Whether client notifications are enabled"
    )
    has_google_baa: bool = Field(
        False, description="Whether therapist has Google Workspace BAA signed"
    )
    last_sync_at: datetime | None = Field(
        None, description="Timestamp of last calendar sync (UTC, None if never synced)"
    )


class GoogleCalendarAuthorizeResponse(BaseModel):
    """
    Response schema for OAuth authorization URL generation.

    Contains the Google OAuth 2.0 authorization URL that the frontend should
    redirect the user to for granting calendar access permissions.

    Attributes:
        authorization_url: Full OAuth URL with all required parameters
    """

    authorization_url: str = Field(
        ...,
        description="Google OAuth 2.0 authorization URL for user to grant access",
    )


class GoogleCalendarSettingsUpdate(BaseModel):
    """
    Request schema for updating Google Calendar sync settings.

    All fields are optional to support partial updates.

    Attributes:
        enabled: Enable/disable automatic sync
        sync_client_names: Include client names in calendar event titles
        notify_clients: Send Google Calendar invitations to clients (requires client email)

    Example:
        {
            "enabled": true,
            "sync_client_names": false,
            "notify_clients": true
        }
    """

    enabled: bool | None = Field(
        None,
        description="Enable or disable automatic calendar sync",
    )
    sync_client_names: bool | None = Field(
        None,
        description="Include client names in calendar event titles (HIPAA consideration)",
    )
    notify_clients: bool | None = Field(
        None,
        description="Send Google Calendar invitations to clients (requires client email)",
    )
    has_google_baa: bool | None = Field(
        None,
        description="Confirm Google Workspace Business Associate Agreement (BAA) is signed",
    )


class GoogleCalendarSettingsResponse(BaseModel):
    """
    Response schema for Google Calendar settings.

    Attributes:
        enabled: Whether automatic sync is enabled
        sync_client_names: Whether client names are included in events
        notify_clients: Whether client notifications are enabled
        last_sync_at: Timestamp of last successful sync
        last_sync_status: Status of last sync ("success" or "error")
        last_sync_error: Error message if last sync failed
    """

    enabled: bool = Field(..., description="Whether automatic sync is enabled")
    sync_client_names: bool = Field(
        ..., description="Whether client names are included in calendar events"
    )
    notify_clients: bool = Field(
        ..., description="Whether client notifications are enabled"
    )
    has_google_baa: bool = Field(
        ..., description="Whether therapist has Google Workspace BAA signed"
    )
    last_sync_at: datetime | None = Field(
        None, description="Timestamp of last sync (UTC)"
    )
    last_sync_status: str | None = Field(
        None, description='Last sync status: "success" or "error"'
    )
    last_sync_error: str | None = Field(
        None, description="Error message if last sync failed"
    )
