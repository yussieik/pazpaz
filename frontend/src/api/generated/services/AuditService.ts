/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
 
import type { AuditAction } from '../models/AuditAction';
import type { AuditEventListResponse } from '../models/AuditEventListResponse';
import type { AuditEventResponse } from '../models/AuditEventResponse';
import type { ResourceType } from '../models/ResourceType';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class AuditService {
    /**
     * List Audit Events
     * List audit events for the workspace with optional filters.
     *
     * Returns a paginated list of audit events, ordered by created_at descending.
     * All results are scoped to the authenticated workspace.
     *
     * SECURITY:
     * - Requires JWT authentication
     * - Only workspace OWNER can access audit logs (HIPAA compliance requirement)
     * - Returns audit events belonging only to authenticated workspace
     *
     * HIPAA Compliance:
     * - Audit events are immutable (enforced by database triggers)
     * - All PHI access is logged (Client, Session, PlanOfCare reads)
     * - Metadata is sanitized to prevent PII/PHI leakage
     * - Access to audit logs is restricted to workspace owners
     *
     * Args:
     * page: Page number (1-indexed)
     * page_size: Number of items per page (max 100)
     * user_id: Filter by user who performed action
     * resource_type: Filter by resource type (Client, Session, etc.)
     * resource_id: Filter by specific resource ID
     * action: Filter by action type (CREATE, READ, UPDATE, DELETE)
     * start_date: Filter events on or after this date
     * end_date: Filter events on or before this date
     * phi_only: If True, only show PHI access events (Client/Session/PlanOfCare reads)
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     *
     * Returns:
     * Paginated list of audit events with total count
     *
     * Raises:
     * HTTPException: 401 if not authenticated, 403 if not owner
     *
     * Examples:
     * - GET /api/v1/audit-events?page=1&page_size=50
     * - GET /api/v1/audit-events?user_id={uuid}&action=READ
     * - GET /api/v1/audit-events?resource_type=Client&phi_only=true
     * - GET /api/v1/audit-events?start_date=2025-01-01T00:00:00Z
     * &end_date=2025-12-31T23:59:59Z
     * @param page Page number (1-indexed)
     * @param pageSize Items per page
     * @param userId Filter by user
     * @param resourceType Filter by resource type
     * @param resourceId Filter by resource ID
     * @param action Filter by action type
     * @param startDate Filter events on or after this date
     * @param endDate Filter events on or before this date
     * @param phiOnly Filter to only PHI access events
     * @param accessToken
     * @returns AuditEventListResponse Successful Response
     * @throws ApiError
     */
    public static listAuditEventsApiV1AuditEventsGet(
        page: number = 1,
        pageSize: number = 50,
        userId?: (string | null),
        resourceType?: (ResourceType | null),
        resourceId?: (string | null),
        action?: (AuditAction | null),
        startDate?: (string | null),
        endDate?: (string | null),
        phiOnly: boolean = false,
        accessToken?: (string | null),
    ): CancelablePromise<AuditEventListResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/audit-events',
            cookies: {
                'access_token': accessToken,
            },
            query: {
                'page': page,
                'page_size': pageSize,
                'user_id': userId,
                'resource_type': resourceType,
                'resource_id': resourceId,
                'action': action,
                'start_date': startDate,
                'end_date': endDate,
                'phi_only': phiOnly,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Audit Event
     * Get a single audit event by ID.
     *
     * Retrieves an audit event by ID, ensuring it belongs to the authenticated workspace.
     *
     * SECURITY:
     * - Requires JWT authentication
     * - Only workspace OWNER can access audit logs (HIPAA compliance requirement)
     * - Returns 404 for both non-existent events and events in other workspaces
     * to prevent information leakage
     *
     * Args:
     * audit_event_id: UUID of the audit event
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     *
     * Returns:
     * Audit event details
     *
     * Raises:
     * HTTPException: 401 if not authenticated, 403 if not owner,
     * 404 if not found or wrong workspace
     * @param auditEventId
     * @param accessToken
     * @returns AuditEventResponse Successful Response
     * @throws ApiError
     */
    public static getAuditEventApiV1AuditEventsAuditEventIdGet(
        auditEventId: string,
        accessToken?: (string | null),
    ): CancelablePromise<AuditEventResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/audit-events/{audit_event_id}',
            path: {
                'audit_event_id': auditEventId,
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
