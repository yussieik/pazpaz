"""File sanitization utilities for removing metadata and ensuring safe content.

This module provides functions to sanitize uploaded files by:
1. Stripping EXIF metadata from images (GPS, camera info, timestamps)
2. Stripping PDF metadata (author, title, subject, keywords, creator, producer, dates)
3. Re-encoding images to remove embedded scripts or malicious content
4. Normalizing file content for safe storage

Security principles:
- Privacy protection: Remove location data (GPS coordinates)
- Metadata removal: Strip camera info, software tags, author info
- Re-encoding: Ensures clean image data without hidden payloads
- Format normalization: Standardize image encoding
- PHI protection: Remove metadata that may contain identifying information

Privacy concerns with metadata:
- GPS coordinates can reveal patient home addresses or treatment locations
- Camera serial numbers and timestamps can be used for correlation attacks
- Software tags may reveal versions with known vulnerabilities
- Author/copyright/title info may contain PHI
- PDF metadata fields may contain therapist or patient identifying information
"""

from __future__ import annotations

import io

from PIL import Image
from pypdf import PdfReader, PdfWriter

from pazpaz.core.logging import get_logger
from pazpaz.utils.file_validation import FILE_TYPE_TO_PIL_FORMAT, FileType

logger = get_logger(__name__)


class SanitizationError(Exception):
    """Base exception for file sanitization errors."""

    pass


def strip_exif_metadata(
    file_content: bytes, file_type: FileType, filename: str
) -> bytes:
    """
    Strip EXIF metadata from images and re-encode for privacy.

    Removes all metadata including:
    - GPS coordinates (geolocation)
    - Camera make/model/serial number
    - Software information
    - Timestamps (original capture time)
    - Author/copyright/description fields
    - Embedded thumbnails

    Process:
    1. Open image with PIL
    2. Load pixel data (strips metadata)
    3. Create new image with same pixel data
    4. Save without metadata

    Args:
        file_content: Raw file bytes
        file_type: Validated FileType (JPEG, PNG, WEBP, or PDF)
        filename: Original filename (for logging)

    Returns:
        Sanitized file bytes without metadata

    Raises:
        SanitizationError: If sanitization fails

    Example:
        ```python
        sanitized_bytes = strip_exif_metadata(
            file_content=uploaded_bytes,
            file_type=FileType.JPEG,
            filename="wound_photo.jpg"
        )
        ```
    """
    # PDFs have different metadata structure - use dedicated stripping function
    if file_type == FileType.PDF:
        return strip_pdf_metadata(file_content, filename)

    # Only sanitize images
    if file_type not in (FileType.JPEG, FileType.PNG, FileType.WEBP):
        logger.warning(
            "unsupported_sanitization_type",
            file_type=file_type.value,
            filename=filename,
        )
        return file_content

    try:
        logger.info(
            "exif_stripping_started",
            filename=filename,
            file_type=file_type.value,
            original_size=len(file_content),
        )

        # Open image
        img = Image.open(io.BytesIO(file_content))

        # Check if image has EXIF data (for logging)
        has_exif = hasattr(img, "_getexif") and img._getexif() is not None
        if has_exif:
            logger.info("exif_metadata_detected", filename=filename)
        else:
            logger.debug("no_exif_metadata_found", filename=filename)

        # Load pixel data (this strips all metadata)
        # Creating new image from pixel data ensures clean image
        img_data = img.convert(img.mode)

        # Get PIL format from shared constant
        save_format = FILE_TYPE_TO_PIL_FORMAT[file_type]

        # Save image without metadata
        output = io.BytesIO()

        # Save parameters (optimized for size and quality)
        save_params = {}

        if file_type == FileType.JPEG:
            # JPEG quality: 85 (good balance of quality vs size)
            # optimize=True enables better compression
            save_params = {
                "format": save_format,
                "quality": 85,
                "optimize": True,
            }
        elif file_type == FileType.PNG:
            # PNG compression level: 6 (default, good balance)
            save_params = {
                "format": save_format,
                "optimize": True,
            }
        elif file_type == FileType.WEBP:
            # WebP quality: 85 (lossy), method 4 (balance speed/compression)
            save_params = {
                "format": save_format,
                "quality": 85,
                "method": 4,
            }

        img_data.save(output, **save_params)
        sanitized_bytes = output.getvalue()

        # Log size comparison
        original_size = len(file_content)
        sanitized_size = len(sanitized_bytes)
        size_reduction = original_size - sanitized_size
        reduction_percent = (
            (size_reduction / original_size * 100) if original_size > 0 else 0
        )

        logger.info(
            "exif_stripping_completed",
            filename=filename,
            original_size=original_size,
            sanitized_size=sanitized_size,
            size_reduction=size_reduction,
            reduction_percent=f"{reduction_percent:.1f}%",
            had_exif=has_exif,
        )

        return sanitized_bytes

    except Exception as e:
        logger.error(
            "exif_stripping_failed",
            filename=filename,
            file_type=file_type.value,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise SanitizationError(f"Failed to strip metadata from {filename}: {e}") from e


def strip_pdf_metadata(file_content: bytes, filename: str) -> bytes:
    """
    Strip metadata from PDF file for privacy protection.

    Removes metadata fields that may contain PHI or identifying information:
    - /Author - May contain therapist or patient name
    - /Title - May contain sensitive document titles
    - /Subject - May contain PHI descriptions
    - /Keywords - May contain sensitive search terms
    - /Creator - Application/software used
    - /Producer - PDF generation software
    - /CreationDate - Original creation timestamp
    - /ModDate - Last modification timestamp

    Process:
    1. Read PDF with pypdf
    2. Create new PDF writer
    3. Copy all pages without metadata
    4. Save without metadata fields

    Args:
        file_content: Raw PDF file bytes
        filename: Original filename (for logging)

    Returns:
        Sanitized PDF bytes without metadata

    Raises:
        SanitizationError: If PDF processing fails

    Example:
        ```python
        sanitized_bytes = strip_pdf_metadata(
            file_content=uploaded_pdf_bytes,
            filename="consent_form.pdf"
        )
        ```
    """
    try:
        logger.info(
            "pdf_metadata_stripping_started",
            filename=filename,
            original_size=len(file_content),
        )

        # Read PDF
        pdf_input = io.BytesIO(file_content)
        reader = PdfReader(pdf_input)

        # Log metadata before stripping (for audit purposes)
        metadata_before = reader.metadata
        if metadata_before:
            # Count non-None metadata fields (don't log values for privacy)
            metadata_field_count = sum(1 for v in metadata_before.values() if v)
            logger.info(
                "pdf_metadata_detected",
                filename=filename,
                metadata_field_count=metadata_field_count,
            )
        else:
            logger.debug("no_pdf_metadata_found", filename=filename)

        # Create new PDF writer without metadata
        writer = PdfWriter()

        # Copy all pages from original PDF
        for page in reader.pages:
            writer.add_page(page)

        # Explicitly set empty metadata to override pypdf's default Producer field
        # This ensures no metadata is written to the output PDF
        writer.add_metadata({})

        # Write sanitized PDF to bytes
        output = io.BytesIO()
        writer.write(output)
        sanitized_bytes = output.getvalue()

        # Log size comparison
        original_size = len(file_content)
        sanitized_size = len(sanitized_bytes)
        size_reduction = original_size - sanitized_size
        reduction_percent = (
            (size_reduction / original_size * 100) if original_size > 0 else 0
        )

        logger.info(
            "pdf_metadata_stripping_completed",
            filename=filename,
            original_size=original_size,
            sanitized_size=sanitized_size,
            size_reduction=size_reduction,
            reduction_percent=f"{reduction_percent:.1f}%",
            page_count=len(reader.pages),
            had_metadata=bool(metadata_before),
        )

        return sanitized_bytes

    except Exception as e:
        logger.error(
            "pdf_metadata_stripping_failed",
            filename=filename,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise SanitizationError(
            f"Failed to strip PDF metadata from {filename}: {e}"
        ) from e


def sanitize_filename(original_filename: str, max_length: int = 255) -> str:
    """
    Sanitize filename to prevent directory traversal and filesystem issues.

    Removes:
    - Path traversal characters (/, \\, ..)
    - Special characters that cause filesystem issues
    - Leading/trailing dots and spaces
    - Control characters

    Preserves:
    - Extension (validated separately)
    - Readable basename

    Args:
        original_filename: Original filename from upload
        max_length: Maximum filename length (default: 255 for most filesystems)

    Returns:
        Sanitized filename safe for filesystem storage

    Example:
        ```python
        # Dangerous filename
        unsafe = "../../etc/passwd.jpg"
        safe = sanitize_filename(unsafe)  # Returns "passwd.jpg"

        # Special characters
        unsafe = "wound<photo>?.jpg"
        safe = sanitize_filename(unsafe)  # Returns "wound_photo.jpg"
        ```
    """
    import re
    from pathlib import Path

    # Extract extension first (preserve it)
    path = Path(original_filename)
    extension = path.suffix.lower()
    basename = path.stem

    # Remove path traversal components (take only filename part)
    basename = Path(basename).name

    # Replace problematic characters with underscore
    # Allowed: alphanumeric, hyphen, underscore, space
    basename = re.sub(r"[^\w\s\-]", "_", basename)

    # Collapse multiple underscores/spaces
    basename = re.sub(r"[_\s]+", "_", basename)

    # Remove leading/trailing underscores and spaces
    basename = basename.strip("_").strip()

    # If basename is empty after sanitization, use fallback
    if not basename:
        basename = "attachment"

    # Truncate basename to fit max_length (leave room for extension)
    max_basename_length = max_length - len(extension) - 1
    if len(basename) > max_basename_length:
        basename = basename[:max_basename_length]

    # Reconstruct filename
    sanitized = f"{basename}{extension}"

    if sanitized != original_filename:
        logger.info(
            "filename_sanitized",
            original=original_filename,
            sanitized=sanitized,
        )

    return sanitized


def prepare_file_for_storage(
    file_content: bytes,
    filename: str,
    file_type: FileType,
    strip_metadata: bool = True,
) -> tuple[bytes, str]:
    """
    Prepare uploaded file for secure storage.

    Applies sanitization pipeline:
    1. Strip EXIF metadata from images (if enabled)
    2. Sanitize filename

    Args:
        file_content: Raw file bytes
        filename: Original filename
        file_type: Validated FileType
        strip_metadata: Whether to strip EXIF metadata (default: True)

    Returns:
        Tuple of (sanitized_bytes, sanitized_filename)

    Example:
        ```python
        sanitized_bytes, safe_filename = prepare_file_for_storage(
            file_content=upload.file.read(),
            filename=upload.filename,
            file_type=FileType.JPEG,
        )
        ```
    """
    logger.info(
        "file_storage_preparation_started",
        filename=filename,
        file_type=file_type.value,
        strip_metadata=strip_metadata,
    )

    # Sanitize filename
    safe_filename = sanitize_filename(filename)

    # Strip metadata if enabled and supported
    if strip_metadata:
        sanitized_content = strip_exif_metadata(file_content, file_type, filename)
    else:
        sanitized_content = file_content
        logger.debug("metadata_stripping_disabled", filename=filename)

    logger.info(
        "file_storage_preparation_completed",
        original_filename=filename,
        safe_filename=safe_filename,
        original_size=len(file_content),
        final_size=len(sanitized_content),
    )

    return sanitized_content, safe_filename
