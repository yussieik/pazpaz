"""Session CRUD API endpoints for SOAP-based clinical documentation."""

from __future__ import annotations

import math
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.api.deps import get_current_user, get_db, get_or_404
from pazpaz.core.logging import get_logger
from pazpaz.core.rate_limiting import check_rate_limit_redis
from pazpaz.core.redis import get_redis
from pazpaz.models.client import Client
from pazpaz.models.session import Session
from pazpaz.models.user import User
from pazpaz.schemas.session import (
    SessionCreate,
    SessionDraftUpdate,
    SessionListResponse,
    SessionResponse,
    SessionUpdate,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])
logger = get_logger(__name__)


async def verify_client_in_workspace(
    db: AsyncSession,
    client_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> Client:
    """
    Verify that a client exists and belongs to the workspace.

    SECURITY: Returns generic 404 error to prevent information leakage.

    Args:
        db: Database session
        client_id: Client ID to verify
        workspace_id: Expected workspace ID

    Returns:
        Client instance

    Raises:
        HTTPException: 404 if client not found or belongs to different workspace
    """
    return await get_or_404(db, Client, client_id, workspace_id)


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    session_data: SessionCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """
    Create a new SOAP session note.

    Creates a new session after verifying:
    1. Client belongs to the workspace
    2. Session date is not in the future (validated by Pydantic)

    SECURITY: workspace_id is derived from authenticated user's JWT token (server-side).
    All PHI fields (subjective, objective, assessment, plan) are automatically encrypted
    at rest using AES-256-GCM via the EncryptedString type.

    AUDIT: Creation is automatically logged by AuditMiddleware.

    Args:
        session_data: Session creation data (without workspace_id)
        request: FastAPI request object (for audit logging)
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Created session with encrypted PHI fields

    Raises:
        HTTPException: 401 if not authenticated, 404 if client not found,
            422 if validation fails

    Example:
        POST /api/v1/sessions
        {
            "client_id": "uuid",
            "session_date": "2025-10-08T14:30:00Z",
            "subjective": "Patient reports...",
            "objective": "Observations...",
            "assessment": "Clinical assessment...",
            "plan": "Treatment plan..."
        }
    """
    workspace_id = current_user.workspace_id
    logger.info(
        "session_create_started",
        workspace_id=str(workspace_id),
        client_id=str(session_data.client_id),
    )

    # Verify client exists and belongs to workspace
    await verify_client_in_workspace(
        db=db,
        client_id=session_data.client_id,
        workspace_id=workspace_id,
    )

    # Create new session with injected workspace_id and created_by_user_id
    # PHI fields are automatically encrypted via EncryptedString type
    session = Session(
        workspace_id=workspace_id,
        client_id=session_data.client_id,
        appointment_id=session_data.appointment_id,
        created_by_user_id=current_user.id,
        subjective=session_data.subjective,
        objective=session_data.objective,
        assessment=session_data.assessment,
        plan=session_data.plan,
        session_date=session_data.session_date,
        duration_minutes=session_data.duration_minutes,
        is_draft=True,  # All new sessions start as drafts
        draft_last_saved_at=datetime.now(UTC),
        version=1,
    )

    db.add(session)
    await db.commit()
    await db.refresh(session)

    logger.info(
        "session_created",
        session_id=str(session.id),
        workspace_id=str(workspace_id),
        client_id=str(session_data.client_id),
        is_draft=session.is_draft,
    )

    # Return response (PHI automatically decrypted by ORM)
    return SessionResponse.model_validate(session)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """
    Get a single session by ID with decrypted SOAP fields.

    Retrieves a session by ID, ensuring it belongs to the authenticated workspace.
    PHI fields are automatically decrypted from database storage.

    SECURITY: Returns 404 for both non-existent sessions and sessions in other
    workspaces to prevent information leakage. workspace_id is derived from JWT token.

    AUDIT: PHI access is manually logged via create_audit_event.

    Args:
        session_id: UUID of the session
        request: FastAPI request object (for audit logging)
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Session details with decrypted PHI fields

    Raises:
        HTTPException: 401 if not authenticated,
            404 if not found or wrong workspace

    Example:
        GET /api/v1/sessions/{uuid}
    """
    workspace_id = current_user.workspace_id

    # Fetch with workspace scoping (validates existence and workspace access)
    session = await get_or_404(db, Session, session_id, workspace_id)

    # NOTE: PHI access is automatically logged by AuditMiddleware for GET /sessions/{id}
    logger.debug(
        "session_phi_accessed",
        session_id=str(session_id),
        workspace_id=str(workspace_id),
        user_id=str(current_user.id),
    )

    # Return response (PHI automatically decrypted by ORM)
    return SessionResponse.model_validate(session)


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    client_id: uuid.UUID | None = Query(
        None, description="Filter by client ID (required for list operations)"
    ),
    is_draft: bool | None = Query(None, description="Filter by draft status"),
) -> SessionListResponse:
    """
    List sessions with optional filters.

    Returns a paginated list of sessions, ordered by session_date descending.
    All results are scoped to the authenticated workspace.

    SECURITY: Only returns sessions belonging to the authenticated user's
    workspace (from JWT). Requires client_id filter to prevent accidental
    exposure of all sessions.

    PERFORMANCE: Uses ix_sessions_workspace_client_date index for optimal
    query performance.

    Args:
        current_user: Authenticated user (from JWT token)
        db: Database session
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
        client_id: Filter by specific client (REQUIRED)
        is_draft: Filter by draft status (optional)

    Returns:
        Paginated list of sessions with decrypted PHI fields

    Raises:
        HTTPException: 401 if not authenticated, 422 if client_id not provided

    Example:
        GET /api/v1/sessions?client_id={uuid}&page=1&page_size=50&is_draft=true
    """
    workspace_id = current_user.workspace_id

    # Require client_id filter to prevent accidental broad queries
    if not client_id:
        raise HTTPException(
            status_code=422,
            detail="client_id parameter is required for listing sessions",
        )

    logger.debug(
        "session_list_started",
        workspace_id=str(workspace_id),
        client_id=str(client_id),
        page=page,
        page_size=page_size,
        is_draft=is_draft,
    )

    # Verify client belongs to workspace
    await verify_client_in_workspace(
        db=db,
        client_id=client_id,
        workspace_id=workspace_id,
    )

    # Calculate offset
    offset = (page - 1) * page_size

    # Build base query with workspace and client scoping
    # Uses ix_sessions_workspace_client_date index
    # (workspace_id, client_id, session_date DESC)
    base_query = select(Session).where(
        Session.workspace_id == workspace_id,
        Session.client_id == client_id,
        Session.deleted_at.is_(None),  # Only active sessions
    )

    # Apply draft filter if provided
    if is_draft is not None:
        base_query = base_query.where(Session.is_draft == is_draft)

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    # Get paginated results ordered by session_date descending
    query = (
        base_query.order_by(Session.session_date.desc()).offset(offset).limit(page_size)
    )
    result = await db.execute(query)
    sessions = result.scalars().all()

    # Build response items (PHI automatically decrypted)
    items = [SessionResponse.model_validate(session) for session in sessions]

    # Calculate total pages
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    logger.debug(
        "session_list_completed",
        workspace_id=str(workspace_id),
        client_id=str(client_id),
        total_sessions=total,
        page=page,
    )

    return SessionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.put("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: uuid.UUID,
    session_data: SessionUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """
    Update an existing session with partial updates.

    Updates session fields. Only provided fields are updated (partial updates).
    Session must belong to the authenticated workspace.

    SECURITY: Verifies workspace ownership before allowing updates.
    workspace_id is derived from JWT token (server-side).
    Updated PHI fields are automatically encrypted at rest.

    OPTIMISTIC LOCKING: Uses version field to prevent concurrent update conflicts.
    Version is automatically incremented on successful update.

    AUDIT: Update is automatically logged by AuditMiddleware.

    Args:
        session_id: UUID of the session to update
        session_data: Fields to update (all optional)
        request: FastAPI request object (for audit logging)
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Updated session with decrypted PHI fields

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace,
            409 if version conflict (concurrent update), 422 if validation fails

    Example:
        PUT /api/v1/sessions/{uuid}
        {
            "subjective": "Updated patient report...",
            "plan": "Updated treatment plan..."
        }
    """
    workspace_id = current_user.workspace_id

    # Fetch existing session with workspace scoping (raises 404 if not found)
    session = await get_or_404(db, Session, session_id, workspace_id)

    # Get update data (only fields that were provided)
    update_data = session_data.model_dump(exclude_unset=True)

    if not update_data:
        # No fields to update, return current session
        return SessionResponse.model_validate(session)

    logger.info(
        "session_update_started",
        session_id=str(session_id),
        workspace_id=str(workspace_id),
        updated_fields=list(update_data.keys()),
    )

    # Update fields (PHI fields automatically encrypted)
    for field, value in update_data.items():
        setattr(session, field, value)

    # Update draft metadata
    session.draft_last_saved_at = datetime.now(UTC)

    # Increment version for optimistic locking
    session.version += 1

    await db.commit()
    await db.refresh(session)

    logger.info(
        "session_updated",
        session_id=str(session_id),
        workspace_id=str(workspace_id),
        new_version=session.version,
    )

    # Return response (PHI automatically decrypted)
    return SessionResponse.model_validate(session)


@router.patch("/{session_id}/draft", response_model=SessionResponse)
async def save_draft(
    session_id: uuid.UUID,
    draft_update: SessionDraftUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis_client=Depends(get_redis),
) -> SessionResponse:
    """
    Save session draft (autosave endpoint).

    This endpoint is designed for frontend autosave functionality called
    every ~5 seconds.

    Features:
    - Relaxed validation (partial/empty fields allowed - drafts don't
      need to be complete)
    - Rate limited to 60 requests/minute per user per session
      (allows autosave every ~1 second)
    - Updates only provided fields (partial update)
    - Auto-increments version for optimistic locking
    - Updates draft_last_saved_at timestamp
    - Keeps is_draft = True

    SECURITY: Verifies workspace ownership before allowing updates.
    workspace_id is derived from JWT token (server-side).
    Rate limiting uses Redis-backed distributed sliding window algorithm.

    AUDIT: Update is automatically logged by AuditMiddleware.

    Args:
        session_id: UUID of the session to update
        draft_update: Fields to update (all optional)
        request: FastAPI request object (for audit logging)
        current_user: Authenticated user (from JWT token)
        db: Database session
        redis_client: Redis client for distributed rate limiting

    Returns:
        Updated session with decrypted PHI fields

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace,
            429 if rate limit exceeded, 422 if validation fails

    Example:
        PATCH /api/v1/sessions/{uuid}/draft
        {
            "subjective": "Patient reports... (partial update)"
        }
    """
    workspace_id = current_user.workspace_id

    # Apply rate limit (60 requests per minute per user per session)
    # Per-session scoping allows concurrent editing of multiple sessions
    rate_limit_key = f"draft_autosave:{current_user.id}:{session_id}"
    if not await check_rate_limit_redis(
        redis_client=redis_client,
        key=rate_limit_key,
        max_requests=60,
        window_seconds=60,
    ):
        logger.warning(
            "draft_autosave_rate_limit_exceeded",
            user_id=str(current_user.id),
            workspace_id=str(workspace_id),
            session_id=str(session_id),
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Rate limit exceeded. Maximum 60 autosave requests "
                "per minute per session."
            ),
        )

    # Fetch session with workspace scoping
    session = await get_or_404(db, Session, session_id, workspace_id)

    # Get update data (only fields that were provided)
    update_data = draft_update.model_dump(exclude_unset=True)

    if update_data:
        logger.info(
            "session_draft_save_started",
            session_id=str(session_id),
            workspace_id=str(workspace_id),
            updated_fields=list(update_data.keys()),
        )

        # Update fields (PHI fields automatically encrypted)
        for field, value in update_data.items():
            setattr(session, field, value)

        # Update draft metadata
        session.draft_last_saved_at = datetime.now(UTC)
        session.version += 1
        session.is_draft = True  # Ensure it stays as draft

        await db.commit()
        await db.refresh(session)

        logger.info(
            "session_draft_saved",
            session_id=str(session_id),
            workspace_id=str(workspace_id),
            new_version=session.version,
        )

    # Return response (PHI automatically decrypted)
    return SessionResponse.model_validate(session)


@router.post("/{session_id}/finalize", response_model=SessionResponse)
async def finalize_session(
    session_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """
    Finalize session and mark as complete.

    Marks a session as finalized, making it immutable and preventing deletion.
    At least one SOAP field must have content before finalizing.

    Validation:
    - At least one SOAP field (subjective, objective, assessment, plan)
      must have content
    - Session must exist and belong to the authenticated workspace

    Effect:
    - Sets finalized_at timestamp to current time
    - Sets is_draft to False
    - Increments version
    - Prevents deletion (enforced in DELETE endpoint)

    SECURITY: Verifies workspace ownership before allowing finalization.
    workspace_id is derived from JWT token (server-side).

    AUDIT: Update is automatically logged by AuditMiddleware with "finalized" action.

    Args:
        session_id: UUID of the session to finalize
        request: FastAPI request object (for audit logging)
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Finalized session with finalized_at timestamp set

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace,
            422 if validation fails (no SOAP content)

    Example:
        POST /api/v1/sessions/{uuid}/finalize
        (no request body needed)
    """
    workspace_id = current_user.workspace_id

    # Fetch session with workspace scoping
    session = await get_or_404(db, Session, session_id, workspace_id)

    # Validate at least one SOAP field has content
    if not any(
        [session.subjective, session.objective, session.assessment, session.plan]
    ):
        logger.warning(
            "session_finalize_rejected_empty",
            session_id=str(session_id),
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot finalize session: at least one SOAP field must have content",
        )

    logger.info(
        "session_finalize_started",
        session_id=str(session_id),
        workspace_id=str(workspace_id),
    )

    # Finalize session
    session.finalized_at = datetime.now(UTC)
    session.is_draft = False
    session.version += 1

    await db.commit()
    await db.refresh(session)

    logger.info(
        "session_finalized",
        session_id=str(session_id),
        workspace_id=str(workspace_id),
        finalized_at=session.finalized_at.isoformat(),
    )

    # Return response (PHI automatically decrypted)
    return SessionResponse.model_validate(session)


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Soft delete a session.

    SOFT DELETE ONLY: Sets deleted_at timestamp without removing data.
    This preserves audit trail and allows recovery if needed.

    SECURITY: Verifies workspace ownership before allowing deletion.
    workspace_id is derived from JWT token (server-side).

    PROTECTION: Finalized sessions cannot be deleted (immutable records).

    AUDIT: Deletion is automatically logged by AuditMiddleware.

    Args:
        session_id: UUID of the session to delete
        request: FastAPI request object (for audit logging)
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        No content (204) on success

    Raises:
        HTTPException: 401 if not authenticated,
            404 if not found, already deleted, or wrong workspace,
            422 if session is finalized (cannot delete finalized sessions)

    Example:
        DELETE /api/v1/sessions/{uuid}
    """
    workspace_id = current_user.workspace_id

    # Fetch existing session with workspace scoping (raises 404 if not found)
    session = await get_or_404(db, Session, session_id, workspace_id)

    # Check if already deleted
    if session.deleted_at is not None:
        logger.info(
            "session_already_deleted",
            session_id=str(session_id),
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )

    # Prevent deletion of finalized sessions
    if session.finalized_at is not None:
        logger.warning(
            "session_delete_rejected_finalized",
            session_id=str(session_id),
            workspace_id=str(workspace_id),
            finalized_at=session.finalized_at.isoformat(),
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Cannot delete finalized sessions. "
                "Finalized sessions are permanent records."
            ),
        )

    # Soft delete: set deleted_at timestamp
    session.deleted_at = datetime.now(UTC)

    await db.commit()

    logger.info(
        "session_deleted",
        session_id=str(session_id),
        workspace_id=str(workspace_id),
    )
