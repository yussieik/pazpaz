/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

/**
 * Response schema for session attachment.
 *
 * Returns metadata about uploaded file (not the file content itself).
 * Use GET /attachments/{id}/download to get pre-signed download URL.
 *
 * Supports both session-level and client-level attachments:
 * - Session-level: session_id is set, is_session_file=True
 * - Client-level: session_id is None, is_session_file=False
 */
export type SessionAttachmentResponse = {
  /**
   * Attachment UUID
   */
  id: string
  /**
   * Session UUID (None for client-level attachments)
   */
  session_id: string | null
  /**
   * Client UUID (always present)
   */
  client_id: string
  /**
   * Workspace UUID
   */
  workspace_id: string
  /**
   * Sanitized filename
   */
  file_name: string
  /**
   * MIME type (e.g., image/jpeg)
   */
  file_type: string
  /**
   * File size in bytes
   */
  file_size_bytes: number
  /**
   * Upload timestamp
   */
  created_at: string
  /**
   * Date of session (None for client-level attachments)
   */
  session_date?: string | null
  /**
   * True if attached to specific session, False if client-level
   */
  is_session_file: boolean
}
