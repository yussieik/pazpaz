import type { paths } from '@/api/schema'

export type ViewType = 'timeGridWeek' | 'timeGridDay' | 'dayGridMonth'

/**
 * Appointment response types from OpenAPI schema
 */
export type AppointmentResponse =
  paths['/api/v1/appointments']['get']['responses']['200']['content']['application/json']

export type AppointmentListItem = AppointmentResponse['items'][0]

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
