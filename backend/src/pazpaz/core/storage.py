"""
S3/MinIO storage client configuration.

This module provides a singleton S3 client for secure file storage with:
- Server-side encryption (SSE-S3) enabled by default
- Connection pooling and retry logic
- TLS/SSL for secure connections
- Workspace-scoped bucket paths for isolation
- UUID-based secure filename generation
- Temporary file handling with auto-cleanup

Security Features:
- All objects encrypted at rest using AES-256 (SSE-S3)
- Presigned URLs with time-based expiration (15 minutes default)
- Workspace path isolation prevents cross-workspace access
- TLS/SSL enforced for all connections in production
- UUID-based filenames prevent path traversal attacks

Usage:
    from pazpaz.core.storage import (
        get_s3_client,
        generate_secure_filename,
        upload_file,
        delete_file,
        generate_presigned_url,
    )

    # Generate secure UUID-based filename
    from pazpaz.utils.file_validation import FileType
    s3_key = generate_secure_filename(
        workspace_id=workspace.id,
        session_id=session.id,
        file_type=FileType.JPEG,
    )

    # Upload file with encryption
    await upload_file(
        file_obj=file.file,
        workspace_id=workspace.id,
        session_id=session.id,
        filename="photo.jpg",
        content_type="image/jpeg",
    )

    # Generate presigned download URL (15 minutes expiration)
    url = generate_presigned_url(s3_key)
"""

import tempfile
import uuid
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from pazpaz.core.config import settings
from pazpaz.core.logging import get_logger

if TYPE_CHECKING:
    from pazpaz.utils.file_validation import FileType

logger = get_logger(__name__)


def is_minio_endpoint(endpoint_url: str) -> bool:
    """
    Check if S3 endpoint is MinIO (not AWS S3).

    MinIO is used in development and has different capabilities than AWS S3
    (e.g., SSE-S3 requires KMS setup in MinIO but is native in AWS S3).

    Args:
        endpoint_url: S3 endpoint URL from settings

    Returns:
        True if endpoint is MinIO, False if AWS S3

    Example:
        >>> is_minio_endpoint("http://localhost:9000")
        True
        >>> is_minio_endpoint("https://s3.amazonaws.com")
        False
    """
    endpoint_lower = endpoint_url.lower()
    return "localhost" in endpoint_lower or "minio" in endpoint_lower


class S3ClientError(Exception):
    """Base exception for S3 client errors."""

    pass


class S3UploadError(S3ClientError):
    """Raised when file upload fails."""

    pass


class S3DownloadError(S3ClientError):
    """Raised when file download fails."""

    pass


class S3DeleteError(S3ClientError):
    """Raised when file deletion fails."""

    pass


@lru_cache(maxsize=1)
def get_s3_client():
    """
    Get cached S3 client singleton with production-ready configuration.

    Configuration:
    - Connection pooling (max_pool_connections=50)
    - Automatic retries (max_attempts=3) with exponential backoff
    - TLS/SSL enforced in production
    - Signature version 4 for security
    - 60-second connect timeout, 300-second read timeout

    The client is cached to avoid recreating connections on every call.

    Returns:
        boto3.client: Configured S3 client

    Raises:
        S3ClientError: If client creation fails

    Example:
        >>> s3 = get_s3_client()
        >>> s3.list_buckets()
    """
    try:
        # Configure with connection pooling and retries
        config = Config(
            max_pool_connections=50,  # Connection pooling
            retries={
                "max_attempts": 3,  # Retry failed requests up to 3 times
                "mode": "adaptive",  # Adaptive retry mode (recommended)
            },
            connect_timeout=60,  # Connection timeout in seconds
            read_timeout=300,  # Read timeout in seconds (5 minutes for large files)
            signature_version="s3v4",  # Use signature version 4 for security
        )

        # Determine if using TLS (required in production)
        use_ssl = settings.environment in ("production", "staging")

        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
            config=config,
            use_ssl=use_ssl,
        )

        logger.info(
            "S3 client initialized",
            extra={
                "endpoint": settings.s3_endpoint_url,
                "region": settings.s3_region,
                "use_ssl": use_ssl,
                "bucket": settings.s3_bucket_name,
            },
        )

        return client

    except (BotoCoreError, ClientError) as e:
        logger.error(f"Failed to create S3 client: {e}")
        raise S3ClientError(f"Failed to initialize S3 client: {e}") from e


def build_object_key(
    workspace_id: int,
    session_id: int,
    filename: str,
) -> str:
    """
    Build workspace-scoped S3 object key path.

    DEPRECATED: Use generate_secure_filename() for new code.
    This function is kept for backward compatibility.

    Object key structure enforces workspace isolation:
        {workspace_id}/sessions/{session_id}/{filename}

    This path-based isolation ensures:
    - No cross-workspace access (application-level enforcement)
    - Clear audit trail (workspace ID in every path)
    - Easy workspace-level deletion (delete prefix)

    Args:
        workspace_id: Workspace ID for isolation
        session_id: Session ID for grouping attachments
        filename: Original filename (sanitized by caller)

    Returns:
        S3 object key with workspace scoping

    Example:
        >>> build_object_key(123, 456, "photo.jpg")
        '123/sessions/456/photo.jpg'
    """
    # Note: Filename should be sanitized by caller before passing to this function
    # This function only builds the path structure
    return f"{workspace_id}/sessions/{session_id}/{filename}"


def generate_secure_filename(
    workspace_id: uuid.UUID,
    session_id: uuid.UUID | None,
    file_type: "FileType",
    client_id: uuid.UUID | None = None,
) -> str:
    """
    Generate secure S3 key with UUID-based filename.

    Uses UUID to ensure:
    - No user-controlled content in filename
    - Unique filenames (no collisions)
    - No path traversal attacks
    - Organized by workspace and session/client

    Key structure:
        - Session-level: workspaces/{workspace_id}/sessions/{session_id}/attachments/{uuid}.{ext}
        - Client-level: workspaces/{workspace_id}/clients/{client_id}/attachments/{uuid}.{ext}

    This is the PREFERRED method for generating S3 keys.

    Args:
        workspace_id: Workspace UUID (for isolation)
        session_id: Session UUID (for organization). None for client-level files.
        file_type: FileType enum (determines extension)
        client_id: Client UUID (required if session_id is None)

    Returns:
        S3 object key (path) with UUID-based filename

    Raises:
        ValueError: If both session_id and client_id are None

    Example:
        >>> from pazpaz.utils.file_validation import FileType
        >>> # Session-level file
        >>> s3_key = generate_secure_filename(
        ...     workspace_id=uuid.UUID("..."),
        ...     session_id=uuid.UUID("..."),
        ...     file_type=FileType.JPEG,
        ... )
        >>> # Returns: "workspaces/{uuid}/sessions/{uuid}/attachments/{uuid}.jpg"
        >>>
        >>> # Client-level file
        >>> s3_key = generate_secure_filename(
        ...     workspace_id=uuid.UUID("..."),
        ...     session_id=None,
        ...     file_type=FileType.PDF,
        ...     client_id=uuid.UUID("..."),
        ... )
        >>> # Returns: "workspaces/{uuid}/clients/{uuid}/attachments/{uuid}.pdf"
    """
    # Import here to avoid circular dependency
    from pazpaz.utils.file_validation import FILE_TYPE_TO_EXTENSION

    # Validate: must have either session_id or client_id
    if session_id is None and client_id is None:
        raise ValueError("Either session_id or client_id must be provided")

    # Generate unique attachment ID
    attachment_id = uuid.uuid4()

    # Get file extension from shared constant
    extension = FILE_TYPE_TO_EXTENSION[file_type]

    # Build S3 key with workspace/session or workspace/client hierarchy
    if session_id is not None:
        # Session-level file
        s3_key = (
            f"workspaces/{workspace_id}/sessions/{session_id}/"
            f"attachments/{attachment_id}.{extension}"
        )
        logger.debug(
            "secure_filename_generated",
            workspace_id=str(workspace_id),
            session_id=str(session_id),
            attachment_id=str(attachment_id),
            s3_key=s3_key,
            file_level="session",
        )
    else:
        # Client-level file
        s3_key = (
            f"workspaces/{workspace_id}/clients/{client_id}/"
            f"attachments/{attachment_id}.{extension}"
        )
        logger.debug(
            "secure_filename_generated",
            workspace_id=str(workspace_id),
            client_id=str(client_id),
            attachment_id=str(attachment_id),
            s3_key=s3_key,
            file_level="client",
        )

    return s3_key


def ensure_bucket_exists(bucket_name: str | None = None) -> None:
    """
    Ensure S3 bucket exists, create if missing.

    Args:
        bucket_name: Bucket name to check/create (default: from settings)

    Raises:
        S3ClientError: If bucket creation fails
    """
    bucket = bucket_name or settings.s3_bucket_name

    try:
        s3_client = get_s3_client()
        # Check if bucket exists
        s3_client.head_bucket(Bucket=bucket)
        logger.debug("bucket_exists", bucket_name=bucket)
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "404":
            # Bucket doesn't exist, create it
            try:
                s3_client.create_bucket(Bucket=bucket)
                logger.info("bucket_created", bucket_name=bucket)
            except ClientError as create_error:
                logger.error(
                    "bucket_creation_failed",
                    bucket_name=bucket,
                    error=str(create_error),
                )
                raise S3ClientError(
                    f"Failed to create bucket {bucket}: {create_error}"
                ) from create_error
        else:
            # Other error (permissions, etc.)
            logger.error(
                "bucket_check_failed",
                bucket_name=bucket,
                error=str(e),
                error_code=error_code,
            )
            raise S3ClientError(f"Failed to access bucket {bucket}: {e}") from e


def generate_presigned_url(
    object_key: str,
    expires_in: int = 900,
    http_method: str = "get_object",
    force_download: bool = True,
) -> str:
    """
    Generate presigned URL for temporary file access.

    Presigned URLs provide time-limited access to S3 objects without
    requiring AWS credentials. URLs expire after specified time.

    Default expiration: 15 minutes (900 seconds)
    Recommended: Keep expiration short to minimize security risk

    Args:
        object_key: S3 object key (from build_object_key)
        expires_in: URL expiration in seconds (default: 900 = 15 minutes)
        http_method: S3 method ("get_object" or "put_object")
        force_download: If True, adds response-content-disposition header to force download

    Returns:
        Presigned URL string

    Raises:
        S3ClientError: If URL generation fails

    Example:
        >>> url = generate_presigned_url("123/sessions/456/photo.jpg")
        >>> # URL valid for 15 minutes and forces download
    """
    try:
        s3_client = get_s3_client()

        params = {
            "Bucket": settings.s3_bucket_name,
            "Key": object_key,
        }

        # Add response-content-disposition to force download instead of inline display
        if force_download:
            # Extract filename from object key
            filename = object_key.split("/")[-1]
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

        url = s3_client.generate_presigned_url(
            http_method,
            Params=params,
            ExpiresIn=expires_in,
        )
        return url

    except (BotoCoreError, ClientError) as e:
        logger.error(
            f"Failed to generate presigned URL for {object_key}: {e}",
            extra={"object_key": object_key, "expires_in": expires_in},
        )
        raise S3ClientError(f"Failed to generate presigned URL: {e}") from e


async def upload_file(
    file_obj,
    workspace_id: int,
    session_id: int,
    filename: str,
    content_type: str,
) -> str:
    """
    Upload file to S3 with server-side encryption.

    Files are automatically encrypted at rest using AES-256 (SSE-S3).
    Object key enforces workspace isolation via path-based scoping.

    Note: MinIO in development mode doesn't support SSE-S3 headers without
    KMS configuration, so encryption headers are conditionally applied
    based on whether we're using MinIO or AWS S3.

    Args:
        file_obj: File-like object to upload (from FastAPI UploadFile)
        workspace_id: Workspace ID for isolation
        session_id: Session ID for grouping
        filename: Sanitized filename
        content_type: MIME type (validated by caller)

    Returns:
        S3 object key of uploaded file

    Raises:
        S3UploadError: If upload fails

    Example:
        >>> key = await upload_file(
        ...     file_obj=upload_file.file,
        ...     workspace_id=123,
        ...     session_id=456,
        ...     filename="photo.jpg",
        ...     content_type="image/jpeg"
        ... )
    """
    try:
        s3_client = get_s3_client()
        object_key = build_object_key(workspace_id, session_id, filename)

        # Prepare upload arguments
        extra_args = {"ContentType": content_type}

        # Only add ServerSideEncryption for AWS S3 (not MinIO in development)
        # MinIO requires KMS setup for SSE-S3, which is not needed in dev
        # In production AWS S3, this enables automatic encryption at rest
        if not is_minio_endpoint(settings.s3_endpoint_url):
            # SSE-S3 encryption (AWS only)
            extra_args["ServerSideEncryption"] = "AES256"

        # Upload file
        s3_client.upload_fileobj(
            file_obj,
            settings.s3_bucket_name,
            object_key,
            ExtraArgs=extra_args,
        )

        logger.info(
            f"File uploaded successfully: {object_key}",
            extra={
                "workspace_id": workspace_id,
                "session_id": session_id,
                "filename": filename,
                "content_type": content_type,
                "encryption": (
                    "MinIO-default"
                    if is_minio_endpoint(settings.s3_endpoint_url)
                    else "SSE-S3"
                ),
            },
        )

        return object_key

    except (BotoCoreError, ClientError) as e:
        logger.error(
            f"Failed to upload file {filename}: {e}",
            extra={
                "workspace_id": workspace_id,
                "session_id": session_id,
                "filename": filename,
            },
        )
        raise S3UploadError(f"Failed to upload file: {e}") from e


async def delete_file(object_key: str) -> None:
    """
    Delete file from S3.

    Note: This is a hard delete. Consider implementing soft deletes
    in the database (deleted_at column) instead of immediately
    removing files from S3.

    Args:
        object_key: S3 object key to delete

    Raises:
        S3DeleteError: If deletion fails

    Example:
        >>> await delete_file("123/sessions/456/photo.jpg")
    """
    try:
        s3_client = get_s3_client()
        s3_client.delete_object(
            Bucket=settings.s3_bucket_name,
            Key=object_key,
        )

        logger.info(
            f"File deleted successfully: {object_key}",
            extra={"object_key": object_key},
        )

    except (BotoCoreError, ClientError) as e:
        logger.error(
            f"Failed to delete file {object_key}: {e}",
            extra={"object_key": object_key},
        )
        raise S3DeleteError(f"Failed to delete file: {e}") from e


def verify_bucket_exists() -> bool:
    """
    Verify that configured S3 bucket exists and is accessible.

    This function is called during application startup to ensure
    storage is properly configured before accepting requests.

    Returns:
        True if bucket exists and is accessible

    Raises:
        S3ClientError: If bucket does not exist or is not accessible

    Example:
        >>> verify_bucket_exists()
        True
    """
    try:
        s3_client = get_s3_client()
        s3_client.head_bucket(Bucket=settings.s3_bucket_name)
        logger.info(f"S3 bucket verified: {settings.s3_bucket_name}")
        return True

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "404":
            logger.error(f"S3 bucket does not exist: {settings.s3_bucket_name}")
            raise S3ClientError(
                f"Bucket '{settings.s3_bucket_name}' does not exist. "
                "Run create_storage_buckets.py to initialize storage."
            ) from e
        else:
            logger.error(f"Failed to access S3 bucket: {e}")
            raise S3ClientError(f"Cannot access bucket: {e}") from e


class TemporaryFileHandler:
    """
    Context manager for temporary file handling with auto-cleanup.

    Ensures temporary files are deleted even on error.
    Supports both sync and async context managers.

    Example:
        ```python
        async with TemporaryFileHandler(suffix=".jpg") as tmp_path:
            # Write to tmp_path
            with open(tmp_path, 'wb') as f:
                f.write(data)
            # Use file
            process_file(tmp_path)
        # File automatically deleted when exiting context
        ```
    """

    def __init__(self, suffix: str = "", prefix: str = "pazpaz_upload_"):
        """
        Initialize temporary file handler.

        Args:
            suffix: File suffix (e.g., ".jpg")
            prefix: File prefix (default: "pazpaz_upload_")
        """
        self.suffix = suffix
        self.prefix = prefix
        self.temp_file = None
        self.temp_path = None

    def __enter__(self) -> Path:
        """
        Create temporary file and return path.

        Returns:
            Path to temporary file
        """
        # Create temporary file
        self.temp_file = tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=self.suffix,
            prefix=self.prefix,
            delete=False,  # We'll delete manually in __exit__
        )
        self.temp_path = Path(self.temp_file.name)

        logger.debug("temporary_file_created", path=str(self.temp_path))

        return self.temp_path

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Clean up temporary file.

        Args:
            exc_type: Exception type (if any)
            exc_val: Exception value (if any)
            exc_tb: Exception traceback (if any)
        """
        if self.temp_file:
            self.temp_file.close()

        if self.temp_path and self.temp_path.exists():
            try:
                self.temp_path.unlink()
                logger.debug("temporary_file_deleted", path=str(self.temp_path))
            except Exception as e:
                logger.warning(
                    "temporary_file_deletion_failed",
                    path=str(self.temp_path),
                    error=str(e),
                )

    async def __aenter__(self) -> Path:
        """Async context manager entry."""
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        return self.__exit__(exc_type, exc_val, exc_tb)
