"""File upload validation utilities with defense-in-depth approach.

This module implements quadruple validation for uploaded files:
1. MIME type validation (reads file header with python-magic)
2. Extension validation (whitelist-based)
3. Content validation (pillow for images, pypdf for PDFs)
4. Malware scanning (ClamAV antivirus)

Security principles:
- Fail closed: Reject on any validation error
- Defense in depth: Multiple validation layers
- Type confusion prevention: Verify MIME matches extension
- Content scanning: Validate file can be parsed safely
- Malware detection: ClamAV scans for known malware signatures

Supported file types (HIPAA-compliant clinical documentation):
- Images: JPEG, PNG, WebP (for wound photos, treatment documentation)
- Documents: PDF (for lab reports, referrals, consent forms)
- Audio: MP3, M4A, WAV, OGG, FLAC, WebM (for voice transcription of SOAP notes)
"""

from __future__ import annotations

import io
from enum import Enum
from pathlib import Path

import magic
from PIL import Image
from pypdf import PdfReader

from pazpaz.core.logging import get_logger
from pazpaz.utils.malware_scanner import scan_file_for_malware

logger = get_logger(__name__)


class FileType(str, Enum):
    """Allowed file types for session attachments and voice transcription."""

    # Images (session attachments)
    JPEG = "image/jpeg"
    PNG = "image/png"
    WEBP = "image/webp"

    # Documents (session attachments)
    PDF = "application/pdf"

    # Audio (voice transcription)
    MP3 = "audio/mpeg"
    M4A = "audio/mp4"
    WAV = "audio/wav"
    OGG = "audio/ogg"
    FLAC = "audio/flac"
    WEBM = "audio/webm"


class FileValidationError(Exception):
    """Base exception for file validation errors."""

    pass


class MimeTypeMismatchError(FileValidationError):
    """MIME type doesn't match extension."""

    pass


class UnsupportedFileTypeError(FileValidationError):
    """File type not in whitelist."""

    pass


class FileSizeExceededError(FileValidationError):
    """File size exceeds limits."""

    pass


class FileContentError(FileValidationError):
    """File content validation failed."""

    pass


# File size limits (bytes)
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB per file
MAX_TOTAL_ATTACHMENTS_BYTES = 50 * 1024 * 1024  # 50 MB per session

# MIME type to extension mapping (whitelist)
ALLOWED_MIME_TYPES = {
    # Images
    FileType.JPEG: {".jpg", ".jpeg"},
    FileType.PNG: {".png"},
    FileType.WEBP: {".webp"},
    # Documents
    FileType.PDF: {".pdf"},
    # Audio
    FileType.MP3: {".mp3"},
    FileType.M4A: {".m4a"},
    FileType.WAV: {".wav"},
    FileType.OGG: {".ogg", ".oga"},
    FileType.FLAC: {".flac"},
    FileType.WEBM: {".webm"},
}

# Extension to MIME type mapping (reverse lookup)
ALLOWED_EXTENSIONS = {}
for mime_type, extensions in ALLOWED_MIME_TYPES.items():
    for ext in extensions:
        ALLOWED_EXTENSIONS[ext] = mime_type

# FileType to file extension mapping (for S3 keys, sanitization)
FILE_TYPE_TO_EXTENSION = {
    # Images
    FileType.JPEG: "jpg",
    FileType.PNG: "png",
    FileType.WEBP: "webp",
    # Documents
    FileType.PDF: "pdf",
    # Audio
    FileType.MP3: "mp3",
    FileType.M4A: "m4a",
    FileType.WAV: "wav",
    FileType.OGG: "ogg",
    FileType.FLAC: "flac",
    FileType.WEBM: "webm",
}

# FileType to PIL format name mapping (for image processing)
FILE_TYPE_TO_PIL_FORMAT = {
    FileType.JPEG: "JPEG",
    FileType.PNG: "PNG",
    FileType.WEBP: "WEBP",
}


def validate_file_size(file_size: int) -> None:
    """
    Validate file size against maximum limit.

    Args:
        file_size: File size in bytes

    Raises:
        FileSizeExceededError: If file exceeds maximum size
    """
    if file_size > MAX_FILE_SIZE_BYTES:
        logger.warning(
            "file_size_exceeded",
            file_size=file_size,
            max_size=MAX_FILE_SIZE_BYTES,
        )
        raise FileSizeExceededError(
            f"File size {file_size} bytes exceeds maximum of "
            f"{MAX_FILE_SIZE_BYTES} bytes ({MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB)"
        )

    logger.debug("file_size_validated", file_size=file_size)


def validate_total_attachments_size(existing_size: int, new_file_size: int) -> None:
    """
    Validate total attachment size for a session.

    Args:
        existing_size: Sum of existing attachment sizes (bytes)
        new_file_size: Size of new file being uploaded (bytes)

    Raises:
        FileSizeExceededError: If total exceeds maximum
    """
    total_size = existing_size + new_file_size

    if total_size > MAX_TOTAL_ATTACHMENTS_BYTES:
        logger.warning(
            "total_attachments_size_exceeded",
            existing_size=existing_size,
            new_file_size=new_file_size,
            total_size=total_size,
            max_total=MAX_TOTAL_ATTACHMENTS_BYTES,
        )
        raise FileSizeExceededError(
            f"Total attachments size {total_size} bytes would exceed maximum of "
            f"{MAX_TOTAL_ATTACHMENTS_BYTES} bytes "
            f"({MAX_TOTAL_ATTACHMENTS_BYTES // (1024 * 1024)} MB)"
        )

    logger.debug(
        "total_attachments_size_validated",
        existing_size=existing_size,
        new_file_size=new_file_size,
        total_size=total_size,
    )


def validate_extension(filename: str) -> str:
    """
    Validate file extension against whitelist.

    Args:
        filename: Original filename from upload

    Returns:
        Normalized extension (lowercase with dot)

    Raises:
        UnsupportedFileTypeError: If extension not in whitelist
    """
    # Extract extension (case-insensitive)
    extension = Path(filename).suffix.lower()

    if not extension:
        logger.warning("file_validation_no_extension", filename=filename)
        raise UnsupportedFileTypeError("File has no extension")

    if extension not in ALLOWED_EXTENSIONS:
        logger.warning(
            "file_validation_unsupported_extension",
            filename=filename,
            extension=extension,
            allowed=list(ALLOWED_EXTENSIONS.keys()),
        )
        raise UnsupportedFileTypeError(
            f"File extension {extension} not allowed. "
            f"Allowed types: {', '.join(ALLOWED_EXTENSIONS.keys())}"
        )

    logger.debug("extension_validated", extension=extension)
    return extension


def detect_mime_type(file_content: bytes) -> FileType:
    """
    Detect MIME type from file header using python-magic.

    Uses libmagic to read file headers and detect actual file type,
    regardless of extension.

    Args:
        file_content: Raw file bytes

    Returns:
        Detected FileType

    Raises:
        UnsupportedFileTypeError: If MIME type not in whitelist
    """
    try:
        # Use magic to detect MIME type from content
        mime_type = magic.from_buffer(file_content, mime=True)

        # Normalize MIME type
        mime_type = mime_type.lower().strip()

        logger.debug("mime_type_detected", mime_type=mime_type)

        # Map to FileType enum
        for file_type in FileType:
            if file_type.value == mime_type:
                return file_type

        # Not in whitelist
        logger.warning(
            "file_validation_unsupported_mime_type",
            mime_type=mime_type,
            allowed=[ft.value for ft in FileType],
        )
        raise UnsupportedFileTypeError(
            f"MIME type {mime_type} not allowed. "
            f"Allowed types: {', '.join([ft.value for ft in FileType])}"
        )

    except Exception as e:
        logger.error(
            "mime_type_detection_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise FileValidationError(f"Failed to detect file type: {e}") from e


def validate_mime_extension_match(detected_mime: FileType, extension: str) -> None:
    """
    Validate that detected MIME type matches the file extension.

    Prevents type confusion attacks (e.g., PHP file renamed to .jpg).

    Args:
        detected_mime: MIME type detected from file header
        extension: File extension (lowercase with dot)

    Raises:
        MimeTypeMismatchError: If MIME and extension don't match
    """
    allowed_extensions = ALLOWED_MIME_TYPES.get(detected_mime, set())

    if extension not in allowed_extensions:
        logger.warning(
            "mime_extension_mismatch",
            detected_mime=detected_mime.value,
            extension=extension,
            expected_extensions=list(allowed_extensions),
        )
        raise MimeTypeMismatchError(
            f"File extension {extension} does not match detected MIME type "
            f"{detected_mime.value}. Expected extensions: "
            f"{', '.join(allowed_extensions)}"
        )

    logger.debug(
        "mime_extension_match_validated",
        mime_type=detected_mime.value,
        extension=extension,
    )


def detect_polyglot_patterns(file_content: bytes) -> None:
    """
    Detect polyglot file patterns (valid image + embedded scripts).

    A polyglot file is a valid file in multiple formats simultaneously.
    For example, a JPEG that also contains valid PHP or HTML code.

    This is a CRITICAL security check when ClamAV is unavailable, as polyglot
    files can bypass basic MIME type and extension validation.

    Attack Scenario:
    1. Attacker creates valid JPEG image
    2. Appends PHP/HTML script after JPEG end marker (FFD9)
    3. File passes MIME validation (valid JPEG header)
    4. File passes content validation (PIL can parse it)
    5. If served by misconfigured server, script executes

    Detection Strategy:
    - Check for executable code markers after image data
    - Look for PHP tags: <?php, <?, <?=
    - Look for HTML script tags: <script>, <html>
    - Look for shell commands: #!/bin/sh, #!/usr/bin/env
    - Check for trailing executable content after image end markers

    Args:
        file_content: Raw file bytes to scan

    Raises:
        FileContentError: If polyglot patterns detected

    Security Note:
    This is a basic polyglot detector for defense-in-depth when ClamAV
    is unavailable (development mode). It catches common patterns but is
    NOT a replacement for proper malware scanning. In production, ClamAV
    MUST be available (enforced by fail-closed policy).
    """
    # Patterns to detect in file content (case-insensitive)
    # These indicate embedded executable code
    dangerous_patterns = [
        b"<?php",  # PHP opening tag
        b"<? ",  # PHP short tag with space
        b"<?=",  # PHP echo short tag
        b"<script",  # HTML/JS script tag
        b"<html",  # HTML document
        b"#!/bin/sh",  # Shell script shebang
        b"#!/bin/bash",  # Bash script shebang
        b"#!/usr/bin/env",  # Generic script shebang
        b"eval(",  # JavaScript/Python eval (common in exploits)
        b"exec(",  # PHP/Python exec (command execution)
        b"system(",  # PHP system() call
        b"passthru(",  # PHP passthru() call
        b"shell_exec(",  # PHP shell_exec() call
    ]

    # Convert content to lowercase for case-insensitive matching
    content_lower = file_content.lower()

    # Check for dangerous patterns
    for pattern in dangerous_patterns:
        if pattern in content_lower:
            # Found suspicious pattern - reject file
            logger.warning(
                "polyglot_pattern_detected",
                pattern=pattern.decode("utf-8", errors="replace"),
                file_size=len(file_content),
                reason="Embedded executable code detected in image file",
            )
            raise FileContentError(
                "File contains suspicious pattern that may indicate a polyglot attack. "
                "Upload rejected for security."
            )

    # Additional check: Look for trailing data after JPEG end marker
    # JPEG files end with FFD9 marker - anything after is suspicious
    if file_content.startswith(b"\xff\xd8"):  # JPEG magic bytes
        # Find last occurrence of JPEG end marker
        jpeg_end_marker = b"\xff\xd9"
        last_marker_pos = file_content.rfind(jpeg_end_marker)

        if last_marker_pos != -1:
            # Check if there's significant data after the end marker
            trailing_data = file_content[last_marker_pos + 2 :]
            # Allow up to 100 bytes of trailing data (metadata, thumbnails)
            # But reject files with large trailing sections (likely polyglot)
            if len(trailing_data) > 100:
                logger.warning(
                    "suspicious_trailing_data_in_jpeg",
                    trailing_bytes=len(trailing_data),
                    file_size=len(file_content),
                    reason="JPEG has large trailing data after end marker (possible polyglot)",
                )
                raise FileContentError(
                    f"Image file has {len(trailing_data)} bytes of trailing data after "
                    f"end marker. This may indicate a polyglot attack. Upload rejected for security."
                )

    logger.debug("polyglot_detection_passed", file_size=len(file_content))


def validate_image_content(file_content: bytes, mime_type: FileType) -> None:
    """
    Validate image file can be parsed safely by PIL.

    Ensures file is actually a valid image and not malicious content.

    Security Enhancements:
    - Basic polyglot detection (when ClamAV unavailable)
    - Format validation against declared MIME type
    - Dimension sanity checks
    - Decompression bomb prevention

    Args:
        file_content: Raw file bytes
        mime_type: Detected MIME type

    Raises:
        FileContentError: If image cannot be parsed or is corrupted
    """
    try:
        # SECURITY: Check for polyglot patterns before PIL validation
        # This catches images with embedded scripts (PHP, HTML, shell)
        detect_polyglot_patterns(file_content)

        # Open image with PIL
        img = Image.open(io.BytesIO(file_content))

        # Verify image can be loaded (triggers decompression)
        img.verify()

        # Re-open after verify() (verify closes the file)
        img = Image.open(io.BytesIO(file_content))

        # Check image format matches MIME type
        expected_format = FILE_TYPE_TO_PIL_FORMAT.get(mime_type)

        if img.format != expected_format:
            logger.warning(
                "image_format_mismatch",
                expected=expected_format,
                actual=img.format,
                mime_type=mime_type.value,
            )
            raise FileContentError(
                f"Image format {img.format} does not match MIME type {mime_type.value}"
            )

        # Basic sanity checks
        if img.size[0] <= 0 or img.size[1] <= 0:
            logger.warning("invalid_image_dimensions", size=img.size)
            raise FileContentError("Image has invalid dimensions")

        # Check for reasonable image size (prevent decompression bombs)
        # Max 50 megapixels (e.g., 7071x7071 or 10000x5000)
        max_pixels = 50_000_000
        total_pixels = img.size[0] * img.size[1]
        if total_pixels > max_pixels:
            logger.warning(
                "image_too_large",
                width=img.size[0],
                height=img.size[1],
                total_pixels=total_pixels,
                max_pixels=max_pixels,
            )
            raise FileContentError(
                f"Image resolution too large ({img.size[0]}x{img.size[1]}). "
                f"Maximum {max_pixels} pixels"
            )

        logger.debug(
            "image_content_validated",
            format=img.format,
            size=img.size,
            mode=img.mode,
        )

    except FileContentError:
        # Re-raise our own exceptions
        raise
    except Exception as e:
        logger.warning(
            "image_validation_failed",
            error=str(e),
            error_type=type(e).__name__,
            mime_type=mime_type.value,
        )
        raise FileContentError(f"Invalid or corrupted image file: {e}") from e


def validate_pdf_content(file_content: bytes) -> None:
    """
    Validate PDF file can be parsed safely by pypdf.

    Ensures file is actually a valid PDF and not malicious content.

    Args:
        file_content: Raw file bytes

    Raises:
        FileContentError: If PDF cannot be parsed or is corrupted
    """
    try:
        # Parse PDF with pypdf
        pdf_reader = PdfReader(io.BytesIO(file_content))

        # Check PDF is not empty
        if len(pdf_reader.pages) == 0:
            logger.warning("pdf_no_pages")
            raise FileContentError("PDF has no pages")

        # Check reasonable page count (prevent resource exhaustion)
        max_pages = 1000
        if len(pdf_reader.pages) > max_pages:
            logger.warning(
                "pdf_too_many_pages",
                page_count=len(pdf_reader.pages),
                max_pages=max_pages,
            )
            raise FileContentError(
                f"PDF has too many pages ({len(pdf_reader.pages)}). "
                f"Maximum {max_pages} pages"
            )

        # Try to read first page (validates structure)
        try:
            _first_page = pdf_reader.pages[0]
        except Exception as e:
            logger.warning("pdf_first_page_read_failed", error=str(e))
            raise FileContentError(f"Cannot read PDF pages: {e}") from e

        logger.debug(
            "pdf_content_validated",
            page_count=len(pdf_reader.pages),
        )

    except FileContentError:
        # Re-raise our own exceptions
        raise
    except Exception as e:
        logger.warning(
            "pdf_validation_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise FileContentError(f"Invalid or corrupted PDF file: {e}") from e


def validate_audio_content(file_content: bytes, mime_type: FileType) -> None:
    """
    Validate audio file metadata and duration.

    Ensures audio file is valid and meets duration requirements for
    voice transcription (max 5 minutes to prevent abuse).

    Security considerations:
    - No malware scanning on audio content (ClamAV handles this)
    - Duration validation prevents resource exhaustion attacks
    - Metadata validation ensures file is parseable

    Args:
        file_content: Raw file bytes
        mime_type: Detected MIME type

    Raises:
        FileContentError: If audio cannot be parsed, is corrupted, or exceeds duration limit
    """
    try:
        import mutagen

        # Parse audio file with mutagen
        audio_file = mutagen.File(io.BytesIO(file_content))

        if audio_file is None:
            logger.warning(
                "audio_validation_no_metadata",
                mime_type=mime_type.value,
            )
            raise FileContentError(
                "Audio file has no readable metadata. File may be corrupted."
            )

        # Get audio duration (in seconds)
        duration = getattr(audio_file.info, "length", None)

        if duration is None:
            logger.warning(
                "audio_validation_no_duration",
                mime_type=mime_type.value,
            )
            # Duration not available - allow file but log warning
            # Some valid audio files may not have duration in metadata
            logger.debug(
                "audio_duration_unavailable",
                mime_type=mime_type.value,
                message="Duration not in metadata, skipping duration check",
            )
            return

        # Check maximum duration (5 minutes = 300 seconds)
        max_duration_seconds = 300
        if duration > max_duration_seconds:
            logger.warning(
                "audio_duration_exceeded",
                duration=duration,
                max_duration=max_duration_seconds,
                mime_type=mime_type.value,
            )
            raise FileContentError(
                f"Audio duration {duration:.1f} seconds exceeds maximum of "
                f"{max_duration_seconds} seconds (5 minutes)"
            )

        # Check minimum duration (2 seconds - reject accidental clicks)
        min_duration_seconds = 2
        if duration < min_duration_seconds:
            logger.warning(
                "audio_duration_too_short",
                duration=duration,
                min_duration=min_duration_seconds,
                mime_type=mime_type.value,
            )
            raise FileContentError(
                f"Audio duration {duration:.1f} seconds is too short. "
                f"Minimum {min_duration_seconds} seconds required."
            )

        logger.debug(
            "audio_content_validated",
            mime_type=mime_type.value,
            duration=duration,
            bitrate=getattr(audio_file.info, "bitrate", None),
            sample_rate=getattr(audio_file.info, "sample_rate", None),
        )

    except FileContentError:
        # Re-raise our own exceptions
        raise
    except Exception as e:
        logger.warning(
            "audio_validation_failed",
            error=str(e),
            error_type=type(e).__name__,
            mime_type=mime_type.value,
        )
        raise FileContentError(f"Invalid or corrupted audio file: {e}") from e


def validate_file(filename: str, file_content: bytes) -> FileType:
    """
    Comprehensive file validation with quadruple-validation approach.

    Validation layers (all must pass):
    1. Extension validation (whitelist-based)
    2. MIME type detection (reads file header)
    3. MIME/extension match validation (prevents type confusion)
    4. Content validation (format-specific parsing)
    5. Malware scanning (ClamAV antivirus)

    Args:
        filename: Original filename from upload
        file_content: Raw file bytes

    Returns:
        Validated FileType

    Raises:
        FileValidationError: If any validation layer fails
        MalwareDetectedError: If file contains malware
        ScannerUnavailableError: If ClamAV unavailable (production/staging only)

    Example:
        ```python
        try:
            file_type = validate_file("photo.jpg", file_bytes)
            # File passed all validation checks including malware scan
        except FileValidationError as e:
            # Handle validation failure
            logger.warning("file_rejected", reason=str(e))
        except MalwareDetectedError as e:
            # Handle malware detection
            logger.error("malware_detected", reason=str(e))
        ```
    """
    logger.info("file_validation_started", filename=filename)

    # 1. Validate file size
    validate_file_size(len(file_content))

    # 2. Validate extension (whitelist)
    extension = validate_extension(filename)

    # 3. Detect MIME type from file header
    detected_mime = detect_mime_type(file_content)

    # 4. Validate MIME type matches extension
    validate_mime_extension_match(detected_mime, extension)

    # 5. Validate file content (format-specific)
    if detected_mime in (FileType.JPEG, FileType.PNG, FileType.WEBP):
        validate_image_content(file_content, detected_mime)
    elif detected_mime == FileType.PDF:
        validate_pdf_content(file_content)
    elif detected_mime in (
        FileType.MP3,
        FileType.M4A,
        FileType.WAV,
        FileType.OGG,
        FileType.FLAC,
        FileType.WEBM,
    ):
        validate_audio_content(file_content, detected_mime)

    # 6. Scan for malware (NEW: ClamAV integration)
    scan_file_for_malware(file_content, filename)

    logger.info(
        "file_validation_passed",
        filename=filename,
        mime_type=detected_mime.value,
        extension=extension,
        size_bytes=len(file_content),
    )

    return detected_mime
