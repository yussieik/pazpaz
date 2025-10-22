/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
 
import type { WorkspaceStorageQuotaUpdateRequest } from '../models/WorkspaceStorageQuotaUpdateRequest';
import type { WorkspaceStorageUsageResponse } from '../models/WorkspaceStorageUsageResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class WorkspacesService {
    /**
     * Get Workspace Storage Usage
     * Get current workspace storage usage statistics.
     *
     * Returns detailed storage usage information including:
     * - Total bytes used by all files
     * - Storage quota (maximum allowed)
     * - Remaining storage (can be negative if over quota)
     * - Usage percentage
     * - Quota exceeded flag
     *
     * Args:
     * workspace_id: Workspace UUID
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     *
     * Returns:
     * Storage usage statistics
     *
     * Raises:
     * HTTPException:
     * - 401 if not authenticated
     * - 403 if workspace_id doesn't match user's workspace
     * - 404 if workspace not found
     *
     * Example:
     * GET /api/v1/workspaces/{uuid}/storage
     * Response: {
         * "used_bytes": 5368709120,
         * "quota_bytes": 10737418240,
         * "remaining_bytes": 5368709120,
         * "usage_percentage": 50.0,
         * "is_quota_exceeded": false,
         * "used_mb": 5120.0,
         * "quota_mb": 10240.0,
         * "remaining_mb": 5120.0
         * }
         * @param workspaceId
         * @param accessToken
         * @returns WorkspaceStorageUsageResponse Successful Response
         * @throws ApiError
         */
        public static getWorkspaceStorageUsageApiV1WorkspacesWorkspaceIdStorageGet(
            workspaceId: string,
            accessToken?: (string | null),
        ): CancelablePromise<WorkspaceStorageUsageResponse> {
            return __request(OpenAPI, {
                method: 'GET',
                url: '/api/v1/workspaces/{workspace_id}/storage',
                path: {
                    'workspace_id': workspaceId,
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
         * Update Workspace Storage Quota
         * Update workspace storage quota (admin only).
         *
         * This endpoint allows administrators to increase or decrease the storage quota
         * for a workspace. Useful for:
         * - Upgrading workspace to higher tier
         * - Temporarily increasing quota for busy practices
         * - Reducing quota for inactive workspaces
         *
         * IMPORTANT: This does NOT delete files if new quota is lower than current usage.
         * Workspace will be over quota until files are deleted.
         *
         * Args:
         * workspace_id: Workspace UUID
         * quota_update: New quota in bytes
         * current_user: Authenticated user (must be admin)
         * db: Database session
         *
         * Returns:
         * Updated storage usage statistics
         *
         * Raises:
         * HTTPException:
         * - 401 if not authenticated
         * - 403 if not admin or wrong workspace
         * - 404 if workspace not found
         * - 400 if quota_bytes is invalid (zero or negative)
         *
         * Example:
         * PATCH /api/v1/workspaces/{uuid}/storage/quota
         * {
             * "quota_bytes": 21474836480
             * }
             * Response: (same as GET /storage)
             * @param workspaceId
             * @param requestBody
             * @param accessToken
             * @returns WorkspaceStorageUsageResponse Successful Response
             * @throws ApiError
             */
            public static updateWorkspaceStorageQuotaApiV1WorkspacesWorkspaceIdStorageQuotaPatch(
                workspaceId: string,
                requestBody: WorkspaceStorageQuotaUpdateRequest,
                accessToken?: (string | null),
            ): CancelablePromise<WorkspaceStorageUsageResponse> {
                return __request(OpenAPI, {
                    method: 'PATCH',
                    url: '/api/v1/workspaces/{workspace_id}/storage/quota',
                    path: {
                        'workspace_id': workspaceId,
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
