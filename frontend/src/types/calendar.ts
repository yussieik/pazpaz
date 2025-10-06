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
