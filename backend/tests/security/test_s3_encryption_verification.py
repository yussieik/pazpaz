"""
Test S3 encryption verification for all upload paths.

Security Requirement: All PHI files MUST be encrypted at rest (HIPAA §164.312(a)(2)(iv)).
"""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from pazpaz.core.storage import EncryptionVerificationError
from pazpaz.utils.file_upload import (
    S3UploadError,
    upload_file_to_s3,
)


class TestS3EncryptionVerification:
    """Test encryption verification in upload_file_to_s3()."""

    @pytest.fixture
    def mock_s3_client(self):
        """Mock S3 client."""
        client = MagicMock()
        with patch("pazpaz.utils.file_upload.get_s3_client", return_value=client):
            yield client

    @pytest.fixture
    def mock_ensure_bucket(self):
        """Mock ensure_bucket_exists."""
        with patch("pazpaz.utils.file_upload.ensure_bucket_exists"):
            yield

    @pytest.fixture
    def mock_is_minio(self):
        """Mock is_minio_endpoint to return False (AWS S3)."""
        with patch("pazpaz.utils.file_upload.is_minio_endpoint", return_value=False):
            yield

    def test_upload_verifies_encryption_success(
        self, mock_s3_client, mock_ensure_bucket, mock_is_minio
    ):
        """Successful upload verifies encryption and returns metadata."""
        # Mock successful upload
        mock_s3_client.put_object.return_value = {"ETag": '"abc123"'}

        # Mock successful encryption verification
        # Patch where the function is used, not where it's defined
        with patch("pazpaz.core.storage.verify_file_encrypted") as mock_verify:
            result = upload_file_to_s3(
                file_content=b"test content",
                s3_key="test.txt",
                content_type="text/plain",
            )

        # Verify encryption check was called
        mock_verify.assert_called_once_with("test.txt")

        # Verify return value includes encryption_verified flag
        assert result["encryption_verified"] is True
        assert result["key"] == "test.txt"
        assert result["size_bytes"] == 12

    def test_upload_fails_if_encryption_verification_fails(
        self, mock_s3_client, mock_ensure_bucket, mock_is_minio
    ):
        """Upload fails and deletes file if encryption cannot be verified."""
        # Mock successful upload
        mock_s3_client.put_object.return_value = {"ETag": '"abc123"'}

        # Mock failed encryption verification
        with patch("pazpaz.core.storage.verify_file_encrypted") as mock_verify:
            mock_verify.side_effect = EncryptionVerificationError(
                "No ServerSideEncryption header"
            )

            # Upload should fail with EncryptionVerificationError
            with pytest.raises(EncryptionVerificationError) as exc_info:
                upload_file_to_s3(
                    file_content=b"sensitive PHI data",
                    s3_key="phi/patient-123.pdf",
                    content_type="application/pdf",
                )

            assert "encryption" in str(exc_info.value).lower()
            assert "phi/patient-123.pdf" in str(exc_info.value)

        # Verify file was deleted after verification failure
        mock_s3_client.delete_object.assert_called_once()
        delete_call = mock_s3_client.delete_object.call_args
        assert delete_call[1]["Key"] == "phi/patient-123.pdf"

    def test_upload_with_sse_enabled_for_aws(
        self, mock_s3_client, mock_ensure_bucket, mock_is_minio
    ):
        """Upload to AWS S3 includes ServerSideEncryption parameter."""
        mock_s3_client.put_object.return_value = {"ETag": '"abc123"'}

        with patch("pazpaz.core.storage.verify_file_encrypted"):
            upload_file_to_s3(
                file_content=b"test",
                s3_key="test.txt",
                content_type="text/plain",
            )

        # Verify put_object was called with SSE
        put_call = mock_s3_client.put_object.call_args
        assert put_call[1]["ServerSideEncryption"] == "AES256"

    def test_upload_without_sse_for_minio(self, mock_s3_client, mock_ensure_bucket):
        """Upload to MinIO does NOT include ServerSideEncryption (not supported)."""
        # Mock is_minio_endpoint to return True
        with patch("pazpaz.utils.file_upload.is_minio_endpoint", return_value=True):
            mock_s3_client.put_object.return_value = {"ETag": '"abc123"'}

            with patch("pazpaz.core.storage.verify_file_encrypted"):
                upload_file_to_s3(
                    file_content=b"test",
                    s3_key="test.txt",
                    content_type="text/plain",
                )

            # Verify put_object was NOT called with SSE
            put_call = mock_s3_client.put_object.call_args
            assert "ServerSideEncryption" not in put_call[1]

    def test_upload_deletes_file_on_verification_failure(
        self, mock_s3_client, mock_ensure_bucket, mock_is_minio
    ):
        """File is deleted if encryption verification fails (fail-closed)."""
        mock_s3_client.put_object.return_value = {"ETag": '"abc123"'}

        with patch("pazpaz.core.storage.verify_file_encrypted") as mock_verify:
            mock_verify.side_effect = EncryptionVerificationError("Not encrypted")

            with pytest.raises(EncryptionVerificationError):
                upload_file_to_s3(
                    file_content=b"PHI data",
                    s3_key="workspaces/ws-1/sessions/s-1/file.pdf",
                    content_type="application/pdf",
                )

        # Verify delete was called
        mock_s3_client.delete_object.assert_called_once()
        assert mock_s3_client.delete_object.call_args[1]["Key"] == (
            "workspaces/ws-1/sessions/s-1/file.pdf"
        )

    def test_upload_handles_delete_failure_gracefully(
        self, mock_s3_client, mock_ensure_bucket, mock_is_minio
    ):
        """If file deletion fails after verification failure, error is logged but original error raised."""
        mock_s3_client.put_object.return_value = {"ETag": '"abc123"'}

        # Mock verification failure
        with patch("pazpaz.core.storage.verify_file_encrypted") as mock_verify:
            mock_verify.side_effect = EncryptionVerificationError("Not encrypted")

            # Mock delete failure
            mock_s3_client.delete_object.side_effect = ClientError(
                {"Error": {"Code": "NoSuchKey"}}, "DeleteObject"
            )

            # Should still raise original EncryptionVerificationError
            with pytest.raises(EncryptionVerificationError) as exc_info:
                upload_file_to_s3(
                    file_content=b"test",
                    s3_key="test.txt",
                    content_type="text/plain",
                )

            assert "Not encrypted" in str(exc_info.value)

    def test_upload_failure_before_verification_raises_s3_upload_error(
        self, mock_s3_client, mock_ensure_bucket, mock_is_minio
    ):
        """Upload failure before verification raises S3UploadError, not EncryptionVerificationError."""
        # Mock upload failure
        mock_s3_client.put_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}}, "PutObject"
        )

        with pytest.raises(S3UploadError) as exc_info:
            upload_file_to_s3(
                file_content=b"test",
                s3_key="test.txt",
                content_type="text/plain",
            )

        assert "Failed to upload" in str(exc_info.value)

    def test_verify_file_encrypted_checks_sse_header(self):
        """verify_file_encrypted() checks for ServerSideEncryption header."""
        from pazpaz.core.storage import verify_file_encrypted

        mock_s3_client = MagicMock()

        with patch("pazpaz.core.storage.get_s3_client", return_value=mock_s3_client):
            with patch("pazpaz.core.storage.is_minio_endpoint", return_value=False):
                # Mock head_object to return SSE header
                mock_s3_client.head_object.return_value = {
                    "ServerSideEncryption": "AES256"
                }

                # Should succeed without error
                verify_file_encrypted("test.txt")

                mock_s3_client.head_object.assert_called_once()

    def test_verify_file_encrypted_raises_if_no_sse_header(self):
        """verify_file_encrypted() raises error if no SSE header on AWS S3."""
        from pazpaz.core.storage import verify_file_encrypted

        mock_s3_client = MagicMock()

        with patch("pazpaz.core.storage.get_s3_client", return_value=mock_s3_client):
            with patch("pazpaz.core.storage.is_minio_endpoint", return_value=False):
                # Mock head_object without SSE header
                mock_s3_client.head_object.return_value = {}

                with pytest.raises(EncryptionVerificationError) as exc_info:
                    verify_file_encrypted("unencrypted.txt")

                # Check error message contains relevant information
                error_msg = str(exc_info.value)
                assert (
                    "not encrypted at rest" in error_msg
                    or "encryption" in error_msg.lower()
                )

    def test_verify_file_encrypted_skips_minio_check(self):
        """verify_file_encrypted() skips check for MinIO (not supported)."""
        from pazpaz.core.storage import verify_file_encrypted

        with patch("pazpaz.core.storage.is_minio_endpoint", return_value=True):
            # Should succeed without checking SSE header
            verify_file_encrypted("minio-file.txt")


class TestEncryptionVerificationError:
    """Test EncryptionVerificationError exception."""

    def test_encryption_verification_error_is_exception(self):
        """EncryptionVerificationError is a proper exception."""
        error = EncryptionVerificationError("test message")
        assert isinstance(error, Exception)
        assert str(error) == "test message"

    def test_encryption_verification_error_can_be_caught(self):
        """EncryptionVerificationError can be caught and handled."""
        try:
            raise EncryptionVerificationError("Encryption failed")
        except EncryptionVerificationError as e:
            assert "Encryption failed" in str(e)
        else:
            pytest.fail("Exception not raised")
