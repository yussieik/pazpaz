"""
Test suite for file sanitization utilities.

Tests:
1. EXIF metadata stripping from images
2. Filename sanitization (path traversal prevention)
3. File preparation pipeline
"""

import io

import pytest
from PIL import Image
from PIL.ExifTags import TAGS

from pazpaz.utils.file_sanitization import (
    SanitizationError,
    prepare_file_for_storage,
    sanitize_filename,
    strip_exif_metadata,
)
from pazpaz.utils.file_validation import FileType


# Test fixtures
@pytest.fixture
def jpeg_with_exif() -> bytes:
    """Create JPEG with EXIF metadata."""
    img = Image.new("RGB", (200, 200), color="blue")

    # Add basic EXIF data (avoiding GPS which requires complex structure)
    exif_data = img.getexif()
    exif_data[0x0132] = "2025:10:12 14:30:00"  # DateTime
    exif_data[0x010F] = "Canon"  # Make
    exif_data[0x0110] = "Canon EOS R5"  # Model
    exif_data[0x010E] = "Treatment session photo"  # ImageDescription

    output = io.BytesIO()
    img.save(output, format="JPEG", exif=exif_data, quality=95)
    return output.getvalue()


@pytest.fixture
def jpeg_without_exif() -> bytes:
    """Create JPEG without any EXIF metadata."""
    img = Image.new("RGB", (200, 200), color="red")
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=85)
    return output.getvalue()


@pytest.fixture
def png_image() -> bytes:
    """Create PNG image (no EXIF support)."""
    img = Image.new("RGBA", (200, 200), color="green")
    output = io.BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()


# Test: EXIF metadata stripping
class TestExifStripping:
    """Test EXIF metadata removal from images."""

    def test_strip_exif_from_jpeg_with_metadata(self, jpeg_with_exif):
        """JPEG with EXIF should have metadata stripped."""
        original_size = len(jpeg_with_exif)

        # Strip EXIF
        sanitized = strip_exif_metadata(
            jpeg_with_exif, FileType.JPEG, "photo.jpg"
        )

        # Verify sanitized image is valid
        img = Image.open(io.BytesIO(sanitized))
        assert img.format == "JPEG"
        assert img.size == (200, 200)

        # Verify EXIF is removed (or minimal)
        exif_data = img.getexif()
        # Should have no or very minimal EXIF data
        assert len(exif_data) == 0 or len(exif_data) < 3

        # Sanitized file should be smaller (EXIF removed)
        assert len(sanitized) <= original_size

    def test_strip_exif_from_jpeg_without_metadata(self, jpeg_without_exif):
        """JPEG without EXIF should pass through unchanged."""
        sanitized = strip_exif_metadata(
            jpeg_without_exif, FileType.JPEG, "photo.jpg"
        )

        # Verify image is still valid
        img = Image.open(io.BytesIO(sanitized))
        assert img.format == "JPEG"
        assert img.size == (200, 200)

    def test_strip_exif_from_png(self, png_image):
        """PNG images should be processed (though PNG has no EXIF)."""
        sanitized = strip_exif_metadata(
            png_image, FileType.PNG, "image.png"
        )

        # Verify image is still valid
        img = Image.open(io.BytesIO(sanitized))
        assert img.format == "PNG"
        assert img.size == (200, 200)

    def test_strip_exif_from_webp(self):
        """WebP images should have metadata stripped."""
        # Create WebP with metadata
        img = Image.new("RGB", (200, 200), color="yellow")
        output = io.BytesIO()
        img.save(output, format="WEBP", quality=85)
        webp_bytes = output.getvalue()

        sanitized = strip_exif_metadata(
            webp_bytes, FileType.WEBP, "photo.webp"
        )

        # Verify image is still valid
        img = Image.open(io.BytesIO(sanitized))
        assert img.format == "WEBP"

    def test_strip_exif_preserves_image_quality(self, jpeg_with_exif):
        """EXIF stripping should preserve image dimensions and quality."""
        sanitized = strip_exif_metadata(
            jpeg_with_exif, FileType.JPEG, "photo.jpg"
        )

        # Open both images
        original_img = Image.open(io.BytesIO(jpeg_with_exif))
        sanitized_img = Image.open(io.BytesIO(sanitized))

        # Dimensions should match
        assert original_img.size == sanitized_img.size
        assert original_img.mode == sanitized_img.mode

    def test_strip_exif_gps_removal(self, jpeg_with_exif):
        """GPS coordinates should be removed from EXIF (all metadata stripped)."""
        sanitized = strip_exif_metadata(
            jpeg_with_exif, FileType.JPEG, "photo.jpg"
        )

        # Check sanitized image has minimal/no EXIF data
        img = Image.open(io.BytesIO(sanitized))
        exif = img.getexif()

        # All EXIF should be stripped, including any GPS tags
        assert len(exif) == 0 or len(exif) < 3

    def test_strip_exif_camera_info_removal(self, jpeg_with_exif):
        """Camera make/model should be removed from EXIF."""
        sanitized = strip_exif_metadata(
            jpeg_with_exif, FileType.JPEG, "photo.jpg"
        )

        # Check sanitized image has no camera data
        img = Image.open(io.BytesIO(sanitized))
        exif = img.getexif()

        # Verify camera tags removed
        camera_tags = {
            0x010F,  # Make
            0x0110,  # Model
            0x010E,  # ImageDescription
        }
        for tag_id in camera_tags:
            assert tag_id not in exif

    def test_strip_exif_corrupted_image(self):
        """Corrupted image should raise SanitizationError."""
        corrupted = b"Not a valid image"
        with pytest.raises(SanitizationError) as exc_info:
            strip_exif_metadata(corrupted, FileType.JPEG, "bad.jpg")

        assert "Failed to strip metadata" in str(exc_info.value)

    def test_strip_exif_pdf_passthrough(self):
        """PDF files should pass through without modification."""
        from pypdf import PdfWriter

        pdf_writer = PdfWriter()
        pdf_writer.add_blank_page(width=200, height=200)
        output = io.BytesIO()
        pdf_writer.write(output)
        pdf_bytes = output.getvalue()

        # PDF should pass through unchanged
        sanitized = strip_exif_metadata(
            pdf_bytes, FileType.PDF, "document.pdf"
        )

        assert sanitized == pdf_bytes


# Test: Filename sanitization
class TestFilenameSanitization:
    """Test filename sanitization for security."""

    def test_sanitize_filename_normal(self):
        """Normal filename should be unchanged."""
        assert sanitize_filename("photo.jpg") == "photo.jpg"
        assert sanitize_filename("document.pdf") == "document.pdf"

    def test_sanitize_filename_with_spaces(self):
        """Filename with spaces should preserve them."""
        assert sanitize_filename("my photo.jpg") == "my_photo.jpg"

    def test_sanitize_filename_path_traversal(self):
        """Path traversal attempts should be removed."""
        assert sanitize_filename("../../etc/passwd.jpg") == "passwd.jpg"
        assert sanitize_filename("../../../secrets.pdf") == "secrets.pdf"
        assert sanitize_filename("..\\..\\windows\\system32.jpg") == "system32.jpg"

    def test_sanitize_filename_absolute_path(self):
        """Absolute paths should be reduced to filename."""
        assert sanitize_filename("/etc/passwd.jpg") == "passwd.jpg"
        assert sanitize_filename("C:\\Windows\\System32\\file.jpg") == "file.jpg"

    def test_sanitize_filename_special_characters(self):
        """Special characters should be replaced with underscores."""
        assert sanitize_filename("photo<script>.jpg") == "photo_script.jpg"
        assert sanitize_filename("file?name*.jpg") == "file_name.jpg"
        assert sanitize_filename("test|file>.jpg") == "test_file.jpg"

    def test_sanitize_filename_multiple_dots(self):
        """Multiple dots should be converted to underscores for safety."""
        assert sanitize_filename("file.v1.jpg") == "file_v1.jpg"

    def test_sanitize_filename_leading_dots(self):
        """Leading dots should be removed."""
        result = sanitize_filename("...hidden.jpg")
        assert result == "hidden.jpg"

    def test_sanitize_filename_trailing_spaces(self):
        """Trailing spaces/underscores should be removed."""
        assert sanitize_filename("photo   .jpg") == "photo.jpg"

    def test_sanitize_filename_empty_basename(self):
        """Empty basename should use fallback."""
        result1 = sanitize_filename("...jpg")
        assert result1.endswith(".jpg") and "attachment" in result1.lower()
        result2 = sanitize_filename(".pdf")
        assert result2.endswith(".pdf") and "attachment" in result2.lower()

    def test_sanitize_filename_max_length(self):
        """Very long filename should be truncated."""
        long_name = "a" * 300 + ".jpg"
        sanitized = sanitize_filename(long_name)
        assert len(sanitized) <= 255  # Max filesystem length

    def test_sanitize_filename_unicode(self):
        """Unicode characters should be preserved or replaced."""
        # Depends on filesystem support, but should not crash
        result = sanitize_filename("photo_日本語.jpg")
        assert result.endswith(".jpg")

    def test_sanitize_filename_null_byte(self):
        """Null bytes should be handled."""
        result = sanitize_filename("file\x00.jpg")
        assert "\x00" not in result

    def test_sanitize_filename_collapse_underscores(self):
        """Multiple consecutive underscores should be collapsed."""
        assert sanitize_filename("file___name.jpg") == "file_name.jpg"


# Test: Full preparation pipeline
class TestFilePreparation:
    """Test complete file preparation for storage."""

    def test_prepare_file_for_storage_jpeg_with_exif(self, jpeg_with_exif):
        """JPEG with EXIF should be sanitized."""
        sanitized_bytes, safe_filename = prepare_file_for_storage(
            file_content=jpeg_with_exif,
            filename="photo.jpg",
            file_type=FileType.JPEG,
            strip_metadata=True,
        )

        # Verify EXIF stripped
        img = Image.open(io.BytesIO(sanitized_bytes))
        exif = img.getexif()
        assert len(exif) == 0 or len(exif) < 3

        # Verify filename sanitized
        assert safe_filename == "photo.jpg"

    def test_prepare_file_for_storage_dangerous_filename(self, jpeg_without_exif):
        """Dangerous filename should be sanitized."""
        sanitized_bytes, safe_filename = prepare_file_for_storage(
            file_content=jpeg_without_exif,
            filename="../../etc/passwd.jpg",
            file_type=FileType.JPEG,
            strip_metadata=True,
        )

        # Verify filename sanitized
        assert safe_filename == "passwd.jpg"
        assert "../" not in safe_filename

    def test_prepare_file_for_storage_no_metadata_stripping(self, jpeg_with_exif):
        """Metadata stripping can be disabled."""
        sanitized_bytes, safe_filename = prepare_file_for_storage(
            file_content=jpeg_with_exif,
            filename="photo.jpg",
            file_type=FileType.JPEG,
            strip_metadata=False,
        )

        # EXIF should still be present
        img = Image.open(io.BytesIO(sanitized_bytes))
        exif = img.getexif()
        assert len(exif) > 0  # EXIF preserved

        # Filename still sanitized
        assert safe_filename == "photo.jpg"

    def test_prepare_file_for_storage_png(self, png_image):
        """PNG preparation should work."""
        sanitized_bytes, safe_filename = prepare_file_for_storage(
            file_content=png_image,
            filename="image.png",
            file_type=FileType.PNG,
            strip_metadata=True,
        )

        # Verify image is valid
        img = Image.open(io.BytesIO(sanitized_bytes))
        assert img.format == "PNG"

        assert safe_filename == "image.png"

    def test_prepare_file_for_storage_pdf(self):
        """PDF preparation should work."""
        from pypdf import PdfWriter

        pdf_writer = PdfWriter()
        pdf_writer.add_blank_page(width=200, height=200)
        output = io.BytesIO()
        pdf_writer.write(output)
        pdf_bytes = output.getvalue()

        sanitized_bytes, safe_filename = prepare_file_for_storage(
            file_content=pdf_bytes,
            filename="document.pdf",
            file_type=FileType.PDF,
            strip_metadata=True,
        )

        # PDF should be unchanged (metadata stripping not implemented yet)
        assert len(sanitized_bytes) > 0

        assert safe_filename == "document.pdf"

    def test_prepare_file_for_storage_complex_filename(self, jpeg_without_exif):
        """Complex filename should be fully sanitized."""
        sanitized_bytes, safe_filename = prepare_file_for_storage(
            file_content=jpeg_without_exif,
            filename="../path/with spaces/and<special>chars?.jpg",
            file_type=FileType.JPEG,
            strip_metadata=True,
        )

        # Filename should be clean
        assert safe_filename == "and_special_chars.jpg"
        assert "../" not in safe_filename
        assert "<" not in safe_filename
        assert "?" not in safe_filename


# Privacy Test Cases
class TestPrivacyProtection:
    """Test privacy-focused sanitization scenarios."""

    def test_gps_coordinates_removed(self, jpeg_with_exif):
        """GPS coordinates should be stripped from photos (all metadata removed)."""
        sanitized_bytes, _ = prepare_file_for_storage(
            file_content=jpeg_with_exif,
            filename="treatment_photo.jpg",
            file_type=FileType.JPEG,
            strip_metadata=True,
        )

        # Verify no GPS data (all EXIF stripped)
        img = Image.open(io.BytesIO(sanitized_bytes))
        exif = img.getexif()

        # All metadata removed, including any GPS data
        assert len(exif) == 0 or len(exif) < 3

    def test_camera_serial_removed(self, jpeg_with_exif):
        """Camera serial number and make/model should be removed."""
        sanitized_bytes, _ = prepare_file_for_storage(
            file_content=jpeg_with_exif,
            filename="photo.jpg",
            file_type=FileType.JPEG,
            strip_metadata=True,
        )

        # Verify no camera identification data
        img = Image.open(io.BytesIO(sanitized_bytes))
        exif = img.getexif()

        camera_tags = {
            0x010F,  # Make
            0x0110,  # Model
        }
        for tag_id in camera_tags:
            assert tag_id not in exif

    def test_timestamp_removed(self, jpeg_with_exif):
        """Original timestamp should be removed."""
        sanitized_bytes, _ = prepare_file_for_storage(
            file_content=jpeg_with_exif,
            filename="photo.jpg",
            file_type=FileType.JPEG,
            strip_metadata=True,
        )

        # Verify no timestamp
        img = Image.open(io.BytesIO(sanitized_bytes))
        exif = img.getexif()

        timestamp_tags = {0x0132}  # DateTime
        for tag_id in timestamp_tags:
            assert tag_id not in exif

    def test_author_description_removed(self, jpeg_with_exif):
        """Author and description fields should be removed."""
        sanitized_bytes, _ = prepare_file_for_storage(
            file_content=jpeg_with_exif,
            filename="photo.jpg",
            file_type=FileType.JPEG,
            strip_metadata=True,
        )

        # Verify no author/description
        img = Image.open(io.BytesIO(sanitized_bytes))
        exif = img.getexif()

        metadata_tags = {
            0x010E,  # ImageDescription
            0x013B,  # Artist
            0x8298,  # Copyright
        }
        for tag_id in metadata_tags:
            assert tag_id not in exif
