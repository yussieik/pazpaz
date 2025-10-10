/**
 * Session and deletion-related constants for PazPaz
 *
 * Centralizes magic numbers and repeated values across the application
 */

/**
 * Grace period for soft-deleted session notes (in days)
 * After this period, notes are permanently deleted
 */
export const SESSION_DELETION_GRACE_PERIOD_DAYS = 30

/**
 * Minimum character count for session content to be considered "substantial"
 * Used to determine smart defaults when deleting appointments with session notes
 */
export const SUBSTANTIAL_CONTENT_THRESHOLD = 50

/**
 * Maximum length for deletion reason text
 */
export const MAX_DELETION_REASON_LENGTH = 500

/**
 * Quick-pick deletion reasons for appointments and session notes
 */
export const DELETION_REASONS = [
  'Duplicate entry',
  'Incorrect information',
  'Patient request',
  'Administrative correction',
] as const

export type DeletionReason = (typeof DELETION_REASONS)[number]
