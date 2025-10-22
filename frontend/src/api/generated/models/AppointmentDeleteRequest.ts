/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */

/**
 * Schema for deleting an appointment with optional reason and session note action.
 */
export type AppointmentDeleteRequest = {
  /**
   * Optional reason for deletion (logged in audit trail)
   */
  reason?: string | null
  /**
   * Action to take with session notes attached to this appointment. 'delete' = soft delete the session note with 30-day grace period, 'keep' = leave the session note unchanged (default if not specified). Required if appointment has session notes and you want to delete them.
   */
  session_note_action?: 'delete' | 'keep' | null
  /**
   * Optional reason for deleting the session note (only used if session_note_action='delete'). This is separate from the appointment deletion reason and is stored with the soft-deleted session note.
   */
  deletion_reason?: string | null
}
