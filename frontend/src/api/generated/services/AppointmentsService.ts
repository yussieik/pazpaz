/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
 
import type { AppointmentCreate } from '../models/AppointmentCreate';
import type { AppointmentDeleteRequest } from '../models/AppointmentDeleteRequest';
import type { AppointmentListResponse } from '../models/AppointmentListResponse';
import type { AppointmentResponse } from '../models/AppointmentResponse';
import type { AppointmentStatus } from '../models/AppointmentStatus';
import type { AppointmentUpdate } from '../models/AppointmentUpdate';
import type { ConflictCheckResponse } from '../models/ConflictCheckResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class AppointmentsService {
    /**
     * Create Appointment
     * Create a new appointment with conflict detection.
     *
     * Creates a new appointment after verifying:
     * 1. Client belongs to the workspace
     * 2. No conflicting appointments exist in the time slot
     *
     * SECURITY: workspace_id is derived from authenticated user's JWT token (server-side).
     *
     * Args:
     * appointment_data: Appointment creation data (without workspace_id)
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     *
     * Returns:
     * Created appointment with client information
     *
     * Raises:
     * HTTPException: 401 if not authenticated, 404 if client not found,
     * 409 if conflict exists, 422 if validation fails
     * @param requestBody
     * @param accessToken
     * @returns AppointmentResponse Successful Response
     * @throws ApiError
     */
    public static createAppointmentApiV1AppointmentsPost(
        requestBody: AppointmentCreate,
        accessToken?: (string | null),
    ): CancelablePromise<AppointmentResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/appointments',
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
     * List Appointments
     * List appointments in the workspace with optional filters.
     *
     * Returns a paginated list of appointments, ordered by scheduled_start descending.
     * All results are scoped to the authenticated workspace.
     *
     * SECURITY: Only returns appointments belonging to the authenticated user's
     * workspace (from JWT).
     *
     * Args:
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     * page: Page number (1-indexed)
     * page_size: Number of items per page (max 100)
     * start_date: Filter appointments starting on or after this date
     * end_date: Filter appointments starting on or before this date
     * client_id: Filter by specific client
     * status: Filter by appointment status
     *
     * Returns:
     * Paginated list of appointments with client information
     *
     * Raises:
     * HTTPException: 401 if not authenticated
     * @param page Page number (1-indexed)
     * @param pageSize Items per page
     * @param startDate Filter by start date (inclusive)
     * @param endDate Filter by end date (inclusive)
     * @param clientId Filter by client ID
     * @param status Filter by status
     * @param accessToken
     * @returns AppointmentListResponse Successful Response
     * @throws ApiError
     */
    public static listAppointmentsApiV1AppointmentsGet(
        page: number = 1,
        pageSize: number = 50,
        startDate?: (string | null),
        endDate?: (string | null),
        clientId?: (string | null),
        status?: (AppointmentStatus | null),
        accessToken?: (string | null),
    ): CancelablePromise<AppointmentListResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/appointments',
            cookies: {
                'access_token': accessToken,
            },
            query: {
                'page': page,
                'page_size': pageSize,
                'start_date': startDate,
                'end_date': endDate,
                'client_id': clientId,
                'status': status,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Check Appointment Conflicts
     * Check for appointment conflicts in a time range.
     *
     * Used by frontend to validate appointment times before submission.
     *
     * SECURITY: Only checks conflicts within the authenticated user's workspace
     * (from JWT).
     *
     * Args:
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     * scheduled_start: Start time to check
     * scheduled_end: End time to check
     * exclude_appointment_id: Appointment to exclude (when updating)
     *
     * Returns:
     * Conflict check result with list of conflicting appointments
     *
     * Raises:
     * HTTPException: 401 if not authenticated,
     * 422 if scheduled_end is not after scheduled_start
     * @param scheduledStart Start time to check
     * @param scheduledEnd End time to check
     * @param excludeAppointmentId Appointment ID to exclude (for updates)
     * @param accessToken
     * @returns ConflictCheckResponse Successful Response
     * @throws ApiError
     */
    public static checkAppointmentConflictsApiV1AppointmentsConflictsGet(
        scheduledStart: string,
        scheduledEnd: string,
        excludeAppointmentId?: (string | null),
        accessToken?: (string | null),
    ): CancelablePromise<ConflictCheckResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/appointments/conflicts',
            cookies: {
                'access_token': accessToken,
            },
            query: {
                'scheduled_start': scheduledStart,
                'scheduled_end': scheduledEnd,
                'exclude_appointment_id': excludeAppointmentId,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Appointment
     * Get a single appointment by ID.
     *
     * Retrieves an appointment by ID, ensuring it belongs to the authenticated workspace.
     *
     * SECURITY: Returns 404 for both non-existent appointments and appointments
     * in other workspaces to prevent information leakage. workspace_id is derived
     * from JWT token.
     *
     * Args:
     * appointment_id: UUID of the appointment
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     *
     * Returns:
     * Appointment details with client information
     *
     * Raises:
     * HTTPException: 401 if not authenticated,
     * 404 if not found or wrong workspace
     * @param appointmentId
     * @param accessToken
     * @returns AppointmentResponse Successful Response
     * @throws ApiError
     */
    public static getAppointmentApiV1AppointmentsAppointmentIdGet(
        appointmentId: string,
        accessToken?: (string | null),
    ): CancelablePromise<AppointmentResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/appointments/{appointment_id}',
            path: {
                'appointment_id': appointmentId,
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
     * Update Appointment
     * Update an existing appointment with conflict detection.
     *
     * Updates appointment fields. Only provided fields are updated.
     * If time is changed, conflict detection is performed unless allow_conflict=True.
     * Appointment must belong to the authenticated workspace.
     *
     * SECURITY: Verifies workspace ownership before allowing updates.
     * workspace_id is derived from JWT token (server-side).
     *
     * Args:
     * appointment_id: UUID of the appointment to update
     * appointment_data: Fields to update
     * allow_conflict: Allow update even if conflicts exist (default: False)
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     *
     * Returns:
     * Updated appointment with client information
     *
     * Raises:
     * HTTPException: 401 if not authenticated, 404 if not found or wrong workspace,
     * 409 if conflict (and allow_conflict=False), 422 if validation fails
     * @param appointmentId
     * @param requestBody
     * @param allowConflict Allow update even if conflicts exist (for 'Keep Both' scenario)
     * @param accessToken
     * @returns AppointmentResponse Successful Response
     * @throws ApiError
     */
    public static updateAppointmentApiV1AppointmentsAppointmentIdPut(
        appointmentId: string,
        requestBody: AppointmentUpdate,
        allowConflict: boolean = false,
        accessToken?: (string | null),
    ): CancelablePromise<AppointmentResponse> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/v1/appointments/{appointment_id}',
            path: {
                'appointment_id': appointmentId,
            },
            cookies: {
                'access_token': accessToken,
            },
            query: {
                'allow_conflict': allowConflict,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Delete Appointment
     * Delete an appointment with optional session note handling.
     *
     * Permanently deletes an appointment. If appointment has attached session notes,
     * you can choose to:
     * - soft delete them (30-day grace period for restoration)
     * - keep them unchanged (default)
     *
     * SOFT DELETE: Session notes are soft-deleted with 30-day grace period.
     * After 30 days, they will be permanently purged by a background job.
     *
     * VALIDATION: Cannot delete session notes that have been amended (amendment_count > 0)
     * due to medical-legal significance.
     *
     * SECURITY: Verifies workspace ownership before allowing deletion.
     * workspace_id is derived from JWT token (server-side).
     *
     * AUDIT: Comprehensive audit logging includes:
     * - Appointment status at deletion
     * - Whether session note existed and action taken
     * - Optional deletion reasons (appointment and session)
     * - Client/service context for forensic review
     *
     * Args:
     * appointment_id: UUID of the appointment to delete
     * deletion_request: Optional deletion reason and session note action
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     *
     * Returns:
     * No content (204) on success
     *
     * Raises:
     * HTTPException: 401 if not authenticated,
     * 404 if not found or wrong workspace,
     * 422 if trying to delete amended session notes
     *
     * Example:
     * DELETE /api/v1/appointments/{uuid}
     * {
         * "reason": "Duplicate entry - scheduled twice by mistake",
         * "session_note_action": "delete",
         * "deletion_reason": "Incorrect session data, will recreate"
         * }
         * @param appointmentId
         * @param accessToken
         * @param requestBody
         * @returns void
         * @throws ApiError
         */
        public static deleteAppointmentApiV1AppointmentsAppointmentIdDelete(
            appointmentId: string,
            accessToken?: (string | null),
            requestBody?: (AppointmentDeleteRequest | null),
        ): CancelablePromise<void> {
            return __request(OpenAPI, {
                method: 'DELETE',
                url: '/api/v1/appointments/{appointment_id}',
                path: {
                    'appointment_id': appointmentId,
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
    }
