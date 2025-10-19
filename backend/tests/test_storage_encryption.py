"""
Test suite for S3/MinIO server-side encryption.

HIPAA Compliance: §164.312(a)(2)(iv) - Encryption at rest for PHI

This test suite validates that all file uploads to S3/MinIO are:
1. Encrypted at rest using server-side encryption (SSE-S3 or AWS KMS)
2. Verified after upload to ensure encryption is active
3. Fail-closed if encryption cannot be confirmed

Test Coverage:
- MinIO encryption configuration (development)
- AWS S3 encryption configuration (production)
- Encryption verification after upload
- Error handling when encryption fails
- Both MinIO and AWS S3 code paths

Reference: Data Protection Audit Report, Section 2.1
"""

import io
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from pazpaz.core.storage import (
    EncryptionVerificationError,
    S3UploadError,
    is_minio_endpoint,
    upload_file,
    verify_file_encrypted,
)


class TestMinIOEndpointDetection:
    """Test MinIO vs AWS S3 endpoint detection."""

    def test_minio_localhost_detected(self):
        """Test localhost MinIO endpoint is detected."""
        assert is_minio_endpoint("http://localhost:9000") is True

    def test_minio_127_detected(self):
        """Test 127.0.0.1 MinIO endpoint is detected."""
        assert is_minio_endpoint("http://127.0.0.1:9000") is True

    def test_minio_hostname_detected(self):
        """Test minio hostname is detected."""
        assert is_minio_endpoint("http://minio.internal:9000") is True
        assert is_minio_endpoint("https://minio-dev.company.com") is True

    def test_aws_s3_not_minio(self):
        """Test AWS S3 endpoints are NOT detected as MinIO."""
        assert is_minio_endpoint("https://s3.amazonaws.com") is False
        assert is_minio_endpoint("https://s3.us-west-2.amazonaws.com") is False
        assert is_minio_endpoint("https://bucket.s3.amazonaws.com") is False

    def test_empty_endpoint_not_minio(self):
        """Test empty endpoint (default AWS S3) is not MinIO."""
        # When S3_ENDPOINT_URL is empty, boto3 uses default AWS S3 endpoint
        assert is_minio_endpoint("") is False


class TestEncryptionConfiguration:
    """Test encryption configuration for MinIO and AWS S3."""

    @patch("pazpaz.core.storage.get_s3_client")
    @patch("pazpaz.core.storage.settings")
    @patch("pazpaz.core.storage.verify_file_encrypted")
    async def test_minio_upload_uses_sse_s3(
        self, mock_verify, mock_settings, mock_get_client
    ):
        """Test MinIO uploads use SSE-S3 (AES256) encryption."""
        # Setup: MinIO endpoint
        mock_settings.s3_endpoint_url = "http://localhost:9000"
        mock_settings.s3_bucket_name = "pazpaz-attachments"

        # Mock S3 client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock file object
        file_obj = io.BytesIO(b"test file content")

        # Upload file
        await upload_file(
            file_obj=file_obj,
            workspace_id=123,
            session_id=456,
            filename="test.jpg",
            content_type="image/jpeg",
        )

        # Verify: ServerSideEncryption=AES256 was passed to upload_fileobj
        mock_client.upload_fileobj.assert_called_once()
        call_args = mock_client.upload_fileobj.call_args
        extra_args = call_args.kwargs["ExtraArgs"]

        assert "ServerSideEncryption" in extra_args
        assert extra_args["ServerSideEncryption"] == "AES256"

    @patch("pazpaz.core.storage.get_s3_client")
    @patch("pazpaz.core.storage.settings")
    @patch("pazpaz.core.storage.verify_file_encrypted")
    async def test_aws_s3_upload_uses_sse_s3(
        self, mock_verify, mock_settings, mock_get_client
    ):
        """Test AWS S3 uploads use SSE-S3 (AES256) encryption."""
        # Setup: AWS S3 endpoint
        mock_settings.s3_endpoint_url = "https://s3.us-west-2.amazonaws.com"
        mock_settings.s3_bucket_name = "pazpaz-attachments-prod"

        # Mock S3 client
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock file object
        file_obj = io.BytesIO(b"production file content")

        # Upload file
        await upload_file(
            file_obj=file_obj,
            workspace_id=999,
            session_id=888,
            filename="prod.pdf",
            content_type="application/pdf",
        )

        # Verify: ServerSideEncryption=AES256 was passed
        mock_client.upload_fileobj.assert_called_once()
        call_args = mock_client.upload_fileobj.call_args
        extra_args = call_args.kwargs["ExtraArgs"]

        assert "ServerSideEncryption" in extra_args
        assert extra_args["ServerSideEncryption"] == "AES256"


class TestEncryptionVerification:
    """Test encryption verification after upload."""

    @patch("pazpaz.core.storage.get_s3_client")
    @patch("pazpaz.core.storage.settings")
    def test_verify_encryption_success_minio(self, mock_settings, mock_get_client):
        """Test successful encryption verification for MinIO."""
        # Setup
        mock_settings.s3_bucket_name = "pazpaz-attachments"
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock head_object response with encryption
        mock_client.head_object.return_value = {
            "ServerSideEncryption": "AES256",
            "ContentType": "image/jpeg",
            "ContentLength": 12345,
        }

        # Verify encryption
        object_key = "123/sessions/456/test.jpg"
        verify_file_encrypted(object_key)  # Should not raise

        # Verify head_object was called
        mock_client.head_object.assert_called_once_with(
            Bucket="pazpaz-attachments",
            Key=object_key,
        )

    @patch("pazpaz.core.storage.get_s3_client")
    @patch("pazpaz.core.storage.settings")
    def test_verify_encryption_success_aws_kms(self, mock_settings, mock_get_client):
        """Test successful encryption verification for AWS S3 with KMS."""
        # Setup
        mock_settings.s3_bucket_name = "pazpaz-attachments-prod"
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock head_object response with AWS KMS encryption
        mock_client.head_object.return_value = {
            "ServerSideEncryption": "aws:kms",
            "SSEKMSKeyId": "arn:aws:kms:us-west-2:123456789:key/abc-def-123",
            "ContentType": "application/pdf",
        }

        # Verify encryption
        object_key = "workspace-uuid/sessions/session-uuid/attachments/file.pdf"
        verify_file_encrypted(object_key)  # Should not raise

        mock_client.head_object.assert_called_once()

    @patch("pazpaz.core.storage.get_s3_client")
    @patch("pazpaz.core.storage.settings")
    def test_verify_encryption_fails_missing_header(
        self, mock_settings, mock_get_client
    ):
        """Test encryption verification fails when ServerSideEncryption header is missing."""
        # Setup
        mock_settings.s3_bucket_name = "pazpaz-attachments"
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock head_object response WITHOUT encryption header
        mock_client.head_object.return_value = {
            "ContentType": "image/jpeg",
            "ContentLength": 12345,
            # ServerSideEncryption header is MISSING!
        }

        # Verify encryption should fail
        object_key = "123/sessions/456/unencrypted.jpg"

        with pytest.raises(EncryptionVerificationError) as exc_info:
            verify_file_encrypted(object_key)

        # Verify error message mentions HIPAA violation
        assert "not encrypted at rest" in str(exc_info.value)
        assert "HIPAA violation" in str(exc_info.value)

    @patch("pazpaz.core.storage.get_s3_client")
    @patch("pazpaz.core.storage.settings")
    def test_verify_encryption_fails_s3_error(self, mock_settings, mock_get_client):
        """Test encryption verification fails when S3 request fails."""
        # Setup
        mock_settings.s3_bucket_name = "pazpaz-attachments"
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock head_object to raise ClientError
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Object not found"}},
            "HeadObject",
        )

        # Verify encryption should fail
        object_key = "123/sessions/456/missing.jpg"

        with pytest.raises(EncryptionVerificationError) as exc_info:
            verify_file_encrypted(object_key)

        # Verify error message contains error code
        assert "NoSuchKey" in str(exc_info.value)


class TestUploadWithEncryptionVerification:
    """Test upload function calls encryption verification."""

    @patch("pazpaz.core.storage.get_s3_client")
    @patch("pazpaz.core.storage.settings")
    @patch("pazpaz.core.storage.verify_file_encrypted")
    async def test_upload_calls_verify_encryption(
        self, mock_verify, mock_settings, mock_get_client
    ):
        """Test upload_file calls verify_file_encrypted after upload."""
        # Setup
        mock_settings.s3_endpoint_url = "http://localhost:9000"
        mock_settings.s3_bucket_name = "pazpaz-attachments"

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        file_obj = io.BytesIO(b"test content")

        # Upload file
        object_key = await upload_file(
            file_obj=file_obj,
            workspace_id=123,
            session_id=456,
            filename="test.jpg",
            content_type="image/jpeg",
        )

        # Verify: verify_file_encrypted was called with correct object key
        mock_verify.assert_called_once_with(object_key)

    @patch("pazpaz.core.storage.get_s3_client")
    @patch("pazpaz.core.storage.settings")
    @patch("pazpaz.core.storage.verify_file_encrypted")
    async def test_upload_fails_if_verification_fails(
        self, mock_verify, mock_settings, mock_get_client
    ):
        """Test upload_file raises error if encryption verification fails."""
        # Setup
        mock_settings.s3_endpoint_url = "http://localhost:9000"
        mock_settings.s3_bucket_name = "pazpaz-attachments"

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock verification to fail
        mock_verify.side_effect = EncryptionVerificationError(
            "File not encrypted at rest!"
        )

        file_obj = io.BytesIO(b"test content")

        # Upload should fail with EncryptionVerificationError
        with pytest.raises(EncryptionVerificationError) as exc_info:
            await upload_file(
                file_obj=file_obj,
                workspace_id=123,
                session_id=456,
                filename="test.jpg",
                content_type="image/jpeg",
            )

        # Verify upload was attempted
        mock_client.upload_fileobj.assert_called_once()

        # Verify error message
        assert "not encrypted at rest" in str(exc_info.value)


class TestEncryptionForDifferentFileTypes:
    """Test encryption is applied to all file types (images, PDFs, etc.)."""

    @patch("pazpaz.core.storage.get_s3_client")
    @patch("pazpaz.core.storage.settings")
    @patch("pazpaz.core.storage.verify_file_encrypted")
    async def test_jpeg_encryption(self, mock_verify, mock_settings, mock_get_client):
        """Test JPEG files are encrypted."""
        mock_settings.s3_endpoint_url = "http://localhost:9000"
        mock_settings.s3_bucket_name = "pazpaz-attachments"

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        file_obj = io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100)  # JPEG magic bytes

        await upload_file(
            file_obj=file_obj,
            workspace_id=1,
            session_id=1,
            filename="photo.jpg",
            content_type="image/jpeg",
        )

        # Verify encryption was requested
        call_args = mock_client.upload_fileobj.call_args
        assert call_args.kwargs["ExtraArgs"]["ServerSideEncryption"] == "AES256"

    @patch("pazpaz.core.storage.get_s3_client")
    @patch("pazpaz.core.storage.settings")
    @patch("pazpaz.core.storage.verify_file_encrypted")
    async def test_pdf_encryption(self, mock_verify, mock_settings, mock_get_client):
        """Test PDF files are encrypted."""
        mock_settings.s3_endpoint_url = "http://localhost:9000"
        mock_settings.s3_bucket_name = "pazpaz-attachments"

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        file_obj = io.BytesIO(b"%PDF-1.4" + b"\x00" * 100)  # PDF magic bytes

        await upload_file(
            file_obj=file_obj,
            workspace_id=1,
            session_id=1,
            filename="notes.pdf",
            content_type="application/pdf",
        )

        # Verify encryption was requested
        call_args = mock_client.upload_fileobj.call_args
        assert call_args.kwargs["ExtraArgs"]["ServerSideEncryption"] == "AES256"

    @patch("pazpaz.core.storage.get_s3_client")
    @patch("pazpaz.core.storage.settings")
    @patch("pazpaz.core.storage.verify_file_encrypted")
    async def test_png_encryption(self, mock_verify, mock_settings, mock_get_client):
        """Test PNG files are encrypted."""
        mock_settings.s3_endpoint_url = "http://localhost:9000"
        mock_settings.s3_bucket_name = "pazpaz-attachments"

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        file_obj = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)  # PNG magic bytes

        await upload_file(
            file_obj=file_obj,
            workspace_id=1,
            session_id=1,
            filename="screenshot.png",
            content_type="image/png",
        )

        # Verify encryption was requested
        call_args = mock_client.upload_fileobj.call_args
        assert call_args.kwargs["ExtraArgs"]["ServerSideEncryption"] == "AES256"


class TestHIPAACompliance:
    """Test HIPAA compliance requirements for PHI file encryption."""

    @patch("pazpaz.core.storage.get_s3_client")
    @patch("pazpaz.core.storage.settings")
    def test_fail_closed_on_missing_encryption(self, mock_settings, mock_get_client):
        """Test system fails closed (rejects file) if encryption cannot be verified."""
        # HIPAA requires fail-closed behavior: if we can't verify encryption,
        # we MUST reject the upload (not allow unencrypted PHI)

        mock_settings.s3_bucket_name = "pazpaz-attachments"
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock response WITHOUT encryption header
        mock_client.head_object.return_value = {
            "ContentType": "image/jpeg",
            "ContentLength": 12345,
        }

        # Should raise EncryptionVerificationError
        with pytest.raises(EncryptionVerificationError):
            verify_file_encrypted("123/sessions/456/phi.jpg")

    @patch("pazpaz.core.storage.get_s3_client")
    @patch("pazpaz.core.storage.settings")
    @patch("pazpaz.core.storage.verify_file_encrypted")
    async def test_all_uploads_request_encryption(
        self, mock_verify, mock_settings, mock_get_client
    ):
        """Test ALL uploads request server-side encryption (no exceptions)."""
        mock_settings.s3_endpoint_url = "http://localhost:9000"
        mock_settings.s3_bucket_name = "pazpaz-attachments"

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Upload 10 different files
        for i in range(10):
            file_obj = io.BytesIO(f"file {i}".encode())
            await upload_file(
                file_obj=file_obj,
                workspace_id=i,
                session_id=i,
                filename=f"file{i}.txt",
                content_type="text/plain",
            )

        # Verify ALL uploads requested encryption
        assert mock_client.upload_fileobj.call_count == 10

        for call in mock_client.upload_fileobj.call_args_list:
            extra_args = call.kwargs["ExtraArgs"]
            assert "ServerSideEncryption" in extra_args
            assert extra_args["ServerSideEncryption"] == "AES256"


class TestProductionVsDevelopment:
    """Test encryption works in both MinIO (dev) and AWS S3 (prod) environments."""

    @patch("pazpaz.core.storage.get_s3_client")
    @patch("pazpaz.core.storage.settings")
    @patch("pazpaz.core.storage.verify_file_encrypted")
    async def test_development_minio_encryption(
        self, mock_verify, mock_settings, mock_get_client
    ):
        """Test development (MinIO) uses SSE-S3 encryption."""
        # Development environment
        mock_settings.s3_endpoint_url = "http://localhost:9000"
        mock_settings.s3_bucket_name = "pazpaz-attachments"

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        file_obj = io.BytesIO(b"dev file")
        await upload_file(
            file_obj=file_obj,
            workspace_id=1,
            session_id=1,
            filename="dev.jpg",
            content_type="image/jpeg",
        )

        # Verify SSE-S3 (AES256) is used
        call_args = mock_client.upload_fileobj.call_args
        assert call_args.kwargs["ExtraArgs"]["ServerSideEncryption"] == "AES256"

    @patch("pazpaz.core.storage.get_s3_client")
    @patch("pazpaz.core.storage.settings")
    @patch("pazpaz.core.storage.verify_file_encrypted")
    async def test_production_aws_s3_encryption(
        self, mock_verify, mock_settings, mock_get_client
    ):
        """Test production (AWS S3) uses SSE-S3 encryption."""
        # Production environment
        mock_settings.s3_endpoint_url = "https://s3.us-west-2.amazonaws.com"
        mock_settings.s3_bucket_name = "pazpaz-attachments-prod"

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        file_obj = io.BytesIO(b"prod file")
        await upload_file(
            file_obj=file_obj,
            workspace_id=999,
            session_id=888,
            filename="prod.pdf",
            content_type="application/pdf",
        )

        # Verify SSE-S3 (AES256) is used
        call_args = mock_client.upload_fileobj.call_args
        assert call_args.kwargs["ExtraArgs"]["ServerSideEncryption"] == "AES256"


class TestErrorHandling:
    """Test error handling and logging for encryption failures."""

    @patch("pazpaz.core.storage.get_s3_client")
    @patch("pazpaz.core.storage.settings")
    @patch("pazpaz.core.storage.verify_file_encrypted")
    async def test_upload_error_handling(
        self, mock_verify, mock_settings, mock_get_client
    ):
        """Test upload errors are handled gracefully."""
        mock_settings.s3_endpoint_url = "http://localhost:9000"
        mock_settings.s3_bucket_name = "pazpaz-attachments"

        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock upload to fail
        mock_client.upload_fileobj.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "Bucket not found"}},
            "PutObject",
        )

        file_obj = io.BytesIO(b"test")

        # Should raise S3UploadError
        with pytest.raises(S3UploadError) as exc_info:
            await upload_file(
                file_obj=file_obj,
                workspace_id=1,
                session_id=1,
                filename="test.jpg",
                content_type="image/jpeg",
            )

        # Verify error message
        assert "Failed to upload file" in str(exc_info.value)

    @patch("pazpaz.core.storage.get_s3_client")
    @patch("pazpaz.core.storage.settings")
    def test_verification_error_includes_details(self, mock_settings, mock_get_client):
        """Test verification errors include detailed information."""
        mock_settings.s3_bucket_name = "pazpaz-attachments"
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Mock head_object to return no encryption
        mock_client.head_object.return_value = {"ContentType": "image/jpeg"}

        # Verify encryption fails
        with pytest.raises(EncryptionVerificationError) as exc_info:
            verify_file_encrypted("test/key.jpg")

        error_message = str(exc_info.value)
        # Verify error message is informative
        assert "not encrypted at rest" in error_message
        assert "HIPAA violation" in error_message
        assert "ServerSideEncryption header missing" in error_message
