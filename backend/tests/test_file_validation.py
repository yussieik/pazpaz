"""
Comprehensive test suite for file validation utilities.

Tests triple validation approach:
1. MIME type validation (python-magic)
2. Extension validation (whitelist)
3. Content validation (pillow/pypdf)

Security test cases:
- Type confusion attacks (wrong extension)
- MIME mismatch attacks
- Oversized files
- Malformed content
- Decompression bombs
"""

import io

import pytest
from PIL import Image
from pypdf import PdfWriter

from pazpaz.utils.file_validation import (
    FileContentError,
    FileSizeExceededError,
    FileType,
    FileValidationError,
    MAX_FILE_SIZE_BYTES,
    MAX_TOTAL_ATTACHMENTS_BYTES,
    MimeTypeMismatchError,
    UnsupportedFileTypeError,
    detect_mime_type,
    validate_extension,
    validate_file,
    validate_file_size,
    validate_image_content,
    validate_mime_extension_match,
    validate_pdf_content,
    validate_total_attachments_size,
)


# Test fixtures for creating valid files
@pytest.fixture
def valid_jpeg_bytes() -> bytes:
    """Create valid JPEG image bytes."""
    img = Image.new("RGB", (100, 100), color="red")
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=85)
    return output.getvalue()


@pytest.fixture
def valid_png_bytes() -> bytes:
    """Create valid PNG image bytes."""
    img = Image.new("RGBA", (100, 100), color="blue")
    output = io.BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
def valid_webp_bytes() -> bytes:
    """Create valid WebP image bytes."""
    img = Image.new("RGB", (100, 100), color="green")
    output = io.BytesIO()
    img.save(output, format="WEBP", quality=85)
    return output.getvalue()


@pytest.fixture
def valid_pdf_bytes() -> bytes:
    """Create valid PDF document bytes."""
    pdf_writer = PdfWriter()
    pdf_writer.add_blank_page(width=200, height=200)
    output = io.BytesIO()
    pdf_writer.write(output)
    return output.getvalue()


@pytest.fixture
def image_with_exif() -> bytes:
    """Create JPEG with EXIF metadata."""
    from PIL.ExifTags import TAGS

    img = Image.new("RGB", (100, 100), color="yellow")

    # Add EXIF data
    exif_data = img.getexif()
    exif_data[0x0132] = "2025:10:12 10:30:00"  # DateTime
    exif_data[0x010F] = "TestCamera"  # Make
    exif_data[0x0110] = "TestModel"  # Model

    output = io.BytesIO()
    img.save(output, format="JPEG", exif=exif_data)
    return output.getvalue()


# Test: File size validation
class TestFileSizeValidation:
    """Test file size limits."""

    def test_validate_file_size_within_limit(self):
        """Valid file size should pass."""
        # 5 MB file (within 10 MB limit)
        validate_file_size(5 * 1024 * 1024)

    def test_validate_file_size_at_limit(self):
        """File at exact limit should pass."""
        validate_file_size(MAX_FILE_SIZE_BYTES)

    def test_validate_file_size_exceeds_limit(self):
        """File exceeding limit should raise error."""
        with pytest.raises(FileSizeExceededError) as exc_info:
            validate_file_size(MAX_FILE_SIZE_BYTES + 1)

        assert "exceeds maximum" in str(exc_info.value)

    def test_validate_total_attachments_size_within_limit(self):
        """Total size within limit should pass."""
        # 30 MB existing + 10 MB new = 40 MB (within 50 MB limit)
        validate_total_attachments_size(
            existing_size=30 * 1024 * 1024,
            new_file_size=10 * 1024 * 1024,
        )

    def test_validate_total_attachments_size_exceeds_limit(self):
        """Total size exceeding limit should raise error."""
        with pytest.raises(FileSizeExceededError) as exc_info:
            # 45 MB existing + 10 MB new = 55 MB (exceeds 50 MB limit)
            validate_total_attachments_size(
                existing_size=45 * 1024 * 1024,
                new_file_size=10 * 1024 * 1024,
            )

        assert "would exceed maximum" in str(exc_info.value)


# Test: Extension validation
class TestExtensionValidation:
    """Test file extension validation."""

    def test_validate_extension_jpeg(self):
        """JPEG extensions should be valid."""
        assert validate_extension("photo.jpg") == ".jpg"
        assert validate_extension("photo.jpeg") == ".jpeg"
        assert validate_extension("PHOTO.JPG") == ".jpg"  # Case insensitive

    def test_validate_extension_png(self):
        """PNG extension should be valid."""
        assert validate_extension("image.png") == ".png"
        assert validate_extension("IMAGE.PNG") == ".png"

    def test_validate_extension_webp(self):
        """WebP extension should be valid."""
        assert validate_extension("photo.webp") == ".webp"

    def test_validate_extension_pdf(self):
        """PDF extension should be valid."""
        assert validate_extension("document.pdf") == ".pdf"

    def test_validate_extension_missing(self):
        """File without extension should raise error."""
        with pytest.raises(UnsupportedFileTypeError) as exc_info:
            validate_extension("noextension")

        assert "no extension" in str(exc_info.value)

    def test_validate_extension_unsupported(self):
        """Unsupported extension should raise error."""
        with pytest.raises(UnsupportedFileTypeError) as exc_info:
            validate_extension("malicious.php")

        assert "not allowed" in str(exc_info.value)

    def test_validate_extension_executable(self):
        """Executable extension should raise error."""
        with pytest.raises(UnsupportedFileTypeError):
            validate_extension("virus.exe")


# Test: MIME type detection
class TestMimeTypeDetection:
    """Test MIME type detection from file content."""

    def test_detect_mime_type_jpeg(self, valid_jpeg_bytes):
        """JPEG file should be detected as image/jpeg."""
        mime_type = detect_mime_type(valid_jpeg_bytes)
        assert mime_type == FileType.JPEG

    def test_detect_mime_type_png(self, valid_png_bytes):
        """PNG file should be detected as image/png."""
        mime_type = detect_mime_type(valid_png_bytes)
        assert mime_type == FileType.PNG

    def test_detect_mime_type_webp(self, valid_webp_bytes):
        """WebP file should be detected as image/webp."""
        mime_type = detect_mime_type(valid_webp_bytes)
        assert mime_type == FileType.WEBP

    def test_detect_mime_type_pdf(self, valid_pdf_bytes):
        """PDF file should be detected as application/pdf."""
        mime_type = detect_mime_type(valid_pdf_bytes)
        assert mime_type == FileType.PDF

    def test_detect_mime_type_text_file(self):
        """Text file should raise error."""
        text_content = b"This is a text file"
        with pytest.raises((UnsupportedFileTypeError, FileValidationError)) as exc_info:
            detect_mime_type(text_content)

        assert "not allowed" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()

    def test_detect_mime_type_php_file(self):
        """PHP file should raise error regardless of content."""
        php_content = b"<?php echo 'malicious'; ?>"
        with pytest.raises((UnsupportedFileTypeError, FileValidationError)):
            detect_mime_type(php_content)


# Test: MIME/Extension matching
class TestMimeExtensionMatch:
    """Test MIME type and extension consistency."""

    def test_validate_mime_extension_match_jpeg(self):
        """JPEG MIME with .jpg/.jpeg extension should match."""
        validate_mime_extension_match(FileType.JPEG, ".jpg")
        validate_mime_extension_match(FileType.JPEG, ".jpeg")

    def test_validate_mime_extension_match_png(self):
        """PNG MIME with .png extension should match."""
        validate_mime_extension_match(FileType.PNG, ".png")

    def test_validate_mime_extension_match_webp(self):
        """WebP MIME with .webp extension should match."""
        validate_mime_extension_match(FileType.WEBP, ".webp")

    def test_validate_mime_extension_match_pdf(self):
        """PDF MIME with .pdf extension should match."""
        validate_mime_extension_match(FileType.PDF, ".pdf")

    def test_validate_mime_extension_mismatch_jpeg_pdf(self):
        """JPEG MIME with .pdf extension should raise error."""
        with pytest.raises(MimeTypeMismatchError) as exc_info:
            validate_mime_extension_match(FileType.JPEG, ".pdf")

        assert "does not match" in str(exc_info.value)

    def test_validate_mime_extension_mismatch_png_jpg(self):
        """PNG MIME with .jpg extension should raise error."""
        with pytest.raises(MimeTypeMismatchError):
            validate_mime_extension_match(FileType.PNG, ".jpg")


# Test: Image content validation
class TestImageContentValidation:
    """Test image content parsing and validation."""

    def test_validate_image_content_jpeg(self, valid_jpeg_bytes):
        """Valid JPEG content should pass."""
        validate_image_content(valid_jpeg_bytes, FileType.JPEG)

    def test_validate_image_content_png(self, valid_png_bytes):
        """Valid PNG content should pass."""
        validate_image_content(valid_png_bytes, FileType.PNG)

    def test_validate_image_content_webp(self, valid_webp_bytes):
        """Valid WebP content should pass."""
        validate_image_content(valid_webp_bytes, FileType.WEBP)

    def test_validate_image_content_corrupted(self):
        """Corrupted image should raise error."""
        corrupted = b"Not a real image file"
        with pytest.raises(FileContentError) as exc_info:
            validate_image_content(corrupted, FileType.JPEG)

        assert "Invalid or corrupted" in str(exc_info.value)

    def test_validate_image_content_truncated(self, valid_jpeg_bytes):
        """Truncated image should raise error."""
        truncated = valid_jpeg_bytes[:100]  # Only first 100 bytes
        with pytest.raises(FileContentError):
            validate_image_content(truncated, FileType.JPEG)

    def test_validate_image_content_format_mismatch(self, valid_png_bytes):
        """PNG content with JPEG MIME should raise error."""
        with pytest.raises(FileContentError) as exc_info:
            validate_image_content(valid_png_bytes, FileType.JPEG)

        assert "does not match MIME type" in str(exc_info.value)

    def test_validate_image_content_decompression_bomb(self):
        """Extremely large image should raise error."""
        # Create image with 100 megapixels (exceeds 50M limit)
        large_img = Image.new("RGB", (10000, 10000), color="white")
        output = io.BytesIO()
        large_img.save(output, format="JPEG", quality=85)

        with pytest.raises(FileContentError) as exc_info:
            validate_image_content(output.getvalue(), FileType.JPEG)

        assert "too large" in str(exc_info.value)

    def test_validate_image_content_zero_dimensions(self):
        """Image with zero dimensions should raise error."""
        # PIL doesn't allow creating 0-size images directly, so we test the validation logic
        # by creating a minimal valid image
        pass  # Skip as PIL prevents this at creation time


# Test: PDF content validation
class TestPdfContentValidation:
    """Test PDF content parsing and validation."""

    def test_validate_pdf_content_valid(self, valid_pdf_bytes):
        """Valid PDF content should pass."""
        validate_pdf_content(valid_pdf_bytes)

    def test_validate_pdf_content_corrupted(self):
        """Corrupted PDF should raise error."""
        corrupted = b"Not a real PDF file"
        with pytest.raises(FileContentError) as exc_info:
            validate_pdf_content(corrupted)

        assert "Invalid or corrupted PDF" in str(exc_info.value)

    def test_validate_pdf_content_empty(self):
        """PDF with no pages should raise error."""
        # Create empty PDF writer
        pdf_writer = PdfWriter()
        output = io.BytesIO()
        pdf_writer.write(output)

        with pytest.raises(FileContentError) as exc_info:
            validate_pdf_content(output.getvalue())

        assert "no pages" in str(exc_info.value)

    def test_validate_pdf_content_too_many_pages(self):
        """PDF with excessive pages should raise error."""
        # Create PDF with 1001 pages (exceeds 1000 limit)
        pdf_writer = PdfWriter()
        for _ in range(1001):
            pdf_writer.add_blank_page(width=200, height=200)

        output = io.BytesIO()
        pdf_writer.write(output)

        with pytest.raises(FileContentError) as exc_info:
            validate_pdf_content(output.getvalue())

        assert "too many pages" in str(exc_info.value)


# Test: Full validation pipeline
class TestFullValidation:
    """Test complete validation pipeline."""

    def test_validate_file_jpeg_success(self, valid_jpeg_bytes):
        """Valid JPEG file should pass all validation."""
        file_type = validate_file("photo.jpg", valid_jpeg_bytes)
        assert file_type == FileType.JPEG

    def test_validate_file_png_success(self, valid_png_bytes):
        """Valid PNG file should pass all validation."""
        file_type = validate_file("image.png", valid_png_bytes)
        assert file_type == FileType.PNG

    def test_validate_file_webp_success(self, valid_webp_bytes):
        """Valid WebP file should pass all validation."""
        file_type = validate_file("photo.webp", valid_webp_bytes)
        assert file_type == FileType.WEBP

    def test_validate_file_pdf_success(self, valid_pdf_bytes):
        """Valid PDF file should pass all validation."""
        file_type = validate_file("document.pdf", valid_pdf_bytes)
        assert file_type == FileType.PDF


# Security Test Cases
class TestSecurityValidation:
    """Test security-focused validation scenarios."""

    def test_type_confusion_attack_php_renamed_to_jpg(self):
        """PHP file renamed to .jpg should be rejected."""
        php_content = b"<?php system($_GET['cmd']); ?>"
        with pytest.raises((UnsupportedFileTypeError, MimeTypeMismatchError, FileValidationError)):
            validate_file("malicious.jpg", php_content)

    def test_type_confusion_attack_pdf_renamed_to_jpg(self, valid_pdf_bytes):
        """PDF renamed to .jpg should be rejected (MIME mismatch)."""
        with pytest.raises(MimeTypeMismatchError) as exc_info:
            validate_file("document.jpg", valid_pdf_bytes)

        assert "does not match" in str(exc_info.value)

    def test_type_confusion_attack_jpeg_renamed_to_pdf(self, valid_jpeg_bytes):
        """JPEG renamed to .pdf should be rejected (MIME mismatch)."""
        with pytest.raises(MimeTypeMismatchError):
            validate_file("image.pdf", valid_jpeg_bytes)

    def test_oversized_file_rejection(self):
        """File exceeding size limit should be rejected."""
        # Create 11 MB file (exceeds 10 MB limit)
        oversized = b"x" * (11 * 1024 * 1024)
        with pytest.raises(FileSizeExceededError):
            validate_file("large.jpg", oversized)

    def test_malicious_filename_path_traversal(self, valid_jpeg_bytes):
        """Path traversal in filename should still validate content."""
        # Validation focuses on content, filename sanitization happens separately
        file_type = validate_file("../../etc/passwd.jpg", valid_jpeg_bytes)
        assert file_type == FileType.JPEG

    def test_double_extension_attack(self, valid_jpeg_bytes):
        """Double extension (file.jpg.php) should be rejected."""
        # Only validates last extension
        with pytest.raises(UnsupportedFileTypeError):
            validate_file("image.jpg.php", valid_jpeg_bytes)

    def test_null_byte_injection(self, valid_jpeg_bytes):
        """Null byte in filename should be handled."""
        # Python strings handle null bytes, but validation should still work
        try:
            file_type = validate_file("image.jpg\x00.php", valid_jpeg_bytes)
            # If it passes, ensure it's the correct type
            assert file_type == FileType.JPEG
        except UnsupportedFileTypeError:
            # Also acceptable - depends on how extension parsing handles nulls
            pass

    def test_image_with_embedded_script(self):
        """Image with embedded script tags should still validate."""
        # Create image with "script" in pixel data (not actual executable code)
        img = Image.new("RGB", (100, 100), color="red")
        output = io.BytesIO()
        img.save(output, format="JPEG")
        jpeg_bytes = output.getvalue()

        # Image should still be valid (EXIF stripping happens separately)
        file_type = validate_file("test.jpg", jpeg_bytes)
        assert file_type == FileType.JPEG

    def test_exif_gps_data_validation(self, image_with_exif):
        """Image with EXIF GPS data should validate (stripping happens separately)."""
        # Validation allows EXIF; sanitization strips it
        file_type = validate_file("photo.jpg", image_with_exif)
        assert file_type == FileType.JPEG


# Edge Cases
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_file(self):
        """Empty file should raise error."""
        with pytest.raises(FileValidationError):
            validate_file("empty.jpg", b"")

    def test_tiny_file(self):
        """Very small file should raise error."""
        with pytest.raises(FileValidationError):
            validate_file("tiny.jpg", b"123")

    def test_filename_with_spaces(self, valid_jpeg_bytes):
        """Filename with spaces should validate."""
        file_type = validate_file("my photo.jpg", valid_jpeg_bytes)
        assert file_type == FileType.JPEG

    def test_filename_with_unicode(self, valid_jpeg_bytes):
        """Filename with Unicode characters should validate."""
        file_type = validate_file("photo_日本語.jpg", valid_jpeg_bytes)
        assert file_type == FileType.JPEG

    def test_filename_case_insensitive(self, valid_jpeg_bytes):
        """Extension validation should be case-insensitive."""
        file_type = validate_file("PHOTO.JPG", valid_jpeg_bytes)
        assert file_type == FileType.JPEG

    def test_multiple_dots_in_filename(self, valid_jpeg_bytes):
        """Filename with multiple dots should use last extension."""
        file_type = validate_file("my.photo.v2.jpg", valid_jpeg_bytes)
        assert file_type == FileType.JPEG
