"""Client attachment API endpoints for secure file uploads.

This module implements secure file upload functionality for client-level files with:
- Triple validation (MIME type, extension, content)
- EXIF metadata stripping for privacy
- Secure S3/MinIO storage with UUID-based keys
- Pre-signed URLs for downloads
- Workspace isolation and audit logging

Client-level attachments include:
- Intake forms uploaded before first session
- Consent documents
- Insurance cards
- Baseline assessment photos
- Any document that applies to the client generally, not a specific session
"""

from __future__ import annotations

import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from io import BytesIO

import redis.asyncio as redis
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.api.deps import get_current_user, get_db, get_or_404
from pazpaz.core.logging import get_logger
from pazpaz.core.rate_limiting import check_rate_limit_redis
from pazpaz.core.redis import get_redis
from pazpaz.core.storage import get_s3_client
from pazpaz.models.client import Client
from pazpaz.models.session import Session
from pazpaz.models.session_attachment import SessionAttachment
from pazpaz.models.user import User
from pazpaz.schemas.session_attachment import (
    AttachmentRenameRequest,
    BulkDownloadRequest,
    SessionAttachmentListResponse,
    SessionAttachmentResponse,
)
from pazpaz.utils.file_sanitization import prepare_file_for_storage
from pazpaz.utils.file_upload import (
    delete_file_from_s3,
    generate_presigned_download_url,
    generate_secure_filename,
    upload_file_to_s3,
)
from pazpaz.utils.file_validation import (
    FileContentError,
    FileSizeExceededError,
    FileValidationError,
    MimeTypeMismatchError,
    UnsupportedFileTypeError,
    validate_file,
)
from pazpaz.utils.storage_quota import (
    StorageQuotaExceededError,
    update_workspace_storage,
    validate_workspace_storage_quota,
)

router = APIRouter(prefix="/clients", tags=["client-attachments"])
logger = get_logger(__name__)


@router.post(
    "/{client_id}/attachments",
    response_model=SessionAttachmentResponse,
    status_code=201,
)
async def upload_client_attachment(
    client_id: uuid.UUID,
    file: UploadFile = File(...),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> SessionAttachmentResponse:
    """
    Upload file attachment for a client (not tied to specific session).

    This endpoint is for client-level documents like intake forms, consent documents,
    insurance cards, or baseline assessments that aren't specific to a session.

    Security features:
    - Triple validation (MIME type, extension, content)
    - EXIF metadata stripping (GPS, camera info)
    - File size limits (10 MB per file, 100 MB total per client)
    - Secure S3 key generation (UUID-based, no user-controlled names)
    - Workspace isolation (verified before upload)
    - Rate limiting (10 uploads per minute per user)
    - Audit logging (automatic via middleware)

    Supported file types:
    - Images: JPEG, PNG, WebP (for baseline photos, insurance cards)
    - Documents: PDF (for intake forms, consent documents, referrals)

    Args:
        client_id: UUID of the client
        file: Uploaded file (multipart/form-data)
        request: FastAPI request object (for audit logging)
        current_user: Authenticated user (from JWT token)
        db: Database session
        redis_client: Redis client (for rate limiting)

    Returns:
        Created attachment metadata (id, filename, size, content_type, created_at)

    Raises:
        HTTPException:
            - 401 if not authenticated
            - 404 if client not found or wrong workspace
            - 413 if file too large or total attachments exceed limit
            - 415 if unsupported file type or validation fails
            - 422 if validation error (MIME mismatch, corrupted file)
            - 429 if rate limit exceeded (10 uploads/minute)

    Example:
        POST /api/v1/clients/{uuid}/attachments
        Content-Type: multipart/form-data

        file: (binary data)
    """
    workspace_id = current_user.workspace_id

    # Rate limiting: 10 uploads per minute per user
    rate_limit_key = f"attachment_upload:{current_user.id}"
    max_uploads_per_minute = 10
    rate_limit_window_seconds = 60

    is_allowed = await check_rate_limit_redis(
        redis_client=redis_client,
        key=rate_limit_key,
        max_requests=max_uploads_per_minute,
        window_seconds=rate_limit_window_seconds,
    )

    if not is_allowed:
        logger.warning(
            "client_attachment_upload_rate_limit_exceeded",
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
            client_id=str(client_id),
            max_uploads=max_uploads_per_minute,
            window_seconds=rate_limit_window_seconds,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Upload rate limit exceeded. "
                f"Maximum {max_uploads_per_minute} uploads per minute."
            ),
        )

    logger.info(
        "client_attachment_upload_started",
        client_id=str(client_id),
        workspace_id=str(workspace_id),
        filename=file.filename,
        content_type=file.content_type,
    )

    # Verify client exists and belongs to workspace
    await get_or_404(db, Client, client_id, workspace_id)

    # Read file content
    try:
        file_content = await file.read()
    except Exception as e:
        logger.error(
            "file_read_failed",
            client_id=str(client_id),
            filename=file.filename,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {e}",
        ) from e

    file_size = len(file_content)

    # Calculate current total attachment size for this client
    query = select(SessionAttachment).where(
        SessionAttachment.client_id == client_id,
        SessionAttachment.workspace_id == workspace_id,
        SessionAttachment.deleted_at.is_(None),
    )
    result = await db.execute(query)
    existing_attachments = result.scalars().all()
    existing_total_size = sum(att.file_size_bytes for att in existing_attachments)

    # Validate file and total size (100 MB limit for client-level files)
    max_client_total_size = 100 * 1024 * 1024  # 100 MB
    try:
        # Validate individual file size
        file_type = validate_file(file.filename, file_content)

        # Validate total attachments size for client
        if existing_total_size + file_size > max_client_total_size:
            max_mb = max_client_total_size // (1024 * 1024)
            current_mb = existing_total_size // (1024 * 1024)
            new_mb = file_size // (1024 * 1024)
            raise FileSizeExceededError(
                f"Total client attachments would exceed {max_mb} MB limit. "
                f"Current: {current_mb} MB, New file: {new_mb} MB"
            )

    except FileSizeExceededError as e:
        logger.warning(
            "client_file_upload_rejected_size",
            client_id=str(client_id),
            filename=file.filename,
            file_size=file_size,
            existing_total_size=existing_total_size,
            reason=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(e),
        ) from e

    except UnsupportedFileTypeError as e:
        logger.warning(
            "client_file_upload_rejected_type",
            client_id=str(client_id),
            filename=file.filename,
            reason=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(e),
        ) from e

    except MimeTypeMismatchError as e:
        logger.warning(
            "client_file_upload_rejected_mime_mismatch",
            client_id=str(client_id),
            filename=file.filename,
            reason=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    except FileContentError as e:
        logger.warning(
            "client_file_upload_rejected_content",
            client_id=str(client_id),
            filename=file.filename,
            reason=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    except FileValidationError as e:
        logger.warning(
            "client_file_upload_rejected_validation",
            client_id=str(client_id),
            filename=file.filename,
            reason=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File validation failed: {e}",
        ) from e

    # Sanitize file (strip EXIF metadata, sanitize filename)
    try:
        sanitized_content, safe_filename = prepare_file_for_storage(
            file_content=file_content,
            filename=file.filename,
            file_type=file_type,
            strip_metadata=True,
        )
    except Exception as e:
        logger.error(
            "file_sanitization_failed",
            client_id=str(client_id),
            filename=file.filename,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File sanitization failed: {e}",
        ) from e

    # Generate secure S3 key (UUID-based, no user input)
    # Use None for session_id to indicate client-level file
    s3_key = generate_secure_filename(
        workspace_id=workspace_id,
        session_id=None,  # Client-level file
        file_type=file_type,
        client_id=client_id,
    )

    # STORAGE QUOTA: Validate BEFORE S3 upload (fail fast)
    try:
        await validate_workspace_storage_quota(
            workspace_id=workspace_id,
            new_file_size=len(sanitized_content),
            db=db,
        )
    except StorageQuotaExceededError as e:
        logger.warning(
            "client_file_upload_rejected_quota",
            client_id=str(client_id),
            workspace_id=str(workspace_id),
            filename=file.filename,
            file_size=len(sanitized_content),
            reason=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail=str(e),
        ) from e
    except ValueError as e:
        logger.error(
            "workspace_not_found_quota_check",
            workspace_id=str(workspace_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        ) from e

    # Upload to S3/MinIO
    try:
        _ = upload_file_to_s3(
            file_content=sanitized_content,
            s3_key=s3_key,
            content_type=file_type.value,
        )
    except Exception as e:
        logger.error(
            "s3_upload_failed",
            client_id=str(client_id),
            filename=file.filename,
            s3_key=s3_key,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {e}",
        ) from e

    # Create database record (session_id is NULL for client-level files)
    attachment = SessionAttachment(
        session_id=None,  # NULL = client-level file
        client_id=client_id,
        workspace_id=workspace_id,
        file_name=safe_filename,
        file_type=file_type.value,
        file_size_bytes=len(sanitized_content),
        s3_key=s3_key,
        uploaded_by_user_id=current_user.id,
    )

    db.add(attachment)

    try:
        await db.commit()
        await db.refresh(attachment)

        # STORAGE QUOTA: Update workspace storage usage AFTER successful commit
        await update_workspace_storage(
            workspace_id=workspace_id,
            bytes_delta=len(sanitized_content),  # Positive delta for upload
            db=db,
        )
        await db.commit()  # Commit storage usage update

    except Exception as e:
        logger.error(
            "client_attachment_db_commit_failed",
            client_id=str(client_id),
            s3_key=s3_key,
            error=str(e),
        )
        # Cleanup: Delete uploaded S3 object
        try:
            delete_file_from_s3(s3_key)
            logger.info("s3_cleanup_successful", s3_key=s3_key)
        except Exception as cleanup_error:
            logger.error(
                "s3_cleanup_failed",
                s3_key=s3_key,
                error=str(cleanup_error),
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save attachment metadata",
        ) from e

    logger.info(
        "client_attachment_uploaded",
        attachment_id=str(attachment.id),
        client_id=str(client_id),
        workspace_id=str(workspace_id),
        filename=safe_filename,
        file_type=file_type.value,
        file_size=len(sanitized_content),
        s3_key=s3_key,
        is_client_level=True,
    )

    # Return response with is_session_file=False
    return SessionAttachmentResponse.model_validate(
        {
            **SessionAttachmentResponse.model_validate(attachment).model_dump(),
            "session_date": None,
            "is_session_file": False,
        }
    )


@router.get(
    "/{client_id}/attachments",
    response_model=SessionAttachmentListResponse,
)
async def list_client_attachments(
    client_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionAttachmentListResponse:
    """
    List all attachments for a client across all sessions.

    Returns metadata for all attachments (filenames, sizes, types, session dates).
    Includes both session-level and client-level attachments.
    Does not include file content (use GET /attachments/{id}/download for content).

    Args:
        client_id: UUID of the client
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        List of attachment metadata with session context where applicable

    Raises:
        HTTPException:
            - 401 if not authenticated
            - 404 if client not found or wrong workspace

    Example:
        GET /api/v1/clients/{uuid}/attachments
        Response: {
            "items": [
                {
                    "id": "uuid",
                    "session_id": "uuid",
                    "client_id": "uuid",
                    "file_name": "wound_photo.jpg",
                    "file_type": "image/jpeg",
                    "file_size_bytes": 123456,
                    "created_at": "2025-10-15T14:30:00Z",
                    "session_date": "2025-10-15T13:00:00Z",
                    "is_session_file": true
                },
                {
                    "id": "uuid",
                    "session_id": null,
                    "client_id": "uuid",
                    "file_name": "intake_form.pdf",
                    "file_type": "application/pdf",
                    "file_size_bytes": 234567,
                    "created_at": "2025-10-01T10:00:00Z",
                    "session_date": null,
                    "is_session_file": false
                }
            ],
            "total": 2
        }
    """
    workspace_id = current_user.workspace_id

    # Verify client exists and belongs to workspace
    await get_or_404(db, Client, client_id, workspace_id)

    # Get all attachments for this client with session date context
    # LEFT JOIN to include client-level files (session_id = NULL)
    query = (
        select(SessionAttachment, Session.session_date)
        .outerjoin(Session, SessionAttachment.session_id == Session.id)
        .where(
            SessionAttachment.client_id == client_id,
            SessionAttachment.workspace_id == workspace_id,
            SessionAttachment.deleted_at.is_(None),
        )
        .order_by(SessionAttachment.created_at.desc())
    )
    result = await db.execute(query)
    rows = result.all()

    logger.debug(
        "client_attachments_listed",
        client_id=str(client_id),
        workspace_id=str(workspace_id),
        attachment_count=len(rows),
    )

    items = [
        SessionAttachmentResponse.model_validate(
            {
                **SessionAttachmentResponse.model_validate(att).model_dump(),
                "session_date": session_date,
                "is_session_file": att.session_id is not None,
            }
        )
        for att, session_date in rows
    ]

    return SessionAttachmentListResponse(
        items=items,
        total=len(items),
    )


@router.get(
    "/{client_id}/attachments/{attachment_id}/download",
    response_model=dict,
)
async def get_client_attachment_download_url(
    client_id: uuid.UUID,
    attachment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    expires_in_minutes: int = 15,
) -> dict:
    """
    Generate pre-signed download URL for client-level attachment.

    Returns a temporary pre-signed URL that allows downloading the file from S3.
    URL expires after specified time (default: 15 minutes, max: 60 minutes).

    Security:
    - URLs expire after 15 minutes by default (configurable, max 60 minutes)
    - Short expiration reduces risk of URL sharing or interception
    - Each download requires re-authentication and workspace verification
    - Workspace isolation enforced

    Args:
        client_id: UUID of the client
        attachment_id: UUID of the attachment
        current_user: Authenticated user (from JWT token)
        db: Database session
        expires_in_minutes: URL expiration time in minutes (default: 15, max: 60)

    Returns:
        Dict with download_url and expires_in_seconds

    Raises:
        HTTPException:
            - 401 if not authenticated
            - 404 if client/attachment not found or wrong workspace
            - 400 if expires_in_minutes exceeds maximum (60)

    Example:
        GET /api/v1/clients/{uuid}/attachments/{uuid}/download?expires_in_minutes=30
        Response: {
            "download_url": "https://s3.../file?X-Amz-...",
            "expires_in_seconds": 1800
        }
    """
    workspace_id = current_user.workspace_id

    # Validate expiration time (max 60 minutes for security)
    max_expiration_minutes = 60
    if expires_in_minutes > max_expiration_minutes:
        logger.warning(
            "client_download_url_expiration_too_long",
            requested_minutes=expires_in_minutes,
            max_minutes=max_expiration_minutes,
            user_id=str(current_user.id),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Expiration time cannot exceed {max_expiration_minutes} minutes",
        )

    if expires_in_minutes < 1:
        logger.warning(
            "client_download_url_expiration_too_short",
            requested_minutes=expires_in_minutes,
            user_id=str(current_user.id),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expiration time must be at least 1 minute",
        )

    # Verify client exists and belongs to workspace
    await get_or_404(db, Client, client_id, workspace_id)

    # Verify attachment exists, belongs to this client, is client-level,
    # and belongs to workspace (session_id NULL = client-level file)
    query = select(SessionAttachment).where(
        SessionAttachment.id == attachment_id,
        SessionAttachment.client_id == client_id,
        SessionAttachment.session_id.is_(None),  # Client-level file
        SessionAttachment.workspace_id == workspace_id,
        SessionAttachment.deleted_at.is_(None),
    )
    result = await db.execute(query)
    attachment = result.scalar_one_or_none()

    if not attachment:
        logger.warning(
            "client_attachment_not_found",
            attachment_id=str(attachment_id),
            client_id=str(client_id),
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )

    # Generate pre-signed URL
    # For image preview, use force_download=False to display inline
    try:
        expiration = timedelta(minutes=expires_in_minutes)
        download_url = generate_presigned_download_url(
            s3_key=attachment.s3_key,
            expiration=expiration,
            force_download=False,  # Display inline for image preview
        )
    except Exception as e:
        logger.error(
            "client_presigned_url_generation_failed",
            attachment_id=str(attachment_id),
            s3_key=attachment.s3_key,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate download URL",
        ) from e

    logger.info(
        "client_attachment_download_url_generated",
        attachment_id=str(attachment_id),
        client_id=str(client_id),
        workspace_id=str(workspace_id),
        expires_in_minutes=expires_in_minutes,
    )

    return {
        "download_url": download_url,
        "expires_in_seconds": int(expiration.total_seconds()),
    }


@router.patch(
    "/{client_id}/attachments/{attachment_id}",
    response_model=SessionAttachmentResponse,
)
async def rename_client_attachment(
    client_id: uuid.UUID,
    attachment_id: uuid.UUID,
    rename_data: AttachmentRenameRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionAttachmentResponse:
    """
    Rename a client-level attachment file.

    The file extension is automatically preserved. Invalid characters
    (/ \\ : * ? " < > |) are rejected. Duplicate filenames return 409 Conflict.

    Validation:
    - Filename length: 1-255 characters (after trimming whitespace)
    - Prohibited characters: / \\ : * ? " < > |
    - Extension preservation: Original extension automatically appended
    - Duplicate detection: Returns 409 if filename exists for same client
    - Whitespace trimming: Leading/trailing spaces removed

    Security:
    - Requires workspace access to the client
    - Validates attachment belongs to specified client
    - Validates attachment is client-level (session_id is NULL)
    - Audit logs all rename operations

    Args:
        client_id: UUID of the client
        attachment_id: UUID of the attachment to rename
        rename_data: New filename (extension will be preserved)
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Updated attachment metadata with new filename

    Raises:
        HTTPException:
            - 400 if filename is invalid (empty, too long, invalid chars)
            - 403 if workspace access denied
            - 404 if client or attachment not found
            - 409 if duplicate filename exists

    Example:
        PATCH /api/v1/clients/{uuid}/attachments/{uuid}
        {
            "file_name": "Intake form - signed"
        }
    """
    from pazpaz.models.audit_event import AuditAction, ResourceType
    from pazpaz.services.audit_service import create_audit_event
    from pazpaz.utils.filename_validation import (
        FilenameValidationError,
        extract_extension,
        validate_and_normalize_filename,
    )

    workspace_id = current_user.workspace_id

    # Verify client exists and belongs to workspace
    _ = await get_or_404(db, Client, client_id, workspace_id)

    # Verify attachment exists, belongs to this client, is client-level,
    # and belongs to workspace (session_id NULL = client-level file)
    query = select(SessionAttachment).where(
        SessionAttachment.id == attachment_id,
        SessionAttachment.client_id == client_id,
        SessionAttachment.session_id.is_(None),  # Client-level file
        SessionAttachment.workspace_id == workspace_id,
        SessionAttachment.deleted_at.is_(None),
    )
    result = await db.execute(query)
    attachment = result.scalar_one_or_none()

    if not attachment:
        logger.warning(
            "client_attachment_rename_not_found",
            attachment_id=str(attachment_id),
            client_id=str(client_id),
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )

    # Extract original extension
    original_extension = extract_extension(attachment.file_name)

    # Store old filename for audit log
    old_filename = attachment.file_name

    # Validate and normalize new filename
    try:
        validated_filename = await validate_and_normalize_filename(
            db=db,
            new_name=rename_data.file_name,
            original_extension=original_extension,
            client_id=client_id,
            exclude_attachment_id=attachment_id,  # Exclude self from duplicate check
        )
    except FilenameValidationError as e:
        logger.info(
            "client_attachment_rename_validation_failed",
            attachment_id=str(attachment_id),
            new_name=rename_data.file_name,
            reason=str(e),
        )

        # Return 409 for duplicates, 400 for other validation errors
        if "already exists" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            ) from e
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

    # Update attachment
    attachment.file_name = validated_filename

    await db.commit()
    await db.refresh(attachment)

    # Create audit event
    await create_audit_event(
        db=db,
        user_id=current_user.id,
        workspace_id=workspace_id,
        action=AuditAction.UPDATE,
        resource_type=ResourceType.SESSION_ATTACHMENT,
        resource_id=attachment_id,
        metadata={
            "old_filename": old_filename,
            "new_filename": validated_filename,
            "client_id": str(client_id),
            "is_client_level": True,
        },
    )

    logger.info(
        "client_attachment_renamed",
        attachment_id=str(attachment_id),
        client_id=str(client_id),
        workspace_id=str(workspace_id),
        old_filename=old_filename,
        new_filename=validated_filename,
    )

    # Return response for client-level attachment
    return SessionAttachmentResponse.model_validate(
        {
            **SessionAttachmentResponse.model_validate(attachment).model_dump(),
            "session_date": None,
            "is_session_file": False,
        }
    )


@router.delete(
    "/{client_id}/attachments/{attachment_id}",
    status_code=204,
)
async def delete_client_attachment(
    client_id: uuid.UUID,
    attachment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Soft delete a client-level attachment.

    Marks attachment as deleted (soft delete) without removing from S3.
    S3 cleanup happens via background job for deleted attachments.

    Args:
        client_id: UUID of the client
        attachment_id: UUID of the attachment
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        No content (204) on success

    Raises:
        HTTPException:
            - 401 if not authenticated
            - 404 if client/attachment not found or wrong workspace

    Example:
        DELETE /api/v1/clients/{uuid}/attachments/{uuid}
    """
    workspace_id = current_user.workspace_id

    # Verify client exists and belongs to workspace
    await get_or_404(db, Client, client_id, workspace_id)

    # Verify attachment exists, belongs to this client, is client-level,
    # and belongs to workspace (session_id NULL = client-level file)
    query = select(SessionAttachment).where(
        SessionAttachment.id == attachment_id,
        SessionAttachment.client_id == client_id,
        SessionAttachment.session_id.is_(None),  # Client-level file
        SessionAttachment.workspace_id == workspace_id,
        SessionAttachment.deleted_at.is_(None),
    )
    result = await db.execute(query)
    attachment = result.scalar_one_or_none()

    if not attachment:
        logger.warning(
            "client_attachment_delete_not_found",
            attachment_id=str(attachment_id),
            client_id=str(client_id),
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )

    logger.info(
        "client_attachment_delete_started",
        attachment_id=str(attachment_id),
        client_id=str(client_id),
        workspace_id=str(workspace_id),
        s3_key=attachment.s3_key,
    )

    # Soft delete (set deleted_at timestamp)
    attachment.deleted_at = datetime.now(UTC)

    # STORAGE QUOTA: Decrement workspace storage usage (negative delta)
    file_size_bytes = attachment.file_size_bytes

    try:
        await db.commit()

        # Update storage quota AFTER successful soft delete commit
        await update_workspace_storage(
            workspace_id=workspace_id,
            bytes_delta=-file_size_bytes,  # Negative delta for delete
            db=db,
        )
        await db.commit()  # Commit storage usage update

    except Exception as e:
        logger.error(
            "client_attachment_delete_commit_failed",
            attachment_id=str(attachment_id),
            client_id=str(client_id),
            workspace_id=str(workspace_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete attachment",
        ) from e

    logger.info(
        "client_attachment_deleted",
        attachment_id=str(attachment_id),
        client_id=str(client_id),
        workspace_id=str(workspace_id),
        file_size_bytes=file_size_bytes,
    )

    # Note: S3 cleanup is handled by background job
    # This prevents blocking the request on S3 operations


def _download_file_from_s3(s3_key: str) -> bytes:
    """
    Download file content from S3/MinIO.

    Args:
        s3_key: S3 object key

    Returns:
        File content as bytes

    Raises:
        HTTPException: If download fails
    """
    from pazpaz.core.config import settings

    try:
        s3_client = get_s3_client()
        response = s3_client.get_object(
            Bucket=settings.s3_bucket_name,
            Key=s3_key,
        )
        return response["Body"].read()
    except Exception as e:
        logger.error(
            "s3_download_failed",
            s3_key=s3_key,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download file from storage: {e}",
        ) from e


def _get_unique_filename(filename: str, existing_filenames: set[str]) -> str:
    """
    Generate unique filename by appending counter if duplicate exists.

    Examples:
        document.pdf -> document.pdf (if unique)
        document.pdf -> document (2).pdf (if duplicate)
        document.pdf -> document (3).pdf (if duplicate again)

    Args:
        filename: Original filename
        existing_filenames: Set of already used filenames

    Returns:
        Unique filename
    """
    if filename not in existing_filenames:
        return filename

    # Split filename into name and extension
    parts = filename.rsplit(".", 1)
    if len(parts) == 2:
        name, ext = parts
        ext = f".{ext}"
    else:
        name = filename
        ext = ""

    # Try incrementing counter until we find unique name
    counter = 2
    while True:
        new_filename = f"{name} ({counter}){ext}"
        if new_filename not in existing_filenames:
            return new_filename
        counter += 1


def _create_zip_from_attachments(
    attachments: list[SessionAttachment],
) -> BytesIO:
    """
    Create in-memory ZIP file from list of attachments.

    Downloads each file from S3 and adds to ZIP with original filename.
    Handles duplicate filenames by appending counter.

    Args:
        attachments: List of SessionAttachment instances

    Returns:
        BytesIO buffer containing ZIP file

    Raises:
        HTTPException: If any file download or ZIP creation fails
    """
    buffer = BytesIO()
    used_filenames: set[str] = set()

    try:
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for attachment in attachments:
                # Download file from S3
                file_data = _download_file_from_s3(attachment.s3_key)

                # Get unique filename (handle duplicates)
                unique_filename = _get_unique_filename(
                    attachment.file_name, used_filenames
                )
                used_filenames.add(unique_filename)

                # Add to ZIP
                zip_file.writestr(unique_filename, file_data)

                logger.debug(
                    "file_added_to_zip",
                    attachment_id=str(attachment.id),
                    filename=unique_filename,
                    size_bytes=len(file_data),
                )

        buffer.seek(0)
        logger.info(
            "zip_created_successfully",
            attachment_count=len(attachments),
            zip_size_bytes=buffer.getbuffer().nbytes,
        )
        return buffer

    except Exception as e:
        logger.error(
            "zip_creation_failed",
            attachment_count=len(attachments),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create ZIP file: {e}",
        ) from e


@router.post(
    "/{client_id}/attachments/download-multiple",
    response_class=StreamingResponse,
)
async def download_multiple_attachments(
    client_id: uuid.UUID,
    request_body: BulkDownloadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """
    Download multiple attachments as a ZIP file.

    Creates a ZIP archive containing all requested attachments and streams it
    to the client. All attachments must belong to the specified client and
    the user's workspace.

    Security:
    - Workspace isolation enforced (all attachments must belong to user's workspace)
    - Client ownership verified (all attachments must belong to specified client)
    - Soft-deleted attachments excluded
    - File size limit: 100 MB total
    - File count limit: 50 files maximum (enforced by schema)

    Performance:
    - Streaming response prevents memory issues with large ZIPs
    - In-memory ZIP creation (suitable for 100 MB limit)
    - Single S3 request per file (no batching needed at this scale)

    Args:
        client_id: UUID of the client
        request_body: List of attachment IDs to download
        current_user: Authenticated user
        db: Database session

    Returns:
        StreamingResponse with ZIP file

    Raises:
        HTTPException:
            - 400 if invalid request (empty list handled by schema)
            - 403 if workspace access denied
            - 404 if client or any attachment not found
            - 413 if total file size exceeds 100 MB
            - 500 if ZIP creation or S3 download fails

    Example:
        POST /api/v1/clients/{uuid}/attachments/download-multiple
        {
            "attachment_ids": ["uuid1", "uuid2", "uuid3"]
        }

        Response:
        Content-Type: application/zip
        Content-Disposition: attachment; filename="client-files-20251019_143022.zip"
        (binary ZIP data)
    """
    from pazpaz.models.audit_event import AuditAction, ResourceType
    from pazpaz.services.audit_service import create_audit_event

    workspace_id = current_user.workspace_id

    logger.info(
        "bulk_download_started",
        client_id=str(client_id),
        workspace_id=str(workspace_id),
        attachment_count=len(request_body.attachment_ids),
    )

    # Verify client exists and belongs to workspace
    await get_or_404(db, Client, client_id, workspace_id)

    # Fetch all requested attachments with validation
    # CRITICAL: Verify workspace_id, client_id, and deleted_at for security
    query = select(SessionAttachment).where(
        SessionAttachment.id.in_(request_body.attachment_ids),
        SessionAttachment.client_id == client_id,
        SessionAttachment.workspace_id == workspace_id,
        SessionAttachment.deleted_at.is_(None),
    )
    result = await db.execute(query)
    attachments = result.scalars().all()

    # Verify we got all requested attachments
    # If count doesn't match, some attachments were not found or
    # don't belong to this client
    if len(attachments) != len(request_body.attachment_ids):
        found_ids = {att.id for att in attachments}
        missing_ids = set(request_body.attachment_ids) - found_ids

        logger.warning(
            "bulk_download_attachments_not_found",
            client_id=str(client_id),
            workspace_id=str(workspace_id),
            requested_count=len(request_body.attachment_ids),
            found_count=len(attachments),
            missing_ids=[str(id) for id in missing_ids],
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "One or more attachments not found or do not belong to this client"
            ),
        )

    # Check total size limit (100 MB)
    total_size_bytes = sum(att.file_size_bytes for att in attachments)
    max_total_size_bytes = 100 * 1024 * 1024  # 100 MB

    if total_size_bytes > max_total_size_bytes:
        max_mb = max_total_size_bytes // (1024 * 1024)
        total_mb = total_size_bytes / (1024 * 1024)

        logger.warning(
            "bulk_download_size_limit_exceeded",
            client_id=str(client_id),
            workspace_id=str(workspace_id),
            total_size_bytes=total_size_bytes,
            total_size_mb=total_mb,
            max_size_mb=max_mb,
            attachment_count=len(attachments),
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"Total file size exceeds {max_mb} MB limit. "
                f"Selected files total {total_mb:.1f} MB. "
                f"Please select fewer files."
            ),
        )

    # Create ZIP file
    zip_buffer = _create_zip_from_attachments(attachments)

    # Generate filename with timestamp
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"client-files-{timestamp}.zip"

    # Create audit event for bulk download
    await create_audit_event(
        db=db,
        user_id=current_user.id,
        workspace_id=workspace_id,
        action=AuditAction.READ,
        resource_type=ResourceType.SESSION_ATTACHMENT,
        resource_id=None,  # Bulk operation, no single resource
        metadata={
            "client_id": str(client_id),
            "attachment_count": len(attachments),
            "attachment_ids": [str(att.id) for att in attachments],
            "total_size_bytes": total_size_bytes,
            "operation": "bulk_download",
        },
    )

    logger.info(
        "bulk_download_completed",
        client_id=str(client_id),
        workspace_id=str(workspace_id),
        attachment_count=len(attachments),
        total_size_bytes=total_size_bytes,
        zip_filename=filename,
    )

    # Return streaming response with ZIP file
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(zip_buffer.getbuffer().nbytes),
        },
    )
