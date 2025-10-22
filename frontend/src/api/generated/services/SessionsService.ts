/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
 
import type { SessionCreate } from '../models/SessionCreate';
import type { SessionDeleteRequest } from '../models/SessionDeleteRequest';
import type { SessionDraftUpdate } from '../models/SessionDraftUpdate';
import type { SessionListResponse } from '../models/SessionListResponse';
import type { SessionResponse } from '../models/SessionResponse';
import type { SessionUpdate } from '../models/SessionUpdate';
import type { SessionVersionResponse } from '../models/SessionVersionResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class SessionsService {
    /**
     * Create Session
     * Create a new SOAP session note.
     *
     * Creates a new session after verifying:
     * 1. Client belongs to the workspace
     * 2. Session date is not in the future (validated by Pydantic)
     *
     * SECURITY: workspace_id is derived from authenticated user's JWT token (server-side).
     * All PHI fields (subjective, objective, assessment, plan) are automatically encrypted
     * at rest using AES-256-GCM via the EncryptedString type.
     *
     * AUDIT: Creation is automatically logged by AuditMiddleware.
     *
     * Args:
     * session_data: Session creation data (without workspace_id)
     * request: FastAPI request object (for audit logging)
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     *
     * Returns:
     * Created session with encrypted PHI fields
     *
     * Raises:
     * HTTPException: 401 if not authenticated, 404 if client not found,
     * 422 if validation fails
     *
     * Example:
     * POST /api/v1/sessions
     * {
         * "client_id": "uuid",
         * "session_date": "2025-10-08T14:30:00Z",
         * "subjective": "Patient reports...",
         * "objective": "Observations...",
         * "assessment": "Clinical assessment...",
         * "plan": "Treatment plan..."
         * }
         * @param requestBody
         * @param accessToken
         * @returns SessionResponse Successful Response
         * @throws ApiError
         */
        public static createSessionApiV1SessionsPost(
            requestBody: SessionCreate,
            accessToken?: (string | null),
        ): CancelablePromise<SessionResponse> {
            return __request(OpenAPI, {
                method: 'POST',
                url: '/api/v1/sessions',
                cookies: {
                    'access_token': accessToken,
                },
                body: requestBody,
                mediaType: 'application/json',
                errors: {
                    422: `Validation Error`,
                },
            });
        }
        /**
         * List Sessions
         * List sessions for a client or appointment with optional full-text search.
         *
         * Returns a paginated list of sessions, ordered by session_date descending.
         * All results are scoped to the authenticated workspace.
         *
         * Query Parameters:
         * client_id: Filter sessions by client ID (optional if appointment_id
         * provided)
         * appointment_id: Filter sessions by appointment ID (optional if
         * client_id provided)
         * page: Page number (default: 1)
         * page_size: Items per page (default: 50, max: 100)
         * is_draft: Filter by draft status (optional)
         * include_deleted: Include soft-deleted sessions (default: false)
         * search: Full-text search across SOAP fields (case-insensitive,
         * partial matching)
         *
         * Note: At least one of client_id or appointment_id must be provided.
         *
         * SECURITY: Only returns sessions belonging to the authenticated user's
         * workspace (from JWT). Requires either client_id or appointment_id filter
         * to prevent accidental exposure of all sessions.
         *
         * SEARCH: When search parameter is provided, decrypts SOAP fields and
         * performs in-memory filtering. Limited to 1000 sessions for safety.
         * Search queries are automatically logged to audit trail for compliance.
         *
         * PERFORMANCE: Uses ix_sessions_workspace_client_date or
         * ix_sessions_workspace_appointment indexes for optimal query performance.
         * Search performance: <150ms for 100 sessions, <500ms for 500 sessions.
         *
         * Args:
         * current_user: Authenticated user (from JWT token)
         * db: Database session
         * page: Page number (1-indexed)
         * page_size: Number of items per page (max 100)
         * client_id: Filter by specific client (optional)
         * appointment_id: Filter by specific appointment (optional)
         * is_draft: Filter by draft status (optional)
         * include_deleted: Include soft-deleted sessions (default: false)
         * search: Search query string (optional)
         *
         * Returns:
         * Paginated list of sessions with decrypted PHI fields
         *
         * Raises:
         * HTTPException: 401 if not authenticated,
         * 400 if neither client_id nor appointment_id provided,
         * 404 if client/appointment not found in workspace,
         * 422 if search query validation fails
         *
         * Example:
         * GET /api/v1/sessions?client_id={uuid}&page=1&page_size=50&is_draft=true
         * GET /api/v1/sessions?appointment_id={uuid}
         * GET /api/v1/sessions?client_id={uuid}&search=shoulder%20pain
         * @param page Page number (1-indexed)
         * @param pageSize Items per page
         * @param clientId Filter by client ID (optional if appointment_id provided)
         * @param appointmentId Filter by appointment ID (optional if client_id provided)
         * @param isDraft Filter by draft status
         * @param includeDeleted Include soft-deleted sessions (for restoration)
         * @param search Search across SOAP fields (subjective, objective, assessment, plan). Case-insensitive partial matching.
         * @param accessToken
         * @returns SessionListResponse Successful Response
         * @throws ApiError
         */
        public static listSessionsApiV1SessionsGet(
            page: number = 1,
            pageSize: number = 50,
            clientId?: (string | null),
            appointmentId?: (string | null),
            isDraft?: (boolean | null),
            includeDeleted: boolean = false,
            search?: (string | null),
            accessToken?: (string | null),
        ): CancelablePromise<SessionListResponse> {
            return __request(OpenAPI, {
                method: 'GET',
                url: '/api/v1/sessions',
                cookies: {
                    'access_token': accessToken,
                },
                query: {
                    'page': page,
                    'page_size': pageSize,
                    'client_id': clientId,
                    'appointment_id': appointmentId,
                    'is_draft': isDraft,
                    'include_deleted': includeDeleted,
                    'search': search,
                },
                errors: {
                    422: `Validation Error`,
                },
            });
        }
        /**
         * Get Session
         * Get a single session by ID with decrypted SOAP fields.
         *
         * Retrieves a session by ID, ensuring it belongs to the authenticated workspace.
         * PHI fields are automatically decrypted from database storage.
         *
         * SECURITY: Returns 404 for both non-existent sessions and sessions in other
         * workspaces to prevent information leakage. workspace_id is derived from JWT token.
         *
         * AUDIT: PHI access is manually logged via create_audit_event.
         *
         * Args:
         * session_id: UUID of the session
         * request: FastAPI request object (for audit logging)
         * current_user: Authenticated user (from JWT token)
         * db: Database session
         *
         * Returns:
         * Session details with decrypted PHI fields and attachment count
         *
         * Raises:
         * HTTPException: 401 if not authenticated,
         * 404 if not found or wrong workspace
         *
         * Example:
         * GET /api/v1/sessions/{uuid}
         * @param sessionId
         * @param accessToken
         * @returns SessionResponse Successful Response
         * @throws ApiError
         */
        public static getSessionApiV1SessionsSessionIdGet(
            sessionId: string,
            accessToken?: (string | null),
        ): CancelablePromise<SessionResponse> {
            return __request(OpenAPI, {
                method: 'GET',
                url: '/api/v1/sessions/{session_id}',
                path: {
                    'session_id': sessionId,
                },
                cookies: {
                    'access_token': accessToken,
                },
                errors: {
                    422: `Validation Error`,
                },
            });
        }
        /**
         * Update Session
         * Update an existing session with partial updates.
         *
         * Updates session fields. Only provided fields are updated (partial updates).
         * Session must belong to the authenticated workspace.
         *
         * SECURITY: Verifies workspace ownership before allowing updates.
         * workspace_id is derived from JWT token (server-side).
         * Updated PHI fields are automatically encrypted at rest.
         *
         * OPTIMISTIC LOCKING: Uses version field to prevent concurrent update conflicts.
         * Version is automatically incremented on successful update.
         *
         * AUDIT: Update is automatically logged by AuditMiddleware.
         *
         * Args:
         * session_id: UUID of the session to update
         * session_data: Fields to update (all optional)
         * request: FastAPI request object (for audit logging)
         * current_user: Authenticated user (from JWT token)
         * db: Database session
         *
         * Returns:
         * Updated session with decrypted PHI fields
         *
         * Raises:
         * HTTPException: 401 if not authenticated, 404 if not found or wrong workspace,
         * 409 if version conflict (concurrent update), 422 if validation fails
         *
         * Example:
         * PUT /api/v1/sessions/{uuid}
         * {
             * "subjective": "Updated patient report...",
             * "plan": "Updated treatment plan..."
             * }
             * @param sessionId
             * @param requestBody
             * @param accessToken
             * @returns SessionResponse Successful Response
             * @throws ApiError
             */
            public static updateSessionApiV1SessionsSessionIdPut(
                sessionId: string,
                requestBody: SessionUpdate,
                accessToken?: (string | null),
            ): CancelablePromise<SessionResponse> {
                return __request(OpenAPI, {
                    method: 'PUT',
                    url: '/api/v1/sessions/{session_id}',
                    path: {
                        'session_id': sessionId,
                    },
                    cookies: {
                        'access_token': accessToken,
                    },
                    body: requestBody,
                    mediaType: 'application/json',
                    errors: {
                        422: `Validation Error`,
                    },
                });
            }
            /**
             * Delete Session
             * Soft delete a session with optional deletion reason.
             *
             * SOFT DELETE ONLY: Sets deleted_at timestamp without removing data.
             * This preserves audit trail and allows recovery if needed.
             *
             * SECURITY: Verifies workspace ownership before allowing deletion.
             * workspace_id is derived from JWT token (server-side).
             *
             * PROTECTION: Finalized sessions cannot be deleted (immutable records).
             *
             * AUDIT: Deletion is automatically logged by AuditMiddleware.
             *
             * Args:
             * session_id: UUID of the session to delete
             * request: FastAPI request object (for audit logging)
             * current_user: Authenticated user (from JWT token)
             * db: Database session
             * deletion_request: Optional request body with deletion reason
             *
             * Body Parameters:
             * reason: Optional reason for deletion (max 500 chars, logged in audit trail)
             *
             * Returns:
             * No content (204) on success
             *
             * Raises:
             * HTTPException: 401 if not authenticated,
             * 404 if not found, already deleted, or wrong workspace,
             * 422 if session is finalized (cannot delete finalized sessions)
             *
             * Example:
             * DELETE /api/v1/sessions/{uuid}
             * {
                 * "reason": "Duplicate entry, will recreate"
                 * }
                 * @param sessionId
                 * @param accessToken
                 * @param requestBody
                 * @returns void
                 * @throws ApiError
                 */
                public static deleteSessionApiV1SessionsSessionIdDelete(
                    sessionId: string,
                    accessToken?: (string | null),
                    requestBody?: (SessionDeleteRequest | null),
                ): CancelablePromise<void> {
                    return __request(OpenAPI, {
                        method: 'DELETE',
                        url: '/api/v1/sessions/{session_id}',
                        path: {
                            'session_id': sessionId,
                        },
                        cookies: {
                            'access_token': accessToken,
                        },
                        body: requestBody,
                        mediaType: 'application/json',
                        errors: {
                            422: `Validation Error`,
                        },
                    });
                }
                /**
                 * Save Draft
                 * Save session draft (autosave endpoint).
                 *
                 * This endpoint is designed for frontend autosave functionality called
                 * every ~5 seconds.
                 *
                 * Features:
                 * - Relaxed validation (partial/empty fields allowed - drafts don't
                 * need to be complete)
                 * - Rate limited to 60 requests/minute per user per session
                 * (allows autosave every ~1 second)
                 * - Updates only provided fields (partial update)
                 * - Auto-increments version for optimistic locking
                 * - Updates draft_last_saved_at timestamp
                 * - Preserves finalized status (amendments) or keeps is_draft = True
                 *
                 * SECURITY: Verifies workspace ownership before allowing updates.
                 * workspace_id is derived from JWT token (server-side).
                 * Rate limiting uses Redis-backed distributed sliding window algorithm.
                 *
                 * AUDIT: Update is automatically logged by AuditMiddleware.
                 *
                 * Args:
                 * session_id: UUID of the session to update
                 * draft_update: Fields to update (all optional)
                 * request: FastAPI request object (for audit logging)
                 * current_user: Authenticated user (from JWT token)
                 * db: Database session
                 * redis_client: Redis client for distributed rate limiting
                 *
                 * Returns:
                 * Updated session with decrypted PHI fields
                 *
                 * Raises:
                 * HTTPException: 401 if not authenticated, 404 if not found or wrong workspace,
                 * 429 if rate limit exceeded, 422 if validation fails
                 *
                 * Example:
                 * PATCH /api/v1/sessions/{uuid}/draft
                 * {
                     * "subjective": "Patient reports... (partial update)"
                     * }
                     * @param sessionId
                     * @param requestBody
                     * @param accessToken
                     * @returns SessionResponse Successful Response
                     * @throws ApiError
                     */
                    public static saveDraftApiV1SessionsSessionIdDraftPatch(
                        sessionId: string,
                        requestBody: SessionDraftUpdate,
                        accessToken?: (string | null),
                    ): CancelablePromise<SessionResponse> {
                        return __request(OpenAPI, {
                            method: 'PATCH',
                            url: '/api/v1/sessions/{session_id}/draft',
                            path: {
                                'session_id': sessionId,
                            },
                            cookies: {
                                'access_token': accessToken,
                            },
                            body: requestBody,
                            mediaType: 'application/json',
                            errors: {
                                422: `Validation Error`,
                            },
                        });
                    }
                    /**
                     * Finalize Session
                     * Finalize session and mark as complete.
                     *
                     * Marks a session as finalized, making it immutable and preventing deletion.
                     * At least one SOAP field must have content before finalizing.
                     *
                     * Validation:
                     * - At least one SOAP field (subjective, objective, assessment, plan)
                     * must have content
                     * - Session must exist and belong to the authenticated workspace
                     *
                     * Effect:
                     * - Sets finalized_at timestamp to current time
                     * - Sets is_draft to False
                     * - Increments version
                     * - Prevents deletion (enforced in DELETE endpoint)
                     *
                     * SECURITY: Verifies workspace ownership before allowing finalization.
                     * workspace_id is derived from JWT token (server-side).
                     *
                     * AUDIT: Update is automatically logged by AuditMiddleware with "finalized" action.
                     *
                     * Args:
                     * session_id: UUID of the session to finalize
                     * request: FastAPI request object (for audit logging)
                     * current_user: Authenticated user (from JWT token)
                     * db: Database session
                     *
                     * Returns:
                     * Finalized session with finalized_at timestamp set
                     *
                     * Raises:
                     * HTTPException: 401 if not authenticated, 404 if not found or wrong workspace,
                     * 422 if validation fails (no SOAP content)
                     *
                     * Example:
                     * POST /api/v1/sessions/{uuid}/finalize
                     * (no request body needed)
                     * @param sessionId
                     * @param accessToken
                     * @returns SessionResponse Successful Response
                     * @throws ApiError
                     */
                    public static finalizeSessionApiV1SessionsSessionIdFinalizePost(
                        sessionId: string,
                        accessToken?: (string | null),
                    ): CancelablePromise<SessionResponse> {
                        return __request(OpenAPI, {
                            method: 'POST',
                            url: '/api/v1/sessions/{session_id}/finalize',
                            path: {
                                'session_id': sessionId,
                            },
                            cookies: {
                                'access_token': accessToken,
                            },
                            errors: {
                                422: `Validation Error`,
                            },
                        });
                    }
                    /**
                     * Unfinalize Session
                     * Unfinalize session and revert to draft status.
                     *
                     * Reverts a finalized session back to draft status, allowing further editing.
                     * This endpoint is the inverse of POST /sessions/{session_id}/finalize.
                     *
                     * Effect:
                     * - Sets is_draft to True
                     * - Clears finalized_at timestamp (sets to NULL)
                     * - Increments version
                     * - Session becomes editable again
                     *
                     * SECURITY: Verifies workspace ownership before allowing unfinalizing.
                     * workspace_id is derived from JWT token (server-side).
                     *
                     * AUDIT: Update is automatically logged by AuditMiddleware with "unfinalized" action.
                     *
                     * Args:
                     * session_id: UUID of the session to unfinalize
                     * request: FastAPI request object (for audit logging)
                     * current_user: Authenticated user (from JWT token)
                     * db: Database session
                     *
                     * Returns:
                     * Unfinalied session with is_draft=True and finalized_at cleared
                     *
                     * Raises:
                     * HTTPException: 401 if not authenticated, 404 if not found or wrong workspace,
                     * 400 if session is already a draft
                     *
                     * Example:
                     * POST /api/v1/sessions/{uuid}/unfinalize
                     * (no request body needed)
                     * @param sessionId
                     * @param accessToken
                     * @returns SessionResponse Successful Response
                     * @throws ApiError
                     */
                    public static unfinalizeSessionApiV1SessionsSessionIdUnfinalizePost(
                        sessionId: string,
                        accessToken?: (string | null),
                    ): CancelablePromise<SessionResponse> {
                        return __request(OpenAPI, {
                            method: 'POST',
                            url: '/api/v1/sessions/{session_id}/unfinalize',
                            path: {
                                'session_id': sessionId,
                            },
                            cookies: {
                                'access_token': accessToken,
                            },
                            errors: {
                                422: `Validation Error`,
                            },
                        });
                    }
                    /**
                     * Get Session Versions
                     * Get version history for a session note.
                     *
                     * Returns all versions of a session note in reverse chronological order
                     * (most recent first). Only finalized sessions have versions.
                     *
                     * SECURITY: Verifies workspace ownership before allowing access.
                     * workspace_id is derived from JWT token (server-side).
                     *
                     * AUDIT: PHI access is automatically logged by AuditMiddleware.
                     *
                     * Args:
                     * session_id: UUID of the session
                     * request: FastAPI request object (for audit logging)
                     * current_user: Authenticated user (from JWT token)
                     * db: Database session
                     *
                     * Returns:
                     * List of session versions with decrypted PHI fields
                     *
                     * Raises:
                     * HTTPException: 401 if not authenticated,
                     * 404 if not found or wrong workspace
                     *
                     * Example:
                     * GET /api/v1/sessions/{uuid}/versions
                     * Response: [
                         * {
                             * "id": "version-uuid-2",
                             * "session_id": "session-uuid",
                             * "version_number": 2,
                             * "subjective": "Amended note...",
                             * "created_at": "2025-01-16T09:15:00Z"
                             * },
                             * {
                                 * "id": "version-uuid-1",
                                 * "session_id": "session-uuid",
                                 * "version_number": 1,
                                 * "subjective": "Original note...",
                                 * "created_at": "2025-01-15T15:05:00Z"
                                 * }
                                 * ]
                                 * @param sessionId
                                 * @param accessToken
                                 * @returns SessionVersionResponse Successful Response
                                 * @throws ApiError
                                 */
                                public static getSessionVersionsApiV1SessionsSessionIdVersionsGet(
                                    sessionId: string,
                                    accessToken?: (string | null),
                                ): CancelablePromise<Array<SessionVersionResponse>> {
                                    return __request(OpenAPI, {
                                        method: 'GET',
                                        url: '/api/v1/sessions/{session_id}/versions',
                                        path: {
                                            'session_id': sessionId,
                                        },
                                        cookies: {
                                            'access_token': accessToken,
                                        },
                                        errors: {
                                            422: `Validation Error`,
                                        },
                                    });
                                }
                                /**
                                 * Restore Session
                                 * Restore a soft-deleted session within 30-day grace period.
                                 *
                                 * Restores a soft-deleted session by clearing the deletion metadata.
                                 * Can only restore sessions that haven't exceeded the 30-day grace period.
                                 *
                                 * SECURITY: Verifies workspace ownership before allowing restoration.
                                 * workspace_id is derived from JWT token (server-side).
                                 *
                                 * AUDIT: Restoration is logged in audit trail.
                                 *
                                 * Args:
                                 * session_id: UUID of the session to restore
                                 * request: FastAPI request object (for audit logging)
                                 * current_user: Authenticated user (from JWT token)
                                 * db: Database session
                                 *
                                 * Returns:
                                 * Restored session with cleared deletion metadata
                                 *
                                 * Raises:
                                 * HTTPException: 401 if not authenticated,
                                 * 404 if not found or not deleted or wrong workspace,
                                 * 410 if 30-day grace period has expired
                                 *
                                 * Example:
                                 * POST /api/v1/sessions/{uuid}/restore
                                 * (no request body needed)
                                 * @param sessionId
                                 * @param accessToken
                                 * @returns SessionResponse Successful Response
                                 * @throws ApiError
                                 */
                                public static restoreSessionApiV1SessionsSessionIdRestorePost(
                                    sessionId: string,
                                    accessToken?: (string | null),
                                ): CancelablePromise<SessionResponse> {
                                    return __request(OpenAPI, {
                                        method: 'POST',
                                        url: '/api/v1/sessions/{session_id}/restore',
                                        path: {
                                            'session_id': sessionId,
                                        },
                                        cookies: {
                                            'access_token': accessToken,
                                        },
                                        errors: {
                                            422: `Validation Error`,
                                        },
                                    });
                                }
                                /**
                                 * Permanently Delete Session
                                 * Permanently delete a soft-deleted session (HARD DELETE).
                                 *
                                 * This endpoint performs a true database deletion, permanently removing the
                                 * session record and all associated data. This action is irreversible.
                                 *
                                 * SECURITY: Verifies workspace ownership before allowing deletion.
                                 * workspace_id is derived from JWT token (server-side).
                                 *
                                 * RESTRICTIONS:
                                 * - Can only permanently delete sessions that are already soft-deleted
                                 * - Cannot delete active (non-deleted) sessions - use DELETE /sessions/{id} first
                                 *
                                 * AUDIT: Permanent deletion is logged in audit trail before record removal.
                                 *
                                 * Args:
                                 * session_id: UUID of the session to permanently delete
                                 * request: FastAPI request object (for audit logging)
                                 * current_user: Authenticated user (from JWT token)
                                 * db: Database session
                                 *
                                 * Returns:
                                 * No content (204) on success
                                 *
                                 * Raises:
                                 * HTTPException: 401 if not authenticated,
                                 * 404 if not found or wrong workspace,
                                 * 422 if session is not soft-deleted (must soft-delete first)
                                 *
                                 * Example:
                                 * DELETE /api/v1/sessions/{uuid}/permanent
                                 * @param sessionId
                                 * @param accessToken
                                 * @returns void
                                 * @throws ApiError
                                 */
                                public static permanentlyDeleteSessionApiV1SessionsSessionIdPermanentDelete(
                                    sessionId: string,
                                    accessToken?: (string | null),
                                ): CancelablePromise<void> {
                                    return __request(OpenAPI, {
                                        method: 'DELETE',
                                        url: '/api/v1/sessions/{session_id}/permanent',
                                        path: {
                                            'session_id': sessionId,
                                        },
                                        cookies: {
                                            'access_token': accessToken,
                                        },
                                        errors: {
                                            422: `Validation Error`,
                                        },
                                    });
                                }
                                /**
                                 * Get Latest Finalized Session
                                 * Get the most recent finalized session for a client.
                                 *
                                 * Returns the latest finalized (non-draft) session note for the specified client,
                                 * ordered by session_date descending. Used by the Previous Session Context Panel
                                 * to provide treatment continuity when creating new session notes.
                                 *
                                 * SECURITY: Verifies client belongs to authenticated workspace before returning data.
                                 * workspace_id is derived from JWT token (server-side).
                                 *
                                 * PERFORMANCE: Uses ix_sessions_workspace_client_date index for optimal performance.
                                 * Query should execute in <50ms p95.
                                 *
                                 * PHI ACCESS: This endpoint returns decrypted SOAP fields (PHI).
                                 * All access is automatically logged by AuditMiddleware for HIPAA compliance.
                                 *
                                 * Args:
                                 * client_id: UUID of the client
                                 * request: FastAPI request object (for audit logging)
                                 * current_user: Authenticated user (from JWT token)
                                 * db: Database session
                                 *
                                 * Returns:
                                 * Most recent finalized session with decrypted SOAP fields
                                 *
                                 * Raises:
                                 * HTTPException: 401 if not authenticated,
                                 * 403 if client not in workspace,
                                 * 404 if client has no finalized sessions
                                 *
                                 * Example:
                                 * GET /api/v1/sessions/clients/{client_id}/latest-finalized
                                 * Response: {
                                     * "id": "uuid",
                                     * "session_date": "2025-10-06T14:00:00Z",
                                     * "duration_minutes": 60,
                                     * "is_draft": false,
                                     * "finalized_at": "2025-10-06T15:05:00Z",
                                     * "subjective": "Patient reports neck pain...",
                                     * "objective": "ROM 90° shoulder abduction...",
                                     * "assessment": "Muscle tension pattern...",
                                     * "plan": "Continue trapezius protocol...",
                                     * ...
                                     * }
                                     * @param clientId
                                     * @param accessToken
                                     * @returns SessionResponse Successful Response
                                     * @throws ApiError
                                     */
                                    public static getLatestFinalizedSessionApiV1SessionsClientsClientIdLatestFinalizedGet(
                                        clientId: string,
                                        accessToken?: (string | null),
                                    ): CancelablePromise<SessionResponse> {
                                        return __request(OpenAPI, {
                                            method: 'GET',
                                            url: '/api/v1/sessions/clients/{client_id}/latest-finalized',
                                            path: {
                                                'client_id': clientId,
                                            },
                                            cookies: {
                                                'access_token': accessToken,
                                            },
                                            errors: {
                                                422: `Validation Error`,
                                            },
                                        });
                                    }
                                }
