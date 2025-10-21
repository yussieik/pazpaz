/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AttachmentRenameRequest } from '../models/AttachmentRenameRequest';
import type { Body_upload_client_attachment_api_v1_clients__client_id__attachments_post } from '../models/Body_upload_client_attachment_api_v1_clients__client_id__attachments_post';
import type { BulkDownloadRequest } from '../models/BulkDownloadRequest';
import type { SessionAttachmentListResponse } from '../models/SessionAttachmentListResponse';
import type { SessionAttachmentResponse } from '../models/SessionAttachmentResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class ClientAttachmentsService {
    /**
     * Upload Client Attachment
     * Upload file attachment for a client (not tied to specific session).
     *
     * This endpoint is for client-level documents like intake forms, consent documents,
     * insurance cards, or baseline assessments that aren't specific to a session.
     *
     * Security features:
     * - Triple validation (MIME type, extension, content)
     * - EXIF metadata stripping (GPS, camera info)
     * - File size limits (10 MB per file, 100 MB total per client)
     * - Secure S3 key generation (UUID-based, no user-controlled names)
     * - Workspace isolation (verified before upload)
     * - Rate limiting (10 uploads per minute per user)
     * - Audit logging (automatic via middleware)
     *
     * Supported file types:
     * - Images: JPEG, PNG, WebP (for baseline photos, insurance cards)
     * - Documents: PDF (for intake forms, consent documents, referrals)
     *
     * Args:
     * client_id: UUID of the client
     * file: Uploaded file (multipart/form-data)
     * request: FastAPI request object (for audit logging)
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     * redis_client: Redis client (for rate limiting)
     *
     * Returns:
     * Created attachment metadata (id, filename, size, content_type, created_at)
     *
     * Raises:
     * HTTPException:
     * - 401 if not authenticated
     * - 404 if client not found or wrong workspace
     * - 413 if file too large or total attachments exceed limit
     * - 415 if unsupported file type or validation fails
     * - 422 if validation error (MIME mismatch, corrupted file)
     * - 429 if rate limit exceeded (10 uploads/minute)
     *
     * Example:
     * POST /api/v1/clients/{uuid}/attachments
     * Content-Type: multipart/form-data
     *
     * file: (binary data)
     * @param clientId
     * @param formData
     * @param accessToken
     * @returns SessionAttachmentResponse Successful Response
     * @throws ApiError
     */
    public static uploadClientAttachmentApiV1ClientsClientIdAttachmentsPost(
        clientId: string,
        formData: Body_upload_client_attachment_api_v1_clients__client_id__attachments_post,
        accessToken?: (string | null),
    ): CancelablePromise<SessionAttachmentResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/clients/{client_id}/attachments',
            path: {
                'client_id': clientId,
            },
            cookies: {
                'access_token': accessToken,
            },
            formData: formData,
            mediaType: 'multipart/form-data',
            errors: {
                422: `Validation Error`,
            },
        });
    }
    /**
     * List Client Attachments
     * List all attachments for a client across all sessions.
     *
     * Returns metadata for all attachments (filenames, sizes, types, session dates).
     * Includes both session-level and client-level attachments.
     * Does not include file content (use GET /attachments/{id}/download for content).
     *
     * Args:
     * client_id: UUID of the client
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     *
     * Returns:
     * List of attachment metadata with session context where applicable
     *
     * Raises:
     * HTTPException:
     * - 401 if not authenticated
     * - 404 if client not found or wrong workspace
     *
     * Example:
     * GET /api/v1/clients/{uuid}/attachments
     * Response: {
         * "items": [
             * {
                 * "id": "uuid",
                 * "session_id": "uuid",
                 * "client_id": "uuid",
                 * "file_name": "wound_photo.jpg",
                 * "file_type": "image/jpeg",
                 * "file_size_bytes": 123456,
                 * "created_at": "2025-10-15T14:30:00Z",
                 * "session_date": "2025-10-15T13:00:00Z",
                 * "is_session_file": true
                 * },
                 * {
                     * "id": "uuid",
                     * "session_id": null,
                     * "client_id": "uuid",
                     * "file_name": "intake_form.pdf",
                     * "file_type": "application/pdf",
                     * "file_size_bytes": 234567,
                     * "created_at": "2025-10-01T10:00:00Z",
                     * "session_date": null,
                     * "is_session_file": false
                     * }
                     * ],
                     * "total": 2
                     * }
                     * @param clientId
                     * @param accessToken
                     * @returns SessionAttachmentListResponse Successful Response
                     * @throws ApiError
                     */
                    public static listClientAttachmentsApiV1ClientsClientIdAttachmentsGet(
                        clientId: string,
                        accessToken?: (string | null),
                    ): CancelablePromise<SessionAttachmentListResponse> {
                        return __request(OpenAPI, {
                            method: 'GET',
                            url: '/api/v1/clients/{client_id}/attachments',
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
                     * Get Client Attachment Download Url
                     * Generate pre-signed download URL for client-level attachment.
                     *
                     * Returns a temporary pre-signed URL that allows downloading the file from S3.
                     * URL expires after specified time (default: 15 minutes, max: 60 minutes).
                     *
                     * Security:
                     * - URLs expire after 15 minutes by default (configurable, max 60 minutes)
                     * - Short expiration reduces risk of URL sharing or interception
                     * - Each download requires re-authentication and workspace verification
                     * - Workspace isolation enforced
                     *
                     * Args:
                     * client_id: UUID of the client
                     * attachment_id: UUID of the attachment
                     * current_user: Authenticated user (from JWT token)
                     * db: Database session
                     * expires_in_minutes: URL expiration time in minutes (default: 15, max: 60)
                     *
                     * Returns:
                     * Dict with download_url and expires_in_seconds
                     *
                     * Raises:
                     * HTTPException:
                     * - 401 if not authenticated
                     * - 404 if client/attachment not found or wrong workspace
                     * - 400 if expires_in_minutes exceeds maximum (60)
                     *
                     * Example:
                     * GET /api/v1/clients/{uuid}/attachments/{uuid}/download?expires_in_minutes=30
                     * Response: {
                         * "download_url": "https://s3.../file?X-Amz-...",
                         * "expires_in_seconds": 1800
                         * }
                         * @param clientId
                         * @param attachmentId
                         * @param expiresInMinutes
                         * @param accessToken
                         * @returns any Successful Response
                         * @throws ApiError
                         */
                        public static getClientAttachmentDownloadUrlApiV1ClientsClientIdAttachmentsAttachmentIdDownloadGet(
                            clientId: string,
                            attachmentId: string,
                            expiresInMinutes: number = 15,
                            accessToken?: (string | null),
                        ): CancelablePromise<Record<string, any>> {
                            return __request(OpenAPI, {
                                method: 'GET',
                                url: '/api/v1/clients/{client_id}/attachments/{attachment_id}/download',
                                path: {
                                    'client_id': clientId,
                                    'attachment_id': attachmentId,
                                },
                                cookies: {
                                    'access_token': accessToken,
                                },
                                query: {
                                    'expires_in_minutes': expiresInMinutes,
                                },
                                errors: {
                                    422: `Validation Error`,
                                },
                            });
                        }
                        /**
                         * Rename Client Attachment
                         * Rename a client-level attachment file.
                         *
                         * The file extension is automatically preserved. Invalid characters
                         * (/ \ : * ? " < > |) are rejected. Duplicate filenames return 409 Conflict.
                         *
                         * Validation:
                         * - Filename length: 1-255 characters (after trimming whitespace)
                         * - Prohibited characters: / \ : * ? " < > |
                         * - Extension preservation: Original extension automatically appended
                         * - Duplicate detection: Returns 409 if filename exists for same client
                         * - Whitespace trimming: Leading/trailing spaces removed
                         *
                         * Security:
                         * - Requires workspace access to the client
                         * - Validates attachment belongs to specified client
                         * - Validates attachment is client-level (session_id is NULL)
                         * - Audit logs all rename operations
                         *
                         * Args:
                         * client_id: UUID of the client
                         * attachment_id: UUID of the attachment to rename
                         * rename_data: New filename (extension will be preserved)
                         * current_user: Authenticated user (from JWT token)
                         * db: Database session
                         *
                         * Returns:
                         * Updated attachment metadata with new filename
                         *
                         * Raises:
                         * HTTPException:
                         * - 400 if filename is invalid (empty, too long, invalid chars)
                         * - 403 if workspace access denied
                         * - 404 if client or attachment not found
                         * - 409 if duplicate filename exists
                         *
                         * Example:
                         * PATCH /api/v1/clients/{uuid}/attachments/{uuid}
                         * {
                             * "file_name": "Intake form - signed"
                             * }
                             * @param clientId
                             * @param attachmentId
                             * @param requestBody
                             * @param accessToken
                             * @returns SessionAttachmentResponse Successful Response
                             * @throws ApiError
                             */
                            public static renameClientAttachmentApiV1ClientsClientIdAttachmentsAttachmentIdPatch(
                                clientId: string,
                                attachmentId: string,
                                requestBody: AttachmentRenameRequest,
                                accessToken?: (string | null),
                            ): CancelablePromise<SessionAttachmentResponse> {
                                return __request(OpenAPI, {
                                    method: 'PATCH',
                                    url: '/api/v1/clients/{client_id}/attachments/{attachment_id}',
                                    path: {
                                        'client_id': clientId,
                                        'attachment_id': attachmentId,
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
                             * Delete Client Attachment
                             * Soft delete a client-level attachment.
                             *
                             * Marks attachment as deleted (soft delete) without removing from S3.
                             * S3 cleanup happens via background job for deleted attachments.
                             *
                             * Args:
                             * client_id: UUID of the client
                             * attachment_id: UUID of the attachment
                             * current_user: Authenticated user (from JWT token)
                             * db: Database session
                             *
                             * Returns:
                             * No content (204) on success
                             *
                             * Raises:
                             * HTTPException:
                             * - 401 if not authenticated
                             * - 404 if client/attachment not found or wrong workspace
                             *
                             * Example:
                             * DELETE /api/v1/clients/{uuid}/attachments/{uuid}
                             * @param clientId
                             * @param attachmentId
                             * @param accessToken
                             * @returns void
                             * @throws ApiError
                             */
                            public static deleteClientAttachmentApiV1ClientsClientIdAttachmentsAttachmentIdDelete(
                                clientId: string,
                                attachmentId: string,
                                accessToken?: (string | null),
                            ): CancelablePromise<void> {
                                return __request(OpenAPI, {
                                    method: 'DELETE',
                                    url: '/api/v1/clients/{client_id}/attachments/{attachment_id}',
                                    path: {
                                        'client_id': clientId,
                                        'attachment_id': attachmentId,
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
                             * Download Multiple Attachments
                             * Download multiple attachments as a ZIP file.
                             *
                             * Creates a ZIP archive containing all requested attachments and returns it
                             * to the client. All attachments must belong to the specified client and
                             * the user's workspace.
                             *
                             * Security:
                             * - Workspace isolation enforced (all attachments must belong to user's workspace)
                             * - Client ownership verified (all attachments must belong to specified client)
                             * - Soft-deleted attachments excluded
                             * - File size limit: 100 MB total
                             * - File count limit: 50 files maximum (enforced by schema)
                             *
                             * Performance:
                             * - In-memory ZIP creation (suitable for 100 MB limit)
                             * - Single S3 request per file (no batching needed at this scale)
                             * - Content-Length header for proper download progress
                             *
                             * Args:
                             * client_id: UUID of the client
                             * request_body: List of attachment IDs to download
                             * current_user: Authenticated user
                             * db: Database session
                             *
                             * Returns:
                             * Response with ZIP file content
                             *
                             * Raises:
                             * HTTPException:
                             * - 400 if invalid request (empty list handled by schema)
                             * - 403 if workspace access denied
                             * - 404 if client or any attachment not found
                             * - 413 if total file size exceeds 100 MB
                             * - 500 if ZIP creation or S3 download fails
                             *
                             * Example:
                             * POST /api/v1/clients/{uuid}/attachments/download-multiple
                             * {
                                 * "attachment_ids": ["uuid1", "uuid2", "uuid3"]
                                 * }
                                 *
                                 * Response:
                                 * Content-Type: application/zip
                                 * Content-Disposition: attachment; filename="client-files-20251019_143022.zip"
                                 * (binary ZIP data)
                                 * @param clientId
                                 * @param requestBody
                                 * @param accessToken
                                 * @returns any Successful Response
                                 * @throws ApiError
                                 */
                                public static downloadMultipleAttachmentsApiV1ClientsClientIdAttachmentsDownloadMultiplePost(
                                    clientId: string,
                                    requestBody: BulkDownloadRequest,
                                    accessToken?: (string | null),
                                ): CancelablePromise<any> {
                                    return __request(OpenAPI, {
                                        method: 'POST',
                                        url: '/api/v1/clients/{client_id}/attachments/download-multiple',
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
                            }
