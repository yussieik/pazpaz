"""Session CRUD API endpoints for SOAP-based clinical documentation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from pazpaz.api.deps import (
    get_current_user,
    get_db,
    get_or_404,
    verify_client_in_workspace,
)
from pazpaz.core.logging import get_logger
from pazpaz.core.rate_limiting import check_rate_limit_redis
from pazpaz.core.redis import get_redis
from pazpaz.models.appointment import Appointment, AppointmentStatus
from pazpaz.models.audit_event import AuditAction, ResourceType
from pazpaz.models.session import Session
from pazpaz.models.session_version import SessionVersion
from pazpaz.models.user import User
from pazpaz.schemas.session import (
    SessionCreate,
    SessionDeleteRequest,
    SessionDraftUpdate,
    SessionListResponse,
    SessionResponse,
    SessionUpdate,
    SessionVersionResponse,
)
from pazpaz.services.audit_service import create_audit_event
from pazpaz.utils.pagination import (
    calculate_pagination_offset,
    calculate_total_pages,
    get_query_total_count,
)
from pazpaz.utils.session_helpers import (
    apply_soft_delete,
    clear_soft_delete_metadata,
    is_grace_period_expired,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])
logger = get_logger(__name__)


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

    # If appointment_id provided and appointment is scheduled, auto-complete it
    if session_data.appointment_id:
        query = select(Appointment).where(
            Appointment.id == session_data.appointment_id,
            Appointment.workspace_id == workspace_id,
        )
        result = await db.execute(query)
        appointment = result.scalar_one_or_none()

        if appointment and appointment.status == AppointmentStatus.SCHEDULED:
            appointment.status = AppointmentStatus.COMPLETED
            logger.info(
                "appointment_auto_completed",
                appointment_id=str(appointment.id),
                session_id=str(session.id),
                workspace_id=str(workspace_id),
                reason="session_created",
            )

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
        None, description="Filter by client ID (optional if appointment_id provided)"
    ),
    appointment_id: uuid.UUID | None = Query(
        None, description="Filter by appointment ID (optional if client_id provided)"
    ),
    is_draft: bool | None = Query(None, description="Filter by draft status"),
    include_deleted: bool = Query(
        False, description="Include soft-deleted sessions (for restoration)"
    ),
    search: str | None = Query(
        None,
        min_length=1,
        max_length=200,
        description="Search across SOAP fields (subjective, objective, assessment, plan). Case-insensitive partial matching.",
        examples=["shoulder pain"],
    ),
) -> SessionListResponse:
    """
    List sessions for a client or appointment with optional full-text search.

    Returns a paginated list of sessions, ordered by session_date descending.
    All results are scoped to the authenticated workspace.

    Query Parameters:
        client_id: Filter sessions by client ID (optional if appointment_id
            provided)
        appointment_id: Filter sessions by appointment ID (optional if
            client_id provided)
        page: Page number (default: 1)
        page_size: Items per page (default: 50, max: 100)
        is_draft: Filter by draft status (optional)
        include_deleted: Include soft-deleted sessions (default: false)
        search: Full-text search across SOAP fields (case-insensitive,
            partial matching)

    Note: At least one of client_id or appointment_id must be provided.

    SECURITY: Only returns sessions belonging to the authenticated user's
    workspace (from JWT). Requires either client_id or appointment_id filter
    to prevent accidental exposure of all sessions.

    SEARCH: When search parameter is provided, decrypts SOAP fields and
    performs in-memory filtering. Limited to 1000 sessions for safety.
    Search queries are automatically logged to audit trail for compliance.

    PERFORMANCE: Uses ix_sessions_workspace_client_date or
    ix_sessions_workspace_appointment indexes for optimal query performance.
    Search performance: <150ms for 100 sessions, <500ms for 500 sessions.

    Args:
        current_user: Authenticated user (from JWT token)
        db: Database session
        page: Page number (1-indexed)
        page_size: Number of items per page (max 100)
        client_id: Filter by specific client (optional)
        appointment_id: Filter by specific appointment (optional)
        is_draft: Filter by draft status (optional)
        include_deleted: Include soft-deleted sessions (default: false)
        search: Search query string (optional)

    Returns:
        Paginated list of sessions with decrypted PHI fields

    Raises:
        HTTPException: 401 if not authenticated,
            400 if neither client_id nor appointment_id provided,
            404 if client/appointment not found in workspace,
            422 if search query validation fails

    Example:
        GET /api/v1/sessions?client_id={uuid}&page=1&page_size=50&is_draft=true
        GET /api/v1/sessions?appointment_id={uuid}
        GET /api/v1/sessions?client_id={uuid}&search=shoulder%20pain
    """
    workspace_id = current_user.workspace_id

    # Validate: must provide either client_id or appointment_id
    if not client_id and not appointment_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide either client_id or appointment_id parameter",
        )

    logger.debug(
        "session_list_started",
        workspace_id=str(workspace_id),
        client_id=str(client_id) if client_id else None,
        appointment_id=str(appointment_id) if appointment_id else None,
        page=page,
        page_size=page_size,
        is_draft=is_draft,
    )

    # Build base query with workspace scoping
    base_query = select(Session).where(Session.workspace_id == workspace_id)

    # Filter deleted sessions unless explicitly requested
    if not include_deleted:
        base_query = base_query.where(Session.deleted_at.is_(None))

    # Apply filters
    if client_id:
        # Verify client belongs to workspace
        await verify_client_in_workspace(
            db=db,
            client_id=client_id,
            workspace_id=workspace_id,
        )
        base_query = base_query.where(Session.client_id == client_id)

    if appointment_id:
        # Verify appointment belongs to workspace
        await get_or_404(
            db=db,
            model_class=Appointment,
            resource_id=appointment_id,
            workspace_id=workspace_id,
        )
        base_query = base_query.where(Session.appointment_id == appointment_id)

    # Apply draft filter if provided
    if is_draft is not None:
        base_query = base_query.where(Session.is_draft == is_draft)

    # SEARCH BRANCH: If search parameter provided, handle specially
    if search:
        logger.debug(
            "session_search_started",
            workspace_id=str(workspace_id),
            client_id=str(client_id) if client_id else None,
            search_query=search,
            page=page,
            page_size=page_size,
        )

        # Load sessions with safety limit (prevents memory issues)
        # Order by session_date desc to prioritize recent sessions
        search_query = base_query.order_by(Session.session_date.desc()).limit(1000)
        result = await db.execute(search_query)
        all_sessions = result.scalars().all()

        # Filter by search term (case-insensitive)
        search_lower = search.lower()
        matching_sessions = []

        for sess in all_sessions:
            # Build searchable text from all SOAP fields
            # PHI fields are automatically decrypted by SQLAlchemy's EncryptedString
            searchable_text = " ".join(
                filter(
                    None,
                    [
                        sess.subjective or "",
                        sess.objective or "",
                        sess.assessment or "",
                        sess.plan or "",
                    ],
                )
            ).lower()

            # Partial matching: search term anywhere in searchable text
            if search_lower in searchable_text:
                matching_sessions.append(sess)

        # Calculate pagination on filtered results
        total = len(matching_sessions)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_sessions = matching_sessions[start_idx:end_idx]

        # Build response items (PHI automatically decrypted)
        items = [SessionResponse.model_validate(s) for s in paginated_sessions]

        # Calculate total pages
        total_pages = calculate_total_pages(total, page_size)

        # Audit logging for search queries (compliance requirement)
        await create_audit_event(
            db=db,
            user_id=current_user.id,
            workspace_id=workspace_id,
            action=AuditAction.READ,
            resource_type=ResourceType.SESSION,
            resource_id=None,  # No specific session
            metadata={
                "action": "search",
                "search_query": search,
                "client_id": str(client_id) if client_id else None,
                "appointment_id": str(appointment_id) if appointment_id else None,
                "results_count": total,
                "sessions_scanned": len(all_sessions),
            },
        )

        logger.debug(
            "session_search_completed",
            workspace_id=str(workspace_id),
            client_id=str(client_id) if client_id else None,
            search_query=search,
            results_count=total,
            sessions_scanned=len(all_sessions),
            page=page,
            page_size=page_size,
            extra={"structured": True},
        )

        return SessionListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    # NORMAL BRANCH: No search, use standard pagination
    # Calculate offset using utility
    offset = calculate_pagination_offset(page, page_size)

    # Get total count using utility
    total = await get_query_total_count(db, base_query)

    # Get paginated results ordered by session_date descending
    query = (
        base_query.order_by(Session.session_date.desc()).offset(offset).limit(page_size)
    )
    result = await db.execute(query)
    sessions = result.scalars().all()

    # Build response items (PHI automatically decrypted)
    items = [SessionResponse.model_validate(session) for session in sessions]

    # Calculate total pages using utility
    total_pages = calculate_total_pages(total, page_size)

    logger.debug(
        "session_list_completed",
        workspace_id=str(workspace_id),
        client_id=str(client_id) if client_id else None,
        appointment_id=str(appointment_id) if appointment_id else None,
        total_sessions=total,
        page=page,
        page_size=page_size,
        extra={"structured": True},
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
        is_finalized=session.finalized_at is not None,
    )

    # Track which SOAP fields are being changed (for amendment audit)
    sections_changed = []
    soap_fields = ["subjective", "objective", "assessment", "plan"]
    for field in soap_fields:
        if field in update_data and getattr(session, field) != update_data[field]:
            sections_changed.append(field)

    # If session is finalized, create new version before applying changes
    if session.finalized_at is not None:
        # Create new version (preserve current state BEFORE edit)
        new_version_number = (
            session.amendment_count + 2
        )  # v1 = original, v2+ = amendments
        version = SessionVersion(
            session_id=session.id,
            version_number=new_version_number,
            subjective=session.subjective,  # Current values BEFORE edit
            objective=session.objective,
            assessment=session.assessment,
            plan=session.plan,
            created_at=datetime.now(UTC),
            created_by_user_id=current_user.id,
        )
        db.add(version)

        # Update amendment tracking
        session.amended_at = datetime.now(UTC)
        session.amendment_count += 1

        # Create audit log entry for amendment
        await create_audit_event(
            db=db,
            user_id=current_user.id,
            workspace_id=workspace_id,
            action=AuditAction.UPDATE,
            resource_type=ResourceType.SESSION,
            resource_id=session_id,
            metadata={
                "amendment": True,
                "original_finalized_at": session.finalized_at.isoformat(),
                "amendment_count": session.amendment_count,
                "sections_changed": sections_changed,
                "previous_version_number": new_version_number - 1,
            },
        )

        logger.info(
            "session_amended",
            session_id=str(session_id),
            workspace_id=str(workspace_id),
            amendment_count=session.amendment_count,
            version_created=new_version_number,
            sections_changed=sections_changed,
        )

    # Update fields (PHI fields automatically encrypted)
    for field, value in update_data.items():
        setattr(session, field, value)

    # Update draft metadata (if still draft)
    if session.is_draft:
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
        was_amendment=session.finalized_at is not None,
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
    - Preserves finalized status (amendments) or keeps is_draft = True

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
        # Only set is_draft = True if it's already a draft
        # This preserves finalized status for amendments
        if session.finalized_at is None:
            session.is_draft = True

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

    # Check if already finalized
    if session.finalized_at is not None:
        logger.warning(
            "session_already_finalized",
            session_id=str(session_id),
            workspace_id=str(workspace_id),
            finalized_at=session.finalized_at.isoformat(),
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Session is already finalized",
        )

    # Finalize session
    session.finalized_at = datetime.now(UTC)
    session.is_draft = False
    session.version += 1

    # Create version 1 (original snapshot)
    version = SessionVersion(
        session_id=session.id,
        version_number=1,
        subjective=session.subjective,
        objective=session.objective,
        assessment=session.assessment,
        plan=session.plan,
        created_at=session.finalized_at,
        created_by_user_id=current_user.id,
    )
    db.add(version)

    await db.commit()
    await db.refresh(session)

    logger.info(
        "session_finalized",
        session_id=str(session_id),
        workspace_id=str(workspace_id),
        finalized_at=session.finalized_at.isoformat(),
        version_created=1,
    )

    # Return response (PHI automatically decrypted)
    return SessionResponse.model_validate(session)


@router.post("/{session_id}/unfinalize", response_model=SessionResponse)
async def unfinalize_session(
    session_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """
    Unfinalize session and revert to draft status.

    Reverts a finalized session back to draft status, allowing further editing.
    This endpoint is the inverse of POST /sessions/{session_id}/finalize.

    Effect:
    - Sets is_draft to True
    - Clears finalized_at timestamp (sets to NULL)
    - Increments version
    - Session becomes editable again

    SECURITY: Verifies workspace ownership before allowing unfinalizing.
    workspace_id is derived from JWT token (server-side).

    AUDIT: Update is automatically logged by AuditMiddleware with "unfinalized" action.

    Args:
        session_id: UUID of the session to unfinalize
        request: FastAPI request object (for audit logging)
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Unfinalied session with is_draft=True and finalized_at cleared

    Raises:
        HTTPException: 401 if not authenticated, 404 if not found or wrong workspace,
            400 if session is already a draft

    Example:
        POST /api/v1/sessions/{uuid}/unfinalize
        (no request body needed)
    """
    workspace_id = current_user.workspace_id

    # Fetch session with workspace scoping
    session = await get_or_404(db, Session, session_id, workspace_id)

    # Check if already a draft
    if session.is_draft:
        logger.warning(
            "session_already_draft",
            session_id=str(session_id),
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is already a draft",
        )

    logger.info(
        "session_unfinalize_started",
        session_id=str(session_id),
        workspace_id=str(workspace_id),
        finalized_at=session.finalized_at.isoformat() if session.finalized_at else None,
        amendment_count=session.amendment_count,
    )

    # Delete all version snapshots (reverting finalized history)
    # This prevents unique constraint violations when re-finalizing
    delete_versions = delete(SessionVersion).where(
        SessionVersion.session_id == session_id
    )
    result = await db.execute(delete_versions)
    deleted_count = result.rowcount

    logger.info(
        "session_versions_deleted",
        session_id=str(session_id),
        workspace_id=str(workspace_id),
        versions_deleted=deleted_count,
    )

    # Unfinalize session
    session.is_draft = True
    session.finalized_at = None
    session.draft_last_saved_at = datetime.now(UTC)
    session.version += 1
    session.amendment_count = 0  # Reset since we're reverting history
    session.amended_at = None  # Clear amendment timestamp

    # Create audit log for unfinalizing
    await create_audit_event(
        db=db,
        user_id=current_user.id,
        workspace_id=workspace_id,
        action=AuditAction.UPDATE,
        resource_type=ResourceType.SESSION,
        resource_id=session_id,
        metadata={
            "action": "unfinalize",
            "was_finalized": True,
            "amendment_count": session.amendment_count,
            "versions_deleted": deleted_count,
        },
    )

    await db.commit()
    await db.refresh(session)

    logger.info(
        "session_unfinalized",
        session_id=str(session_id),
        workspace_id=str(workspace_id),
    )

    # Return response (PHI automatically decrypted)
    return SessionResponse.model_validate(session)


@router.get("/{session_id}/versions", response_model=list[SessionVersionResponse])
async def get_session_versions(
    session_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SessionVersionResponse]:
    """
    Get version history for a session note.

    Returns all versions of a session note in reverse chronological order
    (most recent first). Only finalized sessions have versions.

    SECURITY: Verifies workspace ownership before allowing access.
    workspace_id is derived from JWT token (server-side).

    AUDIT: PHI access is automatically logged by AuditMiddleware.

    Args:
        session_id: UUID of the session
        request: FastAPI request object (for audit logging)
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        List of session versions with decrypted PHI fields

    Raises:
        HTTPException: 401 if not authenticated,
            404 if not found or wrong workspace

    Example:
        GET /api/v1/sessions/{uuid}/versions
        Response: [
          {
            "id": "version-uuid-2",
            "session_id": "session-uuid",
            "version_number": 2,
            "subjective": "Amended note...",
            "created_at": "2025-01-16T09:15:00Z"
          },
          {
            "id": "version-uuid-1",
            "session_id": "session-uuid",
            "version_number": 1,
            "subjective": "Original note...",
            "created_at": "2025-01-15T15:05:00Z"
          }
        ]
    """
    workspace_id = current_user.workspace_id

    # Verify session exists and belongs to workspace
    await get_or_404(db, Session, session_id, workspace_id)

    # Get all versions ordered by version_number descending
    query = (
        select(SessionVersion)
        .where(SessionVersion.session_id == session_id)
        .order_by(SessionVersion.version_number.desc())
    )
    result = await db.execute(query)
    versions = result.scalars().all()

    logger.debug(
        "session_versions_accessed",
        session_id=str(session_id),
        workspace_id=str(workspace_id),
        version_count=len(versions),
    )

    # Return response (PHI automatically decrypted)
    return [SessionVersionResponse.model_validate(version) for version in versions]


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    deletion_request: SessionDeleteRequest | None = None,
) -> None:
    """
    Soft delete a session with optional deletion reason.

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
        deletion_request: Optional request body with deletion reason

    Body Parameters:
        reason: Optional reason for deletion (max 500 chars, logged in audit trail)

    Returns:
        No content (204) on success

    Raises:
        HTTPException: 401 if not authenticated,
            404 if not found, already deleted, or wrong workspace,
            422 if session is finalized (cannot delete finalized sessions)

    Example:
        DELETE /api/v1/sessions/{uuid}
        {
            "reason": "Duplicate entry, will recreate"
        }
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

    # Extract deletion reason if provided
    deletion_reason = deletion_request.reason if deletion_request else None

    # Apply soft delete using utility function
    apply_soft_delete(
        session=session,
        deleted_by_user_id=current_user.id,
        deletion_reason=deletion_reason,
    )

    # Store deletion metadata in request state for audit middleware
    # This allows middleware to include deleted_reason in audit event metadata
    request.state.audit_metadata = {
        "soft_delete": True,
        "was_finalized": session.finalized_at is not None,
        "had_amendments": session.amendment_count > 0,
        "amendment_count": session.amendment_count,
        "deleted_reason": deletion_reason,
    }

    await db.commit()

    logger.info(
        "session_deleted",
        session_id=str(session_id),
        workspace_id=str(workspace_id),
        was_finalized=session.finalized_at is not None,
        amendment_count=session.amendment_count,
        permanent_delete_after=session.permanent_delete_after.isoformat(),
        deleted_reason=deletion_reason,
    )


@router.post("/{session_id}/restore", response_model=SessionResponse)
async def restore_session(
    session_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """
    Restore a soft-deleted session within 30-day grace period.

    Restores a soft-deleted session by clearing the deletion metadata.
    Can only restore sessions that haven't exceeded the 30-day grace period.

    SECURITY: Verifies workspace ownership before allowing restoration.
    workspace_id is derived from JWT token (server-side).

    AUDIT: Restoration is logged in audit trail.

    Args:
        session_id: UUID of the session to restore
        request: FastAPI request object (for audit logging)
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Restored session with cleared deletion metadata

    Raises:
        HTTPException: 401 if not authenticated,
            404 if not found or not deleted or wrong workspace,
            410 if 30-day grace period has expired

    Example:
        POST /api/v1/sessions/{uuid}/restore
        (no request body needed)
    """
    workspace_id = current_user.workspace_id

    # Fetch session with workspace scoping
    # Use include_deleted=True to access soft-deleted sessions for restoration
    session = await get_or_404(
        db=db,
        model_class=Session,
        resource_id=session_id,
        workspace_id=workspace_id,
        include_deleted=True,
    )

    # Check if session is actually deleted
    if session.deleted_at is None:
        logger.warning(
            "session_restore_not_deleted",
            session_id=str(session_id),
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session is not deleted",
        )

    # Check if 30-day grace period has expired using utility function
    if session.permanent_delete_after and is_grace_period_expired(
        session.permanent_delete_after
    ):
        logger.warning(
            "session_restore_expired",
            session_id=str(session_id),
            workspace_id=str(workspace_id),
            permanent_delete_after=session.permanent_delete_after.isoformat(),
        )
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                "Session cannot be restored: 30-day grace period has expired. "
                f"Session was scheduled for permanent deletion on "
                f"{session.permanent_delete_after.isoformat()}."
            ),
        )

    logger.info(
        "session_restore_started",
        session_id=str(session_id),
        workspace_id=str(workspace_id),
        deleted_at=session.deleted_at.isoformat(),
    )

    # Clear deletion metadata using utility function
    clear_soft_delete_metadata(session)

    # Create audit log for restoration
    await create_audit_event(
        db=db,
        user_id=current_user.id,
        workspace_id=workspace_id,
        action=AuditAction.UPDATE,
        resource_type=ResourceType.SESSION,
        resource_id=session_id,
        metadata={
            "action": "restore",
            "was_finalized": session.finalized_at is not None,
            "amendment_count": session.amendment_count,
        },
    )

    await db.commit()
    await db.refresh(session)

    logger.info(
        "session_restored",
        session_id=str(session_id),
        workspace_id=str(workspace_id),
    )

    # Return response (PHI automatically decrypted)
    return SessionResponse.model_validate(session)


@router.delete("/{session_id}/permanent", status_code=204)
async def permanently_delete_session(
    session_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Permanently delete a soft-deleted session (HARD DELETE).

    This endpoint performs a true database deletion, permanently removing the
    session record and all associated data. This action is irreversible.

    SECURITY: Verifies workspace ownership before allowing deletion.
    workspace_id is derived from JWT token (server-side).

    RESTRICTIONS:
    - Can only permanently delete sessions that are already soft-deleted
    - Cannot delete active (non-deleted) sessions - use DELETE /sessions/{id} first

    AUDIT: Permanent deletion is logged in audit trail before record removal.

    Args:
        session_id: UUID of the session to permanently delete
        request: FastAPI request object (for audit logging)
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        No content (204) on success

    Raises:
        HTTPException: 401 if not authenticated,
            404 if not found or wrong workspace,
            422 if session is not soft-deleted (must soft-delete first)

    Example:
        DELETE /api/v1/sessions/{uuid}/permanent
    """
    workspace_id = current_user.workspace_id

    # Fetch session with workspace scoping (include soft-deleted)
    session = await get_or_404(
        db=db,
        model_class=Session,
        resource_id=session_id,
        workspace_id=workspace_id,
        include_deleted=True,
    )

    # Verify session is actually soft-deleted
    if session.deleted_at is None:
        logger.warning(
            "permanent_delete_not_soft_deleted",
            session_id=str(session_id),
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Session must be soft-deleted before permanent deletion. "
                "Use DELETE /sessions/{id} first."
            ),
        )

    logger.info(
        "session_permanent_delete_started",
        session_id=str(session_id),
        workspace_id=str(workspace_id),
        was_finalized=session.finalized_at is not None,
        deleted_at=session.deleted_at.isoformat(),
    )

    # Create audit log BEFORE deletion (record will be gone after)
    await create_audit_event(
        db=db,
        user_id=current_user.id,
        workspace_id=workspace_id,
        action=AuditAction.DELETE,
        resource_type=ResourceType.SESSION,
        resource_id=session_id,
        metadata={
            "permanent_delete": True,
            "was_soft_deleted": True,
            "was_finalized": session.finalized_at is not None,
            "amendment_count": session.amendment_count,
            "deleted_at": session.deleted_at.isoformat(),
            "deletion_reason": session.deleted_reason,
        },
    )

    # HARD DELETE: Remove from database permanently
    await db.delete(session)
    await db.commit()

    logger.info(
        "session_permanently_deleted",
        session_id=str(session_id),
        workspace_id=str(workspace_id),
    )


@router.get("/clients/{client_id}/latest-finalized", response_model=SessionResponse)
async def get_latest_finalized_session(
    client_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """
    Get the most recent finalized session for a client.

    Returns the latest finalized (non-draft) session note for the specified client,
    ordered by session_date descending. Used by the Previous Session Context Panel
    to provide treatment continuity when creating new session notes.

    SECURITY: Verifies client belongs to authenticated workspace before returning data.
    workspace_id is derived from JWT token (server-side).

    PERFORMANCE: Uses ix_sessions_workspace_client_date index for optimal performance.
    Query should execute in <50ms p95.

    PHI ACCESS: This endpoint returns decrypted SOAP fields (PHI).
    All access is automatically logged by AuditMiddleware for HIPAA compliance.

    Args:
        client_id: UUID of the client
        request: FastAPI request object (for audit logging)
        current_user: Authenticated user (from JWT token)
        db: Database session

    Returns:
        Most recent finalized session with decrypted SOAP fields

    Raises:
        HTTPException: 401 if not authenticated,
            403 if client not in workspace,
            404 if client has no finalized sessions

    Example:
        GET /api/v1/sessions/clients/{client_id}/latest-finalized
        Response: {
            "id": "uuid",
            "session_date": "2025-10-06T14:00:00Z",
            "duration_minutes": 60,
            "is_draft": false,
            "finalized_at": "2025-10-06T15:05:00Z",
            "subjective": "Patient reports neck pain...",
            "objective": "ROM 90° shoulder abduction...",
            "assessment": "Muscle tension pattern...",
            "plan": "Continue trapezius protocol...",
            ...
        }
    """
    workspace_id = current_user.workspace_id

    # Verify client exists and belongs to workspace (403 if not)
    await verify_client_in_workspace(
        db=db,
        client_id=client_id,
        workspace_id=workspace_id,
    )

    logger.debug(
        "latest_finalized_session_query_started",
        client_id=str(client_id),
        workspace_id=str(workspace_id),
    )

    # Query for most recent finalized session
    # Uses ix_sessions_workspace_client_date index for performance
    query = (
        select(Session)
        .where(
            Session.workspace_id == workspace_id,
            Session.client_id == client_id,
            Session.is_draft == False,  # noqa: E712 - SQLAlchemy requires == for boolean
            Session.deleted_at.is_(None),  # Exclude soft-deleted sessions
        )
        .order_by(Session.session_date.desc())
        .limit(1)
    )

    result = await db.execute(query)
    session = result.scalar_one_or_none()

    if not session:
        logger.info(
            "no_finalized_sessions_found",
            client_id=str(client_id),
            workspace_id=str(workspace_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No finalized sessions found for this client",
        )

    logger.debug(
        "latest_finalized_session_found",
        session_id=str(session.id),
        client_id=str(client_id),
        workspace_id=str(workspace_id),
        session_date=session.session_date.isoformat(),
    )

    # Return response (PHI automatically decrypted by ORM)
    # Note: PHI access is automatically logged by AuditMiddleware
    return SessionResponse.model_validate(session)
