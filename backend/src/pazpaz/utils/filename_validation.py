"""Filename validation and normalization utilities.

This module provides secure filename validation for attachment renaming:
- Character validation (prohibits special characters)
- Length constraints (1-255 characters)
- Whitespace trimming
- Extension preservation
- Duplicate detection

Security:
- Prevents path traversal (no /, backslash, etc.)
- Sanitizes user input
- Maintains file extension integrity
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.models.session_attachment import SessionAttachment


class FilenameValidationError(ValueError):
    """Base exception for filename validation errors."""

    pass


# Prohibited filename characters (filesystem unsafe)
INVALID_CHARS_PATTERN = r'[/\\:*?"<>|]'

# Maximum filename length (standard filesystem limit)
MAX_FILENAME_LENGTH = 255


def extract_extension(filename: str) -> str:
    """
    Extract file extension from filename (including the dot).

    Args:
        filename: Original filename

    Returns:
        Extension including dot (e.g., ".jpg", ".pdf") or empty string

    Examples:
        >>> extract_extension("photo.jpg")
        '.jpg'
        >>> extract_extension("document.backup.pdf")
        '.pdf'
        >>> extract_extension("noextension")
        ''
    """
    path = Path(filename)
    return path.suffix.lower()  # Returns empty string if no extension


def validate_filename_characters(filename: str) -> None:
    r"""
    Validate filename contains only allowed characters.

    Prohibited characters: / \ : * ? " < > |
    These characters are unsafe for filesystems and could enable path traversal.

    Args:
        filename: Filename to validate

    Raises:
        FilenameValidationError: If filename contains invalid characters

    Examples:
        >>> validate_filename_characters("normal_file.jpg")  # OK
        >>> validate_filename_characters("../../etc/passwd")
        FilenameValidationError: Filename contains invalid characters
    """
    if re.search(INVALID_CHARS_PATTERN, filename):
        raise FilenameValidationError(
            "Filename contains invalid characters. "
            r'The following characters are not allowed: / \ : * ? " < > |'
        )


def validate_filename_length(filename: str) -> None:
    """
    Validate filename length is within filesystem limits.

    Args:
        filename: Filename to validate (should be trimmed first)

    Raises:
        FilenameValidationError: If filename is empty or too long

    Examples:
        >>> validate_filename_length("photo.jpg")  # OK
        >>> validate_filename_length("")
        FilenameValidationError: Filename cannot be empty
        >>> validate_filename_length("x" * 300)
        FilenameValidationError: Filename too long (max 255 characters)
    """
    if len(filename) == 0:
        raise FilenameValidationError("Filename cannot be empty")

    if len(filename) > MAX_FILENAME_LENGTH:
        raise FilenameValidationError(
            f"Filename too long (max {MAX_FILENAME_LENGTH} characters)"
        )


async def check_duplicate_filename(
    db: AsyncSession,
    client_id: uuid.UUID,
    filename: str,
    exclude_attachment_id: uuid.UUID | None = None,
) -> bool:
    """
    Check if filename already exists for this client.

    Checks across both session-level and client-level attachments for the same client.
    This prevents duplicate filenames within a client's attachment collection.

    Args:
        db: Database session
        client_id: Client UUID (all attachments belong to a client)
        filename: Filename to check (case-sensitive)
        exclude_attachment_id: Attachment ID to exclude (when renaming existing file)

    Returns:
        True if duplicate exists, False otherwise

    Examples:
        >>> await check_duplicate_filename(db, client_id, "intake_form.pdf")
        False  # No duplicate
        >>> await check_duplicate_filename(db, client_id, "existing.jpg")
        True  # Duplicate exists
        >>> await check_duplicate_filename(
        ...     db, client_id, "same.jpg", exclude_attachment_id=attachment.id
        ... )
        False  # Excludes self when renaming
    """
    query = select(SessionAttachment).where(
        SessionAttachment.client_id == client_id,
        SessionAttachment.file_name == filename,
        SessionAttachment.deleted_at.is_(None),  # Exclude soft-deleted files
    )

    # Exclude current attachment when renaming (don't check against self)
    if exclude_attachment_id is not None:
        query = query.where(SessionAttachment.id != exclude_attachment_id)

    result = await db.execute(query)
    existing = result.scalar_one_or_none()

    return existing is not None


async def validate_and_normalize_filename(
    db: AsyncSession,
    new_name: str,
    original_extension: str,
    client_id: uuid.UUID,
    exclude_attachment_id: uuid.UUID | None = None,
) -> str:
    """
    Validate and normalize a filename for attachment renaming.

    This is the main entry point for filename validation. It performs:
    1. Whitespace trimming
    2. Length validation (1-255 chars)
    3. Character validation (no special chars)
    4. Extension preservation (appends if missing)
    5. Duplicate detection

    Args:
        db: Database session (for duplicate check)
        new_name: User-provided new filename
        original_extension: Original file extension (e.g., ".jpg", ".pdf")
        client_id: Client UUID (for duplicate check)
        exclude_attachment_id: Current attachment ID (when renaming, exclude self)

    Returns:
        Normalized filename with extension

    Raises:
        FilenameValidationError: If validation fails (empty, too long, invalid chars, duplicate)

    Examples:
        >>> await validate_and_normalize_filename(
        ...     db, "  My Photo  ", ".jpg", client_id
        ... )
        "My Photo.jpg"  # Trimmed, extension added

        >>> await validate_and_normalize_filename(
        ...     db, "Document", ".pdf", client_id
        ... )
        "Document.pdf"  # Extension appended

        >>> await validate_and_normalize_filename(
        ...     db, "../../secret", ".jpg", client_id
        ... )
        FilenameValidationError: Filename contains invalid characters

        >>> await validate_and_normalize_filename(
        ...     db, "", ".jpg", client_id
        ... )
        FilenameValidationError: Filename cannot be empty

        >>> await validate_and_normalize_filename(
        ...     db, "existing_file.jpg", ".jpg", client_id
        ... )
        FilenameValidationError: A file with this name already exists
    """
    # Step 1: Trim whitespace
    trimmed = new_name.strip()

    # Step 2: Validate length (must be done after trimming)
    validate_filename_length(trimmed)

    # Step 3: Validate characters (no path traversal)
    validate_filename_characters(trimmed)

    # Step 4: Preserve/append file extension
    # If user provided extension, keep it; otherwise append original extension
    if not trimmed.lower().endswith(original_extension.lower()):
        full_filename = f"{trimmed}{original_extension}"
    else:
        full_filename = trimmed

    # Final length check after adding extension
    if len(full_filename) > MAX_FILENAME_LENGTH:
        max_name_length = MAX_FILENAME_LENGTH - len(original_extension)
        raise FilenameValidationError(
            f"Filename too long. Maximum {max_name_length} characters "
            f"(excluding {original_extension} extension)"
        )

    # Step 5: Check for duplicates
    is_duplicate = await check_duplicate_filename(
        db=db,
        client_id=client_id,
        filename=full_filename,
        exclude_attachment_id=exclude_attachment_id,
    )

    if is_duplicate:
        raise FilenameValidationError("A file with this name already exists")

    return full_filename
