/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

/**
 * Schema for draft autosave updates (relaxed validation).
 *
 * Used by PATCH /sessions/{id}/draft endpoint for frontend autosave.
 * All fields are optional to allow partial updates.
 * No validation on session_date (drafts can be incomplete).
 */
export type SessionDraftUpdate = {
  subjective?: string | null
  objective?: string | null
  assessment?: string | null
  plan?: string | null
  duration_minutes?: number | null
}
