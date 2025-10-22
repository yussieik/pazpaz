/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

/**
 * Schema for session API responses.
 */
export type SessionResponse = {
  /**
   * Patient-reported symptoms (PHI - encrypted at rest)
   */
  subjective?: string | null
  /**
   * Therapist observations (PHI - encrypted at rest)
   */
  objective?: string | null
  /**
   * Clinical assessment (PHI - encrypted at rest)
   */
  assessment?: string | null
  /**
   * Treatment plan (PHI - encrypted at rest)
   */
  plan?: string | null
  /**
   * Date/time when session occurred (timezone-aware UTC)
   */
  session_date: string
  /**
   * Session duration in minutes (0-480 min, i.e., 0-8 hours)
   */
  duration_minutes?: number | null
  id: string
  workspace_id: string
  client_id: string
  appointment_id: string | null
  created_by_user_id: string
  is_draft: boolean
  draft_last_saved_at: string | null
  finalized_at: string | null
  /**
   * When session was last amended (NULL if never amended)
   */
  amended_at?: string | null
  /**
   * Number of times this finalized session has been amended
   */
  amendment_count?: number
  version: number
  created_at: string
  updated_at: string
  /**
   * When session was soft-deleted (NULL if active)
   */
  deleted_at?: string | null
  /**
   * Optional reason for soft deletion
   */
  deleted_reason?: string | null
  /**
   * User who soft-deleted this session
   */
  deleted_by_user_id?: string | null
  /**
   * Date when session will be permanently purged (deleted_at + 30 days)
   */
  permanent_delete_after?: string | null
  /**
   * Number of file attachments for this session (excludes deleted)
   */
  attachment_count?: number
}
