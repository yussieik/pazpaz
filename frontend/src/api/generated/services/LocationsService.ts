/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

import type { LocationCreate } from '../models/LocationCreate'
import type { LocationListResponse } from '../models/LocationListResponse'
import type { LocationResponse } from '../models/LocationResponse'
import type { LocationType } from '../models/LocationType'
import type { LocationUpdate } from '../models/LocationUpdate'
import type { CancelablePromise } from '../core/CancelablePromise'
import { OpenAPI } from '../core/OpenAPI'
import { request as __request } from '../core/request'
export class LocationsService {
  /**
   * Create Location
   * Create a new location.
   *
   * Creates a new location record in the authenticated workspace.
   * All location data is scoped to the workspace.
   *
   * SECURITY: workspace_id is derived from authenticated user's JWT token (server-side).
   *
   * Args:
   * location_data: Location creation data (without workspace_id)
   * current_user: Authenticated user (from JWT token)
   * db: Database session
   *
   * Returns:
   * Created location with all fields
   *
   * Raises:
   * HTTPException: 401 if not authenticated, 422 if validation fails,
   * 409 if location name already exists in workspace
   * @param requestBody
   * @param accessToken
   * @returns LocationResponse Successful Response
   * @throws ApiError
   */
  public static createLocationApiV1LocationsPost(
    requestBody: LocationCreate,
    accessToken?: string | null
  ): CancelablePromise<LocationResponse> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/locations',
      cookies: {
        access_token: accessToken,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    })
  }
  /**
   * List Locations
   * List all locations in the workspace.
   *
   * Returns a paginated list of locations, ordered by name.
   * All results are scoped to the authenticated workspace.
   *
   * SECURITY: Only returns locations belonging to the authenticated user's
   * workspace (from JWT).
   *
   * Args:
   * current_user: Authenticated user (from JWT token)
   * db: Database session
   * page: Page number (1-indexed)
   * page_size: Number of items per page (max 100)
   * is_active: Filter by active status (default: true, None = all)
   * location_type: Filter by location type (clinic, home, online)
   *
   * Returns:
   * Paginated list of locations with total count
   *
   * Raises:
   * HTTPException: 401 if not authenticated
   * @param page Page number (1-indexed)
   * @param pageSize Items per page
   * @param isActive Filter by active status (default: true)
   * @param locationType Filter by location type
   * @param accessToken
   * @returns LocationListResponse Successful Response
   * @throws ApiError
   */
  public static listLocationsApiV1LocationsGet(
    page: number = 1,
    pageSize: number = 50,
    isActive?: boolean | null,
    locationType?: LocationType | null,
    accessToken?: string | null
  ): CancelablePromise<LocationListResponse> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/locations',
      cookies: {
        access_token: accessToken,
      },
      query: {
        page: page,
        page_size: pageSize,
        is_active: isActive,
        location_type: locationType,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }
  /**
   * Get Location
   * Get a single location by ID.
   *
   * Retrieves a location by ID, ensuring it belongs to the authenticated workspace.
   *
   * SECURITY: Returns 404 for non-existent locations and locations in
   * other workspaces to prevent information leakage. workspace_id is derived
   * from JWT token.
   *
   * Args:
   * location_id: UUID of the location
   * current_user: Authenticated user (from JWT token)
   * db: Database session
   *
   * Returns:
   * Location details
   *
   * Raises:
   * HTTPException: 401 if not authenticated, 404 if not found or wrong workspace
   * @param locationId
   * @param accessToken
   * @returns LocationResponse Successful Response
   * @throws ApiError
   */
  public static getLocationApiV1LocationsLocationIdGet(
    locationId: string,
    accessToken?: string | null
  ): CancelablePromise<LocationResponse> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/locations/{location_id}',
      path: {
        location_id: locationId,
      },
      cookies: {
        access_token: accessToken,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }
  /**
   * Update Location
   * Update an existing location.
   *
   * Updates location fields. Only provided fields are updated.
   * Location must belong to the authenticated workspace.
   *
   * SECURITY: Verifies workspace ownership before allowing updates.
   * workspace_id is derived from JWT token (server-side).
   *
   * Args:
   * location_id: UUID of the location to update
   * location_data: Fields to update
   * current_user: Authenticated user (from JWT token)
   * db: Database session
   *
   * Returns:
   * Updated location
   *
   * Raises:
   * HTTPException: 401 if not authenticated, 404 if not found or wrong workspace,
   * 409 if name conflicts with existing location, 422 if validation fails
   * @param locationId
   * @param requestBody
   * @param accessToken
   * @returns LocationResponse Successful Response
   * @throws ApiError
   */
  public static updateLocationApiV1LocationsLocationIdPut(
    locationId: string,
    requestBody: LocationUpdate,
    accessToken?: string | null
  ): CancelablePromise<LocationResponse> {
    return __request(OpenAPI, {
      method: 'PUT',
      url: '/api/v1/locations/{location_id}',
      path: {
        location_id: locationId,
      },
      cookies: {
        access_token: accessToken,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    })
  }
  /**
   * Delete Location
   * Delete a location.
   *
   * Soft deletes a location by setting is_active=False if referenced by
   * appointments.
   * Hard deletes if no appointments reference it.
   * Location must belong to the authenticated workspace.
   *
   * SECURITY: Verifies workspace ownership before allowing deletion.
   * workspace_id is derived from JWT token (server-side).
   *
   * Args:
   * location_id: UUID of the location to delete
   * current_user: Authenticated user (from JWT token)
   * db: Database session
   *
   * Returns:
   * No content (204) on success
   *
   * Raises:
   * HTTPException: 401 if not authenticated, 404 if not found or wrong workspace
   * @param locationId
   * @param accessToken
   * @returns void
   * @throws ApiError
   */
  public static deleteLocationApiV1LocationsLocationIdDelete(
    locationId: string,
    accessToken?: string | null
  ): CancelablePromise<void> {
    return __request(OpenAPI, {
      method: 'DELETE',
      url: '/api/v1/locations/{location_id}',
      path: {
        location_id: locationId,
      },
      cookies: {
        access_token: accessToken,
      },
      errors: {
        422: `Validation Error`,
      },
    })
  }
}
