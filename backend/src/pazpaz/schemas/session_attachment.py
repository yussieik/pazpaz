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

    Supports both session-level and client-level attachments:
    - Session-level: session_id is set, is_session_file=True
    - Client-level: session_id is None, is_session_file=False
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Attachment UUID")
    session_id: uuid.UUID | None = Field(
        description="Session UUID (None for client-level attachments)"
    )
    client_id: uuid.UUID = Field(description="Client UUID (always present)")
    workspace_id: uuid.UUID = Field(description="Workspace UUID")
    file_name: str = Field(description="Sanitized filename")
    file_type: str = Field(description="MIME type (e.g., image/jpeg)")
    file_size_bytes: int = Field(description="File size in bytes")
    created_at: datetime = Field(description="Upload timestamp")
    session_date: datetime | None = Field(
        None,
        description="Date of session (None for client-level attachments)",
    )
    is_session_file: bool = Field(
        description="True if attached to specific session, False if client-level"
    )


class SessionAttachmentListResponse(BaseModel):
    """Response schema for list of session attachments."""

    items: list[SessionAttachmentResponse] = Field(description="List of attachments")
    total: int = Field(description="Total number of attachments")


class AttachmentRenameRequest(BaseModel):
    """
    Request schema for renaming an attachment.

    The filename is validated and normalized:
    - Whitespace is trimmed
    - Length must be 1-255 characters
    - Invalid characters are rejected: / \\ : * ? " < > |
    - File extension is preserved automatically
    - Duplicate filenames are rejected
    """

    file_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="New filename (extension will be preserved automatically)",
        examples=["Treatment notes - Oct 2025", "Left shoulder pain"],
    )


class BulkDownloadRequest(BaseModel):
    """
    Request schema for bulk downloading multiple attachments as a ZIP file.

    Validation:
    - At least 1 attachment ID required
    - Maximum 50 attachments per request (prevents abuse)
    - All attachment IDs must be valid UUIDs

    Security:
    - All attachments must belong to the specified client
    - All attachments must belong to user's workspace
    - Total file size limited to 100 MB
    """

    attachment_ids: list[uuid.UUID] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of attachment UUIDs to download (1-50 files)",
        examples=[
            [
                uuid.UUID("12345678-1234-5678-1234-567812345678"),
                uuid.UUID("87654321-4321-8765-4321-876543218765"),
            ]
        ],
    )
