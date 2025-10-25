import type { paths } from '@/api/schema'

export type ViewType = 'timeGridWeek' | 'timeGridDay' | 'dayGridMonth'

/**
 * Appointment response types from OpenAPI schema
 */
export type AppointmentResponse =
  paths['/api/v1/appointments']['get']['responses']['200']['content']['application/json']

export type AppointmentListItem = AppointmentResponse['items'][0]

/**
 * Appointment status type
 */
export type AppointmentStatus =
  | 'scheduled'
  | 'confirmed'
  | 'completed'
  | 'cancelled'
  | 'no_show'

/**
 * Calendar state interface
 */
export interface CalendarState {
  currentView: ViewType
  currentDate: Date
  currentDateRange: { start: Date; end: Date }
}

/**
 * Date range for API requests
 */
export interface DateRange {
  start: string
  end: string
}

/**
 * Appointment form data for create/edit operations
 * Note: This matches the backend schema (AppointmentCreate/AppointmentUpdate)
 */
export interface AppointmentFormData {
  client_id: string
  scheduled_start: string
  scheduled_end: string
  location_type: 'clinic' | 'home' | 'online'
  location_details?: string
  notes?: string
}

/**
 * Conflict detection types
 */
export interface ConflictingAppointment {
  id: string
  scheduled_start: string
  scheduled_end: string
  client_initials: string
  location_type: 'clinic' | 'home' | 'online'
  status: 'scheduled' | 'confirmed' | 'completed' | 'cancelled' | 'no_show'
}

export interface ConflictCheckResponse {
  has_conflict: boolean
  conflicting_appointments: ConflictingAppointment[]
}

/**
 * Extended appointment type with edit tracking
 * Note: The base AppointmentListItem comes from OpenAPI schema
 * These fields will be added by the backend specialist
 */
export interface AppointmentWithEditTracking extends AppointmentListItem {
  edited_at: string | null
  edit_count: number
}

/**
 * Session status for appointment details
 */
export interface SessionStatus {
  hasSession: boolean
  sessionId: string | null
  isDraft: boolean
}

/**
 * Extended session interface with amendment tracking
 * These fields will be added by the backend specialist
 */
export interface SessionWithAmendments {
  id: string
  workspace_id: string
  client_id: string
  appointment_id: string | null
  subjective?: string | null
  objective?: string | null
  assessment?: string | null
  plan?: string | null
  session_date: string
  duration_minutes?: number | null
  created_by_user_id: string
  is_draft: boolean
  draft_last_saved_at: string | null
  finalized_at: string | null
  amended_at: string | null
  amendment_count: number
  version: number
  created_at: string
  updated_at: string
  deleted_at?: string | null
  deleted_reason?: string | null
  deleted_by_user_id?: string | null
  permanent_delete_after?: string | null
  attachment_count?: number
  has_versions: boolean
}

/**
 * Session version for version history
 */
export interface SessionVersion {
  id: string
  version_number: number
  subjective: string | null
  objective: string | null
  assessment: string | null
  plan: string | null
  created_at: string
}
