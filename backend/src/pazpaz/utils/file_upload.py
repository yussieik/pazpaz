"""Secure file upload utilities for S3/MinIO storage.

IMPORTANT: This module is a compatibility wrapper. All core S3/MinIO
functionality has been consolidated into pazpaz.core.storage for better
architecture and DRY principles.

For new code, import directly from pazpaz.core.storage:
    from pazpaz.core.storage import (
        get_s3_client,
        generate_secure_filename,
        upload_file,
        delete_file,
        generate_presigned_url,
        ensure_bucket_exists,
        TemporaryFileHandler,
    )

This module re-exports these functions for backward compatibility with existing code.
"""

from __future__ import annotations

from datetime import timedelta

# Re-export all core storage functionality
from pazpaz.core.storage import (
    EncryptionVerificationError,
    S3ClientError,
    S3DeleteError,
    S3UploadError,
    TemporaryFileHandler,  # noqa: F401 - re-exported for compatibility
    ensure_bucket_exists,
    generate_secure_filename,  # noqa: F401 - re-exported for compatibility
    get_s3_client,
    is_minio_endpoint,
)
from pazpaz.core.storage import (
    generate_presigned_url as generate_presigned_url_core,
)

# Re-export base exception with old name for compatibility
FileUploadError = S3ClientError

# Explicitly list what's exported from this module
__all__ = [
    # Core storage re-exports
    "S3ClientError",
    "S3DeleteError",
    "S3UploadError",
    "EncryptionVerificationError",
    "FileUploadError",
    "TemporaryFileHandler",
    "ensure_bucket_exists",
    "generate_secure_filename",
    "get_s3_client",
    # Compatibility wrappers
    "generate_presigned_download_url",
    "upload_file_to_s3",
    "delete_file_from_s3",
]


def generate_presigned_download_url(
    s3_key: str,
    expiration: timedelta = timedelta(hours=1),
    bucket_name: str | None = None,
    force_download: bool = True,
) -> str:
    """
    Generate pre-signed URL for secure file download.

    COMPATIBILITY WRAPPER: This function wraps the core storage module's
    generate_presigned_url to maintain the same API signature used by
    existing code.

    For new code, use:
        from pazpaz.core.storage import generate_presigned_url

    Args:
        s3_key: S3 object key (path)
        expiration: URL expiration time (default: 1 hour)
        bucket_name: Bucket name (ignored, uses settings.s3_bucket_name)
        force_download: If True, URL forces download; if False, displays inline

    Returns:
        Pre-signed URL string

    Raises:
        S3ClientError: If URL generation fails
    """
    # Convert timedelta to seconds for core function
    expires_in = int(expiration.total_seconds())
    return generate_presigned_url_core(
        s3_key, expires_in=expires_in, force_download=force_download
    )


def upload_file_to_s3(
    file_content: bytes,
    s3_key: str,
    content_type: str,
    bucket_name: str | None = None,
) -> dict:
    """
    Upload file to S3/MinIO with server-side encryption and verification.

    COMPATIBILITY WRAPPER: This function wraps the core storage module's upload
    functionality but uses a synchronous interface with bytes content.

    SECURITY: This function MUST verify encryption after upload (HIPAA requirement).

    NOTE: This is NOT the preferred method. The core storage.upload_file() is async
    and works with file objects for better memory efficiency with large files.

    For new code, use:
        from pazpaz.core.storage import upload_file

    Args:
        file_content: File bytes to upload
        s3_key: S3 object key (path)
        content_type: MIME type (e.g., "image/jpeg")
        bucket_name: Bucket name (ignored, uses settings.s3_bucket_name)

    Returns:
        Dict with upload metadata:
            - bucket: S3 bucket name
            - key: S3 object key
            - etag: S3 ETag for integrity verification
            - size_bytes: File size in bytes
            - encryption_verified: True if encryption was verified
            - encryption_metadata: Dict with encryption details for database storage:
                - algorithm: "AES256"
                - verified_at: ISO timestamp
                - s3_sse: ServerSideEncryption value from S3
                - etag: S3 ETag

    Raises:
        S3UploadError: If upload fails
        EncryptionVerificationError: If encryption cannot be verified (HIPAA critical)
    """
    import structlog

    from pazpaz.core.config import settings
    from pazpaz.core.storage import verify_file_encrypted

    logger = structlog.get_logger(__name__)

    try:
        # Use synchronous boto3 client directly for compatibility
        s3_client = get_s3_client()

        # Ensure bucket exists
        ensure_bucket_exists(bucket_name)

        bucket = bucket_name or settings.s3_bucket_name

        # Prepare upload arguments
        extra_args = {"ContentType": content_type}

        # Enable server-side encryption (SSE-S3)
        # Note: MinIO doesn't support SSE-S3, so only enable for AWS
        if not is_minio_endpoint(settings.s3_endpoint_url):
            extra_args["ServerSideEncryption"] = "AES256"
            logger.info(
                "s3_sse_enabled",
                s3_key=s3_key,
                encryption="AES256",
            )

        # Upload file to S3
        response = s3_client.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=file_content,
            **extra_args,
        )

        logger.info(
            "file_uploaded_to_s3",
            s3_key=s3_key,
            bucket=bucket,
            size_bytes=len(file_content),
        )

        # CRITICAL SECURITY FIX: Verify encryption after upload (HIPAA requirement)
        # This ensures PHI files are encrypted at rest before returning success
        try:
            verify_file_encrypted(s3_key)
            logger.info(
                "s3_encryption_verified",
                s3_key=s3_key,
                encryption_status="verified",
            )
        except Exception as verify_error:
            # Verification failed - this is a CRITICAL security issue
            # Delete the potentially unencrypted file
            logger.error(
                "s3_encryption_verification_failed",
                s3_key=s3_key,
                error=str(verify_error),
                action="deleting_file",
            )

            try:
                s3_client.delete_object(Bucket=bucket, Key=s3_key)
                logger.info("unencrypted_file_deleted", s3_key=s3_key)
            except Exception as delete_error:
                logger.error(
                    "failed_to_delete_unencrypted_file",
                    s3_key=s3_key,
                    error=str(delete_error),
                )

            # Re-raise verification error (fail-closed)
            raise EncryptionVerificationError(
                f"Failed to verify encryption for {s3_key}: {verify_error}. "
                f"File has been deleted for security. Please retry upload."
            ) from verify_error

        # Extract ETag and encryption metadata from response
        etag = response.get("ETag", "").strip('"')
        server_side_encryption = response.get("ServerSideEncryption", "AES256")

        # Build encryption metadata for database storage (HIPAA compliance)
        from datetime import UTC, datetime

        encryption_metadata = {
            "algorithm": "AES256",
            "verified_at": datetime.now(UTC).isoformat(),
            "s3_sse": server_side_encryption,
            "etag": etag,
        }

        return {
            "bucket": bucket,
            "key": s3_key,
            "etag": etag,
            "size_bytes": len(file_content),
            "encryption_verified": True,
            "encryption_metadata": encryption_metadata,  # NEW: Metadata for DB storage
        }

    except EncryptionVerificationError:
        # Re-raise encryption errors (HIPAA critical)
        raise
    except Exception as e:
        logger.error(
            "s3_upload_failed",
            s3_key=s3_key,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise S3UploadError(f"Failed to upload file to S3: {e}") from e


def delete_file_from_s3(
    s3_key: str,
    bucket_name: str | None = None,
) -> None:
    """
    Delete file from S3/MinIO (synchronous).

    COMPATIBILITY WRAPPER: This function wraps the core storage module's delete
    functionality but uses a synchronous interface.

    For new async code, use:
        from pazpaz.core.storage import delete_file
        await delete_file(s3_key)

    Args:
        s3_key: S3 object key (path)
        bucket_name: Bucket name (ignored, uses settings.s3_bucket_name)

    Raises:
        S3DeleteError: If deletion fails
    """
    from pazpaz.core.config import settings

    try:
        s3_client = get_s3_client()
        bucket = bucket_name or settings.s3_bucket_name

        s3_client.delete_object(
            Bucket=bucket,
            Key=s3_key,
        )

    except Exception as e:
        raise S3DeleteError(f"Failed to delete file from S3: {e}") from e
