/**
 * Session-related type definitions for PazPaz
 *
 * Includes types for:
 * - Session responses with soft delete support
 * - Appointment deletion with session note handling
 * - Session restoration and permanent deletion
 */

import { SUBSTANTIAL_CONTENT_THRESHOLD } from '@/constants/sessions'

/**
 * Session data interface (matches backend SessionResponse)
 */
export interface SessionResponse {
  id: string
  workspace_id: string
  client_id: string
  appointment_id: string | null
  subjective: string | null
  objective: string | null
  assessment: string | null
  plan: string | null
  session_date: string
  duration_minutes: number | null
  is_draft: boolean
  draft_last_saved_at: string | null
  finalized_at: string | null
  amended_at: string | null
  amendment_count: number

  // Soft delete fields
  deleted_at?: string | null
  deleted_reason?: string | null
  deleted_by_user_id?: string | null
  permanent_delete_after?: string | null

  created_at: string
  updated_at: string
}

/**
 * Appointment deletion request with session note handling
 */
export interface AppointmentDeleteRequest {
  reason?: string
  session_note_action?: 'delete' | 'keep'
  deletion_reason?: string
}

/**
 * Session note action options
 */
export type SessionNoteAction = 'delete' | 'keep'

/**
 * Check if a session note has substantial content
 * Uses SUBSTANTIAL_CONTENT_THRESHOLD constant (50 chars by default)
 */
export function hasSubstantialContent(session: {
  subjective?: string | null
  objective?: string | null
  assessment?: string | null
  plan?: string | null
}): boolean {
  const content = [session.subjective, session.objective, session.assessment, session.plan]
    .filter(Boolean)
    .join('')
  return content.trim().length > SUBSTANTIAL_CONTENT_THRESHOLD
}

/**
 * Check if grace period has expired
 * @param permanent_delete_after - ISO timestamp when permanent deletion occurs
 */
export function isGracePeriodExpired(permanent_delete_after: string): boolean {
  return new Date(permanent_delete_after) <= new Date()
}
