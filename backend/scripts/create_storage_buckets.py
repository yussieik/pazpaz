#!/usr/bin/env python3
"""
Create and configure S3/MinIO storage buckets for PazPaz.

This script initializes the S3/MinIO storage backend with:
- Bucket creation with server-side encryption (SSE-S3)
- Versioning configuration (optional for V1)
- Lifecycle policies for automatic cleanup
- Access control policies (private by default)

Security Features:
- All buckets are private by default (no public access)
- Server-side encryption enabled (AES-256)
- Versioning can be enabled for audit compliance
- Lifecycle policies prevent storage bloat

Usage:
    # Run manually during setup
    python backend/scripts/create_storage_buckets.py

    # Run automatically on application startup (see main.py)
    # This ensures buckets exist before accepting requests

Environment Variables Required:
    S3_ENDPOINT_URL: MinIO/S3 endpoint (e.g., http://localhost:9000)
    S3_ACCESS_KEY: Access key ID
    S3_SECRET_KEY: Secret access key
    S3_BUCKET_NAME: Bucket name to create
    S3_REGION: S3 region (default: us-east-1)

Exit Codes:
    0: Success (bucket created or already exists)
    1: Configuration error (missing environment variables)
    2: Connection error (cannot reach S3/MinIO)
    3: Permission error (insufficient credentials)
"""

import sys
from pathlib import Path

# Add backend src to path for imports
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root / "src"))

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger

logger = get_logger(__name__)


class BucketCreationError(Exception):
    """Raised when bucket creation fails."""
    pass


def create_bucket_if_not_exists() -> bool:
    """
    Create S3 bucket with encryption if it doesn't exist.

    Returns:
        True if bucket was created or already exists
        False if creation failed

    Raises:
        BucketCreationError: If bucket creation fails with unrecoverable error
    """
    try:
        # Create S3 client
        s3_client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )

        bucket_name = settings.s3_bucket_name

        # Check if bucket already exists
        try:
            s3_client.head_bucket(Bucket=bucket_name)
            logger.info(f"Bucket already exists: {bucket_name}")
            return True

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code != "404":
                # Bucket exists but we don't have access
                logger.error(f"Cannot access bucket {bucket_name}: {e}")
                raise BucketCreationError(
                    f"Bucket exists but is not accessible: {e}"
                ) from e

        # Bucket doesn't exist, create it
        logger.info(f"Creating bucket: {bucket_name}")

        # For MinIO (localhost), we don't specify LocationConstraint
        # For AWS S3, we would need CreateBucketConfiguration
        if "localhost" in settings.s3_endpoint_url or "minio" in settings.s3_endpoint_url:
            # MinIO doesn't support LocationConstraint
            s3_client.create_bucket(Bucket=bucket_name)
        else:
            # AWS S3 requires LocationConstraint for non-us-east-1 regions
            if settings.s3_region == "us-east-1":
                s3_client.create_bucket(Bucket=bucket_name)
            else:
                s3_client.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": settings.s3_region},
                )

        logger.info(f"Bucket created successfully: {bucket_name}")

        # Configure server-side encryption (SSE-S3)
        configure_bucket_encryption(s3_client, bucket_name)

        # Block all public access (security best practice)
        block_public_access(s3_client, bucket_name)

        # Optional: Configure versioning (for audit compliance)
        # configure_versioning(s3_client, bucket_name)

        # Optional: Configure lifecycle policies (auto-cleanup)
        # configure_lifecycle_policies(s3_client, bucket_name)

        return True

    except (BotoCoreError, ClientError) as e:
        logger.error(f"Failed to create bucket {bucket_name}: {e}")
        raise BucketCreationError(f"Bucket creation failed: {e}") from e


def configure_bucket_encryption(s3_client, bucket_name: str) -> None:
    """
    Enable server-side encryption (SSE-S3) on bucket.

    All objects uploaded to this bucket will be automatically
    encrypted at rest using AES-256 encryption.

    Args:
        s3_client: Boto3 S3 client
        bucket_name: Bucket name

    Raises:
        BucketCreationError: If encryption configuration fails
    """
    try:
        s3_client.put_bucket_encryption(
            Bucket=bucket_name,
            ServerSideEncryptionConfiguration={
                "Rules": [
                    {
                        "ApplyServerSideEncryptionByDefault": {
                            "SSEAlgorithm": "AES256"  # SSE-S3 (free tier)
                        },
                        "BucketKeyEnabled": True,  # Reduce encryption costs
                    }
                ]
            },
        )
        logger.info(f"Bucket encryption enabled (SSE-S3): {bucket_name}")

    except ClientError as e:
        # MinIO may not support this API, log warning but continue
        error_code = e.response["Error"]["Code"]
        if error_code in ("NotImplemented", "MethodNotAllowed"):
            logger.warning(
                f"Bucket encryption API not supported (MinIO): {bucket_name}. "
                "Ensure MINIO_KMS_AUTO_ENCRYPTION=on is set in docker-compose.yml"
            )
        else:
            logger.error(f"Failed to enable encryption on {bucket_name}: {e}")
            raise BucketCreationError(f"Encryption configuration failed: {e}") from e


def block_public_access(s3_client, bucket_name: str) -> None:
    """
    Block all public access to bucket (security best practice).

    This prevents accidental exposure of PHI/PII data.
    All access must go through authenticated presigned URLs.

    Args:
        s3_client: Boto3 S3 client
        bucket_name: Bucket name

    Raises:
        BucketCreationError: If public access blocking fails
    """
    try:
        s3_client.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                "BlockPublicAcls": True,
                "IgnorePublicAcls": True,
                "BlockPublicPolicy": True,
                "RestrictPublicBuckets": True,
            },
        )
        logger.info(f"Public access blocked: {bucket_name}")

    except ClientError as e:
        # MinIO may not support this API, log warning but continue
        error_code = e.response["Error"]["Code"]
        if error_code in ("NotImplemented", "MethodNotAllowed", "MalformedXML"):
            logger.warning(
                f"Public access block API not supported (MinIO): {bucket_name}. "
                "MinIO buckets are private by default. "
                "Ensure no public bucket policies are applied."
            )
        else:
            logger.error(f"Failed to block public access on {bucket_name}: {e}")
            # Don't raise - this is not critical for MinIO
            logger.warning("Continuing without public access block configuration...")


def configure_versioning(s3_client, bucket_name: str, enabled: bool = False) -> None:
    """
    Configure bucket versioning (optional for V1).

    Versioning keeps all versions of objects for audit compliance.
    Disabled by default to save storage costs.

    Enable for production if required by compliance regulations.

    Args:
        s3_client: Boto3 S3 client
        bucket_name: Bucket name
        enabled: Enable versioning (default: False for V1)

    Raises:
        BucketCreationError: If versioning configuration fails
    """
    try:
        status = "Enabled" if enabled else "Suspended"
        s3_client.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={"Status": status},
        )
        logger.info(f"Bucket versioning {status.lower()}: {bucket_name}")

    except ClientError as e:
        logger.error(f"Failed to configure versioning on {bucket_name}: {e}")
        raise BucketCreationError(f"Versioning configuration failed: {e}") from e


def configure_lifecycle_policies(s3_client, bucket_name: str) -> None:
    """
    Configure lifecycle policies for automatic cleanup (optional for V1).

    Example policies:
    - Delete incomplete multipart uploads after 7 days
    - Transition old versions to cheaper storage after 30 days
    - Delete old versions after 90 days

    Args:
        s3_client: Boto3 S3 client
        bucket_name: Bucket name

    Raises:
        BucketCreationError: If lifecycle configuration fails
    """
    try:
        s3_client.put_bucket_lifecycle_configuration(
            Bucket=bucket_name,
            LifecycleConfiguration={
                "Rules": [
                    {
                        "Id": "delete-incomplete-multipart-uploads",
                        "Status": "Enabled",
                        "AbortIncompleteMultipartUpload": {
                            "DaysAfterInitiation": 7
                        },
                        "Filter": {},
                    }
                ]
            },
        )
        logger.info(f"Lifecycle policies configured: {bucket_name}")

    except ClientError as e:
        # MinIO may not support this API, log warning but continue
        error_code = e.response["Error"]["Code"]
        if error_code in ("NotImplemented", "MethodNotAllowed"):
            logger.warning(
                f"Lifecycle policy API not supported (MinIO): {bucket_name}"
            )
        else:
            logger.error(f"Failed to configure lifecycle policies on {bucket_name}: {e}")
            raise BucketCreationError(
                f"Lifecycle policy configuration failed: {e}"
            ) from e


def verify_bucket_configuration(s3_client, bucket_name: str) -> dict:
    """
    Verify bucket configuration and return status.

    Args:
        s3_client: Boto3 S3 client
        bucket_name: Bucket name

    Returns:
        Dictionary with configuration status

    Example:
        >>> status = verify_bucket_configuration(s3_client, "pazpaz-attachments")
        >>> print(status)
        {
            "exists": True,
            "encryption": "Enabled",
            "public_access": "Blocked",
            "versioning": "Suspended"
        }
    """
    status = {
        "exists": False,
        "encryption": "Unknown",
        "public_access": "Unknown",
        "versioning": "Unknown",
    }

    try:
        # Check if bucket exists
        s3_client.head_bucket(Bucket=bucket_name)
        status["exists"] = True

        # Check encryption
        try:
            encryption = s3_client.get_bucket_encryption(Bucket=bucket_name)
            status["encryption"] = "Enabled"
        except ClientError:
            status["encryption"] = "Disabled"

        # Check public access block
        try:
            public_access = s3_client.get_public_access_block(Bucket=bucket_name)
            config = public_access["PublicAccessBlockConfiguration"]
            if all(config.values()):
                status["public_access"] = "Blocked"
            else:
                status["public_access"] = "Partially Blocked"
        except ClientError:
            status["public_access"] = "Not Configured"

        # Check versioning
        try:
            versioning = s3_client.get_bucket_versioning(Bucket=bucket_name)
            status["versioning"] = versioning.get("Status", "Disabled")
        except ClientError:
            status["versioning"] = "Disabled"

    except ClientError as e:
        logger.error(f"Failed to verify bucket configuration: {e}")

    return status


def main() -> int:
    """
    Main entry point for bucket creation script.

    Returns:
        Exit code (0 = success, non-zero = failure)
    """
    try:
        logger.info("=" * 60)
        logger.info("PazPaz Storage Bucket Initialization")
        logger.info("=" * 60)
        logger.info(f"Endpoint: {settings.s3_endpoint_url}")
        logger.info(f"Bucket: {settings.s3_bucket_name}")
        logger.info(f"Region: {settings.s3_region}")
        logger.info("-" * 60)

        # Create bucket
        success = create_bucket_if_not_exists()

        if success:
            # Verify configuration
            s3_client = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint_url,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
                region_name=settings.s3_region,
            )
            status = verify_bucket_configuration(s3_client, settings.s3_bucket_name)

            logger.info("-" * 60)
            logger.info("Bucket Configuration Status:")
            for key, value in status.items():
                logger.info(f"  {key.replace('_', ' ').title()}: {value}")
            logger.info("=" * 60)
            logger.info("Storage initialization complete!")
            logger.info("=" * 60)
            return 0
        else:
            logger.error("Failed to create bucket")
            return 1

    except BucketCreationError as e:
        logger.error(f"Bucket creation error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
