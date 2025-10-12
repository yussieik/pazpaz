"""Session attachment API endpoints for secure file uploads.

This module implements secure file upload functionality for SOAP session notes with:
- Triple validation (MIME type, extension, content)
- EXIF metadata stripping for privacy
- Secure S3/MinIO storage with UUID-based keys
- Pre-signed URLs for downloads
- Workspace isolation and audit logging
"""

from __future__ import annotations

import uuid
from datetime import timedelta

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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.api.deps import get_current_user, get_db, get_or_404
from pazpaz.core.logging import get_logger
from pazpaz.core.rate_limiting import check_rate_limit_redis
from pazpaz.core.redis import get_redis
from pazpaz.models.session import Session
from pazpaz.models.session_attachment import SessionAttachment
from pazpaz.models.user import User
from pazpaz.schemas.session_attachment import (
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
    validate_total_attachments_size,
)

router = APIRouter(prefix="/sessions", tags=["session-attachments"])
logger = get_logger(__name__)


@router.post(
    "/{session_id}/attachments",
    response_model=SessionAttachmentResponse,
    status_code=201,
)
async def upload_session_attachment(
    session_id: uuid.UUID,
    file: UploadFile = File(...),
    request: Request = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> SessionAttachmentResponse:
    """
    Upload file attachment for a session note.

    Security features:
    - Triple validation (MIME type, extension, content)
    - EXIF metadata stripping (GPS, camera info)
    - File size limits (10 MB per file, 50 MB total per session)
    - Secure S3 key generation (UUID-based, no user-controlled names)
    - Workspace isolation (verified before upload)
    - Rate limiting (10 uploads per minute per user)
    - Audit logging (automatic via middleware)

    Supported file types:
    - Images: JPEG, PNG, WebP (for wound photos, treatment documentation)
    - Documents: PDF (for lab reports, referrals, consent forms)

    Args:
        session_id: UUID of the session
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
            - 404 if session not found or wrong workspace
            - 413 if file too large or total attachments exceed limit
            - 415 if unsupported file type or validation fails
            - 422 if validation error (MIME mismatch, corrupted file)
            - 429 if rate limit exceeded (10 uploads/minute)

    Example:
        POST /api/v1/sessions/{uuid}/attachments
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
            "attachment_upload_rate_limit_exceeded",
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
            session_id=str(session_id),
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
        "attachment_upload_started",
        session_id=str(session_id),
        workspace_id=str(workspace_id),
        filename=file.filename,
        content_type=file.content_type,
    )

    # Verify session exists and belongs to workspace
    await get_or_404(db, Session, session_id, workspace_id)

    # Read file content
    try:
        file_content = await file.read()
    except Exception as e:
        logger.error(
            "file_read_failed",
            session_id=str(session_id),
            filename=file.filename,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {e}",
        ) from e

    file_size = len(file_content)

    # Calculate current total attachment size for this session
    query = select(SessionAttachment).where(
        SessionAttachment.session_id == session_id,
        SessionAttachment.workspace_id == workspace_id,
        SessionAttachment.deleted_at.is_(None),
    )
    result = await db.execute(query)
    existing_attachments = result.scalars().all()
    existing_total_size = sum(att.file_size_bytes for att in existing_attachments)

    # Validate file and total size
    try:
        # Validate individual file size and total attachments size
        validate_total_attachments_size(existing_total_size, file_size)

        # Triple validation: MIME type, extension, content
        file_type = validate_file(file.filename, file_content)

    except FileSizeExceededError as e:
        logger.warning(
            "file_upload_rejected_size",
            session_id=str(session_id),
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
            "file_upload_rejected_type",
            session_id=str(session_id),
            filename=file.filename,
            reason=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(e),
        ) from e

    except MimeTypeMismatchError as e:
        logger.warning(
            "file_upload_rejected_mime_mismatch",
            session_id=str(session_id),
            filename=file.filename,
            reason=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    except FileContentError as e:
        logger.warning(
            "file_upload_rejected_content",
            session_id=str(session_id),
            filename=file.filename,
            reason=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e

    except FileValidationError as e:
        logger.warning(
            "file_upload_rejected_validation",
            session_id=str(session_id),
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
            session_id=str(session_id),
            filename=file.filename,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File sanitization failed: {e}",
        ) from e

    # Generate secure S3 key (UUID-based, no user input)
    s3_key = generate_secure_filename(
        workspace_id=workspace_id,
        session_id=session_id,
        file_type=file_type,
    )

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
            session_id=str(session_id),
            filename=file.filename,
            s3_key=s3_key,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {e}",
        ) from e

    # Create database record
    attachment = SessionAttachment(
        session_id=session_id,
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
    except Exception as e:
        logger.error(
            "attachment_db_commit_failed",
            session_id=str(session_id),
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
        "attachment_uploaded",
        attachment_id=str(attachment.id),
        session_id=str(session_id),
        workspace_id=str(workspace_id),
        filename=safe_filename,
        file_type=file_type.value,
        file_size=len(sanitized_content),
        s3_key=s3_key,
    )

    return SessionAttachmentResponse.model_validate(attachment)


@router.get(
    "/{session_id}/attachments",
    response_model=SessionAttachmentListResponse,
)
async def list_session_attachments(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionAttachmentListResponse:
    """
    List all attachments for a session.

    Returns metadata for all attachments (filenames, sizes, types).
    Does not include file content (use GET /attachments/{id}/download for content).

    Args:
        session_id: UUID of the session
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        List of attachment metadata

    Raises:
        HTTPException:
            - 401 if not authenticated
            - 404 if session not found or wrong workspace

    Example:
        GET /api/v1/sessions/{uuid}/attachments
    """
    workspace_id = current_user.workspace_id

    # Verify session exists and belongs to workspace
    await get_or_404(db, Session, session_id, workspace_id)

    # Get all attachments for this session (exclude soft-deleted)
    query = (
        select(SessionAttachment)
        .where(
            SessionAttachment.session_id == session_id,
            SessionAttachment.workspace_id == workspace_id,
            SessionAttachment.deleted_at.is_(None),
        )
        .order_by(SessionAttachment.created_at.desc())
    )
    result = await db.execute(query)
    attachments = result.scalars().all()

    logger.debug(
        "attachments_listed",
        session_id=str(session_id),
        workspace_id=str(workspace_id),
        attachment_count=len(attachments),
    )

    items = [SessionAttachmentResponse.model_validate(att) for att in attachments]

    return SessionAttachmentListResponse(
        items=items,
        total=len(items),
    )


@router.get(
    "/{session_id}/attachments/{attachment_id}/download",
    response_model=dict,
)
async def get_attachment_download_url(
    session_id: uuid.UUID,
    attachment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    expires_in_minutes: int = 15,
) -> dict:
    """
    Generate pre-signed download URL for attachment.

    Returns a temporary pre-signed URL that allows downloading the file from S3.
    URL expires after specified time (default: 15 minutes, max: 60 minutes).

    Security:
    - URLs expire after 15 minutes by default (configurable, max 60 minutes)
    - Short expiration reduces risk of URL sharing or interception
    - Each download requires re-authentication and workspace verification

    Args:
        session_id: UUID of the session
        attachment_id: UUID of the attachment
        current_user: Authenticated user (from JWT token)
        db: Database session
        expires_in_minutes: URL expiration time in minutes (default: 15, max: 60)

    Returns:
        Dict with download_url and expires_at timestamp

    Raises:
        HTTPException:
            - 401 if not authenticated
            - 404 if session/attachment not found or wrong workspace
            - 400 if expires_in_minutes exceeds maximum (60)

    Example:
        GET /api/v1/sessions/{uuid}/attachments/{uuid}/download?expires_in_minutes=30
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
            "download_url_expiration_too_long",
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
            "download_url_expiration_too_short",
            requested_minutes=expires_in_minutes,
            user_id=str(current_user.id),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expiration time must be at least 1 minute",
        )

    # Verify session exists and belongs to workspace
    await get_or_404(db, Session, session_id, workspace_id)

    # Verify attachment exists and belongs to this session and workspace
    query = select(SessionAttachment).where(
        SessionAttachment.id == attachment_id,
        SessionAttachment.session_id == session_id,
        SessionAttachment.workspace_id == workspace_id,
        SessionAttachment.deleted_at.is_(None),
    )
    result = await db.execute(query)
    attachment = result.scalar_one_or_none()

    if not attachment:
        logger.warning(
            "attachment_not_found",
            attachment_id=str(attachment_id),
            session_id=str(session_id),
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )

    # Generate pre-signed URL
    try:
        expiration = timedelta(minutes=expires_in_minutes)
        download_url = generate_presigned_download_url(
            s3_key=attachment.s3_key,
            expiration=expiration,
        )
    except Exception as e:
        logger.error(
            "presigned_url_generation_failed",
            attachment_id=str(attachment_id),
            s3_key=attachment.s3_key,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate download URL",
        ) from e

    logger.info(
        "attachment_download_url_generated",
        attachment_id=str(attachment_id),
        session_id=str(session_id),
        workspace_id=str(workspace_id),
        expires_in_minutes=expires_in_minutes,
    )

    return {
        "download_url": download_url,
        "expires_in_seconds": int(expiration.total_seconds()),
    }


@router.delete(
    "/{session_id}/attachments/{attachment_id}",
    status_code=204,
)
async def delete_session_attachment(
    session_id: uuid.UUID,
    attachment_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Soft delete a session attachment.

    Marks attachment as deleted (soft delete) without removing from S3.
    S3 cleanup happens via background job for deleted attachments.

    Args:
        session_id: UUID of the session
        attachment_id: UUID of the attachment
        request: FastAPI request object (for audit logging)
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        No content (204) on success

    Raises:
        HTTPException:
            - 401 if not authenticated
            - 404 if session/attachment not found or wrong workspace

    Example:
        DELETE /api/v1/sessions/{uuid}/attachments/{uuid}
    """
    workspace_id = current_user.workspace_id

    # Verify session exists and belongs to workspace
    await get_or_404(db, Session, session_id, workspace_id)

    # Verify attachment exists and belongs to this session and workspace
    query = select(SessionAttachment).where(
        SessionAttachment.id == attachment_id,
        SessionAttachment.session_id == session_id,
        SessionAttachment.workspace_id == workspace_id,
        SessionAttachment.deleted_at.is_(None),
    )
    result = await db.execute(query)
    attachment = result.scalar_one_or_none()

    if not attachment:
        logger.warning(
            "attachment_delete_not_found",
            attachment_id=str(attachment_id),
            session_id=str(session_id),
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )

    logger.info(
        "attachment_delete_started",
        attachment_id=str(attachment_id),
        session_id=str(session_id),
        workspace_id=str(workspace_id),
        s3_key=attachment.s3_key,
    )

    # Soft delete (set deleted_at timestamp)
    from datetime import UTC, datetime

    attachment.deleted_at = datetime.now(UTC)

    await db.commit()

    logger.info(
        "attachment_deleted",
        attachment_id=str(attachment_id),
        session_id=str(session_id),
        workspace_id=str(workspace_id),
    )

    # Note: S3 cleanup is handled by background job
    # This prevents blocking the request on S3 operations
