/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AttachmentRenameRequest } from '../models/AttachmentRenameRequest';
import type { Body_upload_session_attachment_api_v1_sessions__session_id__attachments_post } from '../models/Body_upload_session_attachment_api_v1_sessions__session_id__attachments_post';
import type { SessionAttachmentListResponse } from '../models/SessionAttachmentListResponse';
import type { SessionAttachmentResponse } from '../models/SessionAttachmentResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class SessionAttachmentsService {
    /**
     * Upload Session Attachment
     * Upload file attachment for a session note.
     *
     * Security features:
     * - Triple validation (MIME type, extension, content)
     * - EXIF metadata stripping (GPS, camera info)
     * - File size limits (10 MB per file, 50 MB total per session)
     * - Secure S3 key generation (UUID-based, no user-controlled names)
     * - Workspace isolation (verified before upload)
     * - Rate limiting (10 uploads per minute per user)
     * - Audit logging (automatic via middleware)
     *
     * Supported file types:
     * - Images: JPEG, PNG, WebP (for wound photos, treatment documentation)
     * - Documents: PDF (for lab reports, referrals, consent forms)
     *
     * Args:
     * session_id: UUID of the session
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
     * - 404 if session not found or wrong workspace
     * - 413 if file too large or total attachments exceed limit
     * - 415 if unsupported file type or validation fails
     * - 422 if validation error (MIME mismatch, corrupted file)
     * - 429 if rate limit exceeded (10 uploads/minute)
     *
     * Example:
     * POST /api/v1/sessions/{uuid}/attachments
     * Content-Type: multipart/form-data
     *
     * file: (binary data)
     * @param sessionId
     * @param formData
     * @param accessToken
     * @returns SessionAttachmentResponse Successful Response
     * @throws ApiError
     */
    public static uploadSessionAttachmentApiV1SessionsSessionIdAttachmentsPost(
        sessionId: string,
        formData: Body_upload_session_attachment_api_v1_sessions__session_id__attachments_post,
        accessToken?: (string | null),
    ): CancelablePromise<SessionAttachmentResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/sessions/{session_id}/attachments',
            path: {
                'session_id': sessionId,
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
     * List Session Attachments
     * List all attachments for a session.
     *
     * Returns metadata for all attachments (filenames, sizes, types, session date).
     * Does not include file content (use GET /attachments/{id}/download for content).
     *
     * Args:
     * session_id: UUID of the session
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     *
     * Returns:
     * List of attachment metadata with session context
     *
     * Raises:
     * HTTPException:
     * - 401 if not authenticated
     * - 404 if session not found or wrong workspace
     *
     * Example:
     * GET /api/v1/sessions/{uuid}/attachments
     * @param sessionId
     * @param accessToken
     * @returns SessionAttachmentListResponse Successful Response
     * @throws ApiError
     */
    public static listSessionAttachmentsApiV1SessionsSessionIdAttachmentsGet(
        sessionId: string,
        accessToken?: (string | null),
    ): CancelablePromise<SessionAttachmentListResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/sessions/{session_id}/attachments',
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
     * Get Attachment Download Url
     * Generate pre-signed download URL for attachment.
     *
     * Returns a temporary pre-signed URL that allows downloading the file from S3.
     * URL expires after specified time (default: 15 minutes, max: 60 minutes).
     *
     * Security:
     * - URLs expire after 15 minutes by default (configurable, max 60 minutes)
     * - Short expiration reduces risk of URL sharing or interception
     * - Each download requires re-authentication and workspace verification
     *
     * Args:
     * session_id: UUID of the session
     * attachment_id: UUID of the attachment
     * current_user: Authenticated user (from JWT token)
     * db: Database session
     * expires_in_minutes: URL expiration time in minutes (default: 15, max: 60)
     *
     * Returns:
     * Dict with download_url and expires_at timestamp
     *
     * Raises:
     * HTTPException:
     * - 401 if not authenticated
     * - 404 if session/attachment not found or wrong workspace
     * - 400 if expires_in_minutes exceeds maximum (60)
     *
     * Example:
     * GET /api/v1/sessions/{uuid}/attachments/{uuid}/download?expires_in_minutes=30
     * Response: {
         * "download_url": "https://s3.../file?X-Amz-...",
         * "expires_in_seconds": 1800
         * }
         * @param sessionId
         * @param attachmentId
         * @param expiresInMinutes
         * @param accessToken
         * @returns any Successful Response
         * @throws ApiError
         */
        public static getAttachmentDownloadUrlApiV1SessionsSessionIdAttachmentsAttachmentIdDownloadGet(
            sessionId: string,
            attachmentId: string,
            expiresInMinutes: number = 15,
            accessToken?: (string | null),
        ): CancelablePromise<Record<string, any>> {
            return __request(OpenAPI, {
                method: 'GET',
                url: '/api/v1/sessions/{session_id}/attachments/{attachment_id}/download',
                path: {
                    'session_id': sessionId,
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
         * Rename Session Attachment
         * Rename a session-level attachment file.
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
         * - Requires workspace access to the session's client
         * - Validates attachment belongs to specified session
         * - Audit logs all rename operations
         *
         * Args:
         * session_id: UUID of the session
         * attachment_id: UUID of the attachment to rename
         * rename_data: New filename (extension will be preserved)
         * current_user: Authenticated user (from JWT token)
         * db: Database session
         *
         * Returns:
         * Updated attachment metadata with new filename and updated timestamp
         *
         * Raises:
         * HTTPException:
         * - 400 if filename is invalid (empty, too long, invalid chars)
         * - 403 if workspace access denied
         * - 404 if session or attachment not found
         * - 409 if duplicate filename exists
         *
         * Example:
         * PATCH /api/v1/sessions/{uuid}/attachments/{uuid}
         * {
             * "file_name": "Left shoulder pain - Oct 2025"
             * }
             * @param sessionId
             * @param attachmentId
             * @param requestBody
             * @param accessToken
             * @returns SessionAttachmentResponse Successful Response
             * @throws ApiError
             */
            public static renameSessionAttachmentApiV1SessionsSessionIdAttachmentsAttachmentIdPatch(
                sessionId: string,
                attachmentId: string,
                requestBody: AttachmentRenameRequest,
                accessToken?: (string | null),
            ): CancelablePromise<SessionAttachmentResponse> {
                return __request(OpenAPI, {
                    method: 'PATCH',
                    url: '/api/v1/sessions/{session_id}/attachments/{attachment_id}',
                    path: {
                        'session_id': sessionId,
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
             * Delete Session Attachment
             * Soft delete a session attachment.
             *
             * Marks attachment as deleted (soft delete) without removing from S3.
             * S3 cleanup happens via background job for deleted attachments.
             *
             * Args:
             * session_id: UUID of the session
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
             * - 404 if session/attachment not found or wrong workspace
             *
             * Example:
             * DELETE /api/v1/sessions/{uuid}/attachments/{uuid}
             * @param sessionId
             * @param attachmentId
             * @param accessToken
             * @returns void
             * @throws ApiError
             */
            public static deleteSessionAttachmentApiV1SessionsSessionIdAttachmentsAttachmentIdDelete(
                sessionId: string,
                attachmentId: string,
                accessToken?: (string | null),
            ): CancelablePromise<void> {
                return __request(OpenAPI, {
                    method: 'DELETE',
                    url: '/api/v1/sessions/{session_id}/attachments/{attachment_id}',
                    path: {
                        'session_id': sessionId,
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
        }
