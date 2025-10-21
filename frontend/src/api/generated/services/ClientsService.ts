/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ClientCreate } from '../models/ClientCreate';
import type { ClientListResponse } from '../models/ClientListResponse';
import type { ClientResponse } from '../models/ClientResponse';
import type { ClientUpdate } from '../models/ClientUpdate';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class ClientsService {
    /**
     * Create Client
     * Create a new client.
     *
     * Creates a new client record in the authenticated workspace.
     * All client data is scoped to the workspace.
     *
     * SECURITY: workspace_id is derived from authenticated user's JWT token (server-side).
     *
     * Args:
     * client_data: Client creation data (without workspace_id)
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     *
     * Returns:
     * Created client with all fields
     *
     * Raises:
     * HTTPException: 401 if not authenticated, 422 if validation fails
     * @param requestBody
     * @param accessToken
     * @returns ClientResponse Successful Response
     * @throws ApiError
     */
    public static createClientApiV1ClientsPost(
        requestBody: ClientCreate,
        accessToken?: (string | null),
    ): CancelablePromise<ClientResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/clients',
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
     * List Clients
     * List all clients in the workspace.
     *
     * Returns a paginated list of clients, ordered by last name, first name.
     * All results are scoped to the authenticated workspace.
     *
     * By default, only active clients are returned. Use include_inactive=true
     * to see archived clients as well.
     *
     * SECURITY: Only returns clients belonging to the authenticated user's
     * workspace (from JWT).
     *
     * Args:
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     * page: Page number (1-indexed)
     * page_size: Number of items per page (max 100)
     * include_inactive: If True, include archived/inactive clients
     * include_appointments: If True, include appointment stats
     * (adds 3 queries per client)
     *
     * Returns:
     * Paginated list of clients with total count
     *
     * Raises:
     * HTTPException: 401 if not authenticated
     * @param page Page number (1-indexed)
     * @param pageSize Items per page
     * @param includeInactive Include archived/inactive clients
     * @param includeAppointments Include appointment stats (slower)
     * @param accessToken
     * @returns ClientListResponse Successful Response
     * @throws ApiError
     */
    public static listClientsApiV1ClientsGet(
        page: number = 1,
        pageSize: number = 50,
        includeInactive: boolean = false,
        includeAppointments: boolean = false,
        accessToken?: (string | null),
    ): CancelablePromise<ClientListResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/clients',
            cookies: {
                'access_token': accessToken,
            },
            query: {
                'page': page,
                'page_size': pageSize,
                'include_inactive': includeInactive,
                'include_appointments': includeAppointments,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Client
     * Get a single client by ID with computed appointment fields.
     *
     * Retrieves a client by ID, ensuring it belongs to the authenticated workspace.
     * Includes computed fields: next_appointment, last_appointment, appointment_count.
     *
     * SECURITY: Returns 404 for both non-existent clients and clients in other
     * workspaces to prevent information leakage. workspace_id is derived from
     * JWT token (server-side).
     *
     * PHI ACCESS: This endpoint accesses Protected Health Information (PHI).
     * All access is automatically logged by AuditMiddleware for HIPAA compliance.
     *
     * Args:
     * client_id: UUID of the client
     * request: FastAPI request object
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     *
     * Returns:
     * Client details with computed appointment fields
     *
     * Raises:
     * HTTPException: 401 if not authenticated, 404 if not found or wrong workspace
     * @param clientId
     * @param accessToken
     * @returns ClientResponse Successful Response
     * @throws ApiError
     */
    public static getClientApiV1ClientsClientIdGet(
        clientId: string,
        accessToken?: (string | null),
    ): CancelablePromise<ClientResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/clients/{client_id}',
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
    /**
     * Update Client
     * Update an existing client.
     *
     * Updates client fields. Only provided fields are updated.
     * Client must belong to the authenticated workspace.
     *
     * SECURITY: Verifies workspace ownership before allowing updates.
     * workspace_id is derived from JWT token (server-side).
     *
     * Args:
     * client_id: UUID of the client to update
     * client_data: Fields to update
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     *
     * Returns:
     * Updated client with computed appointment fields
     *
     * Raises:
     * HTTPException: 401 if not authenticated, 404 if not found or wrong workspace,
     * 422 if validation fails
     * @param clientId
     * @param requestBody
     * @param accessToken
     * @returns ClientResponse Successful Response
     * @throws ApiError
     */
    public static updateClientApiV1ClientsClientIdPut(
        clientId: string,
        requestBody: ClientUpdate,
        accessToken?: (string | null),
    ): CancelablePromise<ClientResponse> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/v1/clients/{client_id}',
            path: {
                'client_id': clientId,
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
     * Delete Client
     * Soft delete a client by marking as inactive.
     *
     * CHANGED: This now performs a soft delete (is_active = false) instead of
     * hard delete to preserve audit trail and appointment history.
     *
     * Client must belong to the authenticated workspace. The client will no longer
     * appear in default list views but can be retrieved with include_inactive=true.
     *
     * SECURITY: Verifies workspace ownership before allowing deletion.
     * workspace_id is derived from JWT token (server-side).
     *
     * Args:
     * client_id: UUID of the client to delete
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     *
     * Returns:
     * No content (204) on success
     *
     * Raises:
     * HTTPException: 401 if not authenticated, 404 if not found or wrong workspace
     * @param clientId
     * @param accessToken
     * @returns void
     * @throws ApiError
     */
    public static deleteClientApiV1ClientsClientIdDelete(
        clientId: string,
        accessToken?: (string | null),
    ): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/clients/{client_id}',
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
