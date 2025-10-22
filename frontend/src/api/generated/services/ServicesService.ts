/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
 
import type { ServiceCreate } from '../models/ServiceCreate';
import type { ServiceListResponse } from '../models/ServiceListResponse';
import type { ServiceResponse } from '../models/ServiceResponse';
import type { ServiceUpdate } from '../models/ServiceUpdate';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class ServicesService {
    /**
     * Create Service
     * Create a new service.
     *
     * Creates a new service record in the authenticated workspace.
     * All service data is scoped to the workspace.
     *
     * SECURITY: workspace_id is derived from authenticated user's JWT token (server-side).
     *
     * Args:
     * service_data: Service creation data (without workspace_id)
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     *
     * Returns:
     * Created service with all fields
     *
     * Raises:
     * HTTPException: 401 if not authenticated, 422 if validation fails,
     * 409 if service name already exists in workspace
     * @param requestBody
     * @param accessToken
     * @returns ServiceResponse Successful Response
     * @throws ApiError
     */
    public static createServiceApiV1ServicesPost(
        requestBody: ServiceCreate,
        accessToken?: (string | null),
    ): CancelablePromise<ServiceResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/services',
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
     * List Services
     * List all services in the workspace.
     *
     * Returns a paginated list of services, ordered by name.
     * All results are scoped to the authenticated workspace.
     *
     * SECURITY: Only returns services belonging to the authenticated user's
     * workspace (from JWT).
     *
     * Args:
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     * page: Page number (1-indexed)
     * page_size: Number of items per page (max 100)
     * is_active: Filter by active status (default: true, None = all)
     *
     * Returns:
     * Paginated list of services with total count
     *
     * Raises:
     * HTTPException: 401 if not authenticated
     * @param page Page number (1-indexed)
     * @param pageSize Items per page
     * @param isActive Filter by active status (default: true)
     * @param accessToken
     * @returns ServiceListResponse Successful Response
     * @throws ApiError
     */
    public static listServicesApiV1ServicesGet(
        page: number = 1,
        pageSize: number = 50,
        isActive?: (boolean | null),
        accessToken?: (string | null),
    ): CancelablePromise<ServiceListResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/services',
            cookies: {
                'access_token': accessToken,
            },
            query: {
                'page': page,
                'page_size': pageSize,
                'is_active': isActive,
            },
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * Get Service
     * Get a single service by ID.
     *
     * Retrieves a service by ID, ensuring it belongs to the authenticated workspace.
     *
     * SECURITY: Returns 404 for non-existent services and services in
     * other workspaces to prevent information leakage. workspace_id is derived
     * from JWT token.
     *
     * Args:
     * service_id: UUID of the service
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     *
     * Returns:
     * Service details
     *
     * Raises:
     * HTTPException: 401 if not authenticated, 404 if not found or wrong workspace
     * @param serviceId
     * @param accessToken
     * @returns ServiceResponse Successful Response
     * @throws ApiError
     */
    public static getServiceApiV1ServicesServiceIdGet(
        serviceId: string,
        accessToken?: (string | null),
    ): CancelablePromise<ServiceResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/services/{service_id}',
            path: {
                'service_id': serviceId,
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
     * Update Service
     * Update an existing service.
     *
     * Updates service fields. Only provided fields are updated.
     * Service must belong to the authenticated workspace.
     *
     * SECURITY: Verifies workspace ownership before allowing updates.
     * workspace_id is derived from JWT token (server-side).
     *
     * Args:
     * service_id: UUID of the service to update
     * service_data: Fields to update
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     *
     * Returns:
     * Updated service
     *
     * Raises:
     * HTTPException: 401 if not authenticated, 404 if not found or wrong workspace,
     * 409 if name conflicts with existing service, 422 if validation fails
     * @param serviceId
     * @param requestBody
     * @param accessToken
     * @returns ServiceResponse Successful Response
     * @throws ApiError
     */
    public static updateServiceApiV1ServicesServiceIdPut(
        serviceId: string,
        requestBody: ServiceUpdate,
        accessToken?: (string | null),
    ): CancelablePromise<ServiceResponse> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/v1/services/{service_id}',
            path: {
                'service_id': serviceId,
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
     * Delete Service
     * Delete a service.
     *
     * Soft deletes a service by setting is_active=False if referenced by
     * appointments.
     * Hard deletes if no appointments reference it.
     * Service must belong to the authenticated workspace.
     *
     * SECURITY: Verifies workspace ownership before allowing deletion.
     * workspace_id is derived from JWT token (server-side).
     *
     * Args:
     * service_id: UUID of the service to delete
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     *
     * Returns:
     * No content (204) on success
     *
     * Raises:
     * HTTPException: 401 if not authenticated, 404 if not found or wrong workspace
     * @param serviceId
     * @param accessToken
     * @returns void
     * @throws ApiError
     */
    public static deleteServiceApiV1ServicesServiceIdDelete(
        serviceId: string,
        accessToken?: (string | null),
    ): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/api/v1/services/{service_id}',
            path: {
                'service_id': serviceId,
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
