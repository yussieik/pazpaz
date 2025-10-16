"""Pydantic schemas for session attachment API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SessionAttachmentResponse(BaseModel):
    """
    Response schema for session attachment.

    Returns metadata about uploaded file (not the file content itself).
    Use GET /attachments/{id}/download to get pre-signed download URL.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Attachment UUID")
    session_id: uuid.UUID = Field(description="Session UUID")
    workspace_id: uuid.UUID = Field(description="Workspace UUID")
    file_name: str = Field(description="Sanitized filename")
    file_type: str = Field(description="MIME type (e.g., image/jpeg)")
    file_size_bytes: int = Field(description="File size in bytes")
    created_at: datetime = Field(description="Upload timestamp")


class SessionAttachmentListResponse(BaseModel):
    """Response schema for list of session attachments."""

    items: list[SessionAttachmentResponse] = Field(description="List of attachments")
    total: int = Field(description="Total number of attachments")
