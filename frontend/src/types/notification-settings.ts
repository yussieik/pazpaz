/**
 * Notification Settings Types
 *
 * Type definitions for user notification preferences.
 * Matches backend API schema for notification settings.
 */

/**
 * User notification settings
 * Controls email notifications, daily digests, reminders, etc.
 */
export interface NotificationSettings {
  /**
   * Unique identifier
   */
  id: string

  /**
   * User ID (owner of these settings)
   */
  user_id: string

  /**
   * Workspace ID (settings are workspace-scoped)
   */
  workspace_id: string

  /**
   * Master toggle: Enable all email notifications
   * When false, all other email notifications are disabled
   */
  email_enabled: boolean

  /**
   * Event Notifications
   */

  /**
   * Notify when a new appointment is booked
   */
  notify_appointment_booked: boolean

  /**
   * Notify when an appointment is cancelled
   */
  notify_appointment_cancelled: boolean

  /**
   * Notify when an appointment is rescheduled
   */
  notify_appointment_rescheduled: boolean

  /**
   * Notify when a client confirms their appointment
   */
  notify_appointment_confirmed: boolean

  /**
   * Daily Digest
   */

  /**
   * Enable daily digest email
   */
  digest_enabled: boolean

  /**
   * Time to send daily digest (HH:MM format, 24-hour)
   * Example: "08:00", "17:30"
   * Null if digest is disabled
   */
  digest_time: string | null

  /**
   * Skip digest on weekends (Saturday and Sunday)
   */
  digest_skip_weekends: boolean

  /**
   * Appointment Reminders
   */

  /**
   * Enable appointment reminder emails
   */
  reminder_enabled: boolean

  /**
   * Minutes before appointment to send reminder
   * Valid values: 15, 30, 60, 120, 1440 (1 day)
   * Null if reminders disabled
   */
  reminder_minutes: number | null

  /**
   * Session Notes Reminders
   */

  /**
   * Enable reminder to complete session notes
   */
  notes_reminder_enabled: boolean

  /**
   * Time to send session notes reminder (HH:MM format, 24-hour)
   * Null if notes reminders disabled
   */
  notes_reminder_time: string | null

  /**
   * Extended settings (for future features)
   * Stored as JSON, can contain any additional settings
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  extended_settings: Record<string, any>

  /**
   * Timestamps
   */
  created_at: string
  updated_at: string
}

/**
 * Notification settings update request
 * All fields are optional (partial updates supported)
 */
export interface NotificationSettingsUpdate {
  email_enabled?: boolean
  notify_appointment_booked?: boolean
  notify_appointment_cancelled?: boolean
  notify_appointment_rescheduled?: boolean
  notify_appointment_confirmed?: boolean
  digest_enabled?: boolean
  digest_time?: string | null
  digest_skip_weekends?: boolean
  reminder_enabled?: boolean
  reminder_minutes?: number | null
  notes_reminder_enabled?: boolean
  notes_reminder_time?: string | null
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  extended_settings?: Record<string, any>
}

/**
 * Valid reminder minute options
 */
export const REMINDER_MINUTE_OPTIONS = [
  { value: 15, label: '15 minutes before' },
  { value: 30, label: '30 minutes before' },
  { value: 60, label: '1 hour before' },
  { value: 120, label: '2 hours before' },
  { value: 1440, label: '1 day before' },
] as const

/**
 * Type for reminder minute values
 */
export type ReminderMinutes = (typeof REMINDER_MINUTE_OPTIONS)[number]['value']

/**
 * Validation helpers
 */
export const NotificationSettingsValidation = {
  /**
   * Validate time format (HH:MM)
   * @param time - Time string to validate
   * @returns true if valid, false otherwise
   */
  isValidTimeFormat(time: string | null): boolean {
    if (!time) return false
    const timeRegex = /^([01]\d|2[0-3]):([0-5]\d)$/
    return timeRegex.test(time)
  },

  /**
   * Validate reminder minutes value
   * @param minutes - Minutes value to validate
   * @returns true if valid, false otherwise
   */
  isValidReminderMinutes(minutes: number | null): boolean {
    if (minutes === null) return false
    return REMINDER_MINUTE_OPTIONS.some((opt) => opt.value === minutes)
  },

  /**
   * Validate time format and return error message
   * @param time - Time string to validate
   * @returns Error message if invalid, null if valid
   */
  validateTimeFormat(time: string | null): string | null {
    if (!time) return 'Time is required'
    if (!this.isValidTimeFormat(time)) {
      return 'Time must be in HH:MM format (00:00 to 23:59)'
    }
    return null
  },

  /**
   * Validate reminder minutes and return error message
   * @param minutes - Minutes value to validate
   * @returns Error message if invalid, null if valid
   */
  validateReminderMinutes(minutes: number | null): string | null {
    if (minutes === null) return 'Reminder time is required'
    if (!this.isValidReminderMinutes(minutes)) {
      return 'Invalid reminder time. Please select from the available options.'
    }
    return null
  },
}
