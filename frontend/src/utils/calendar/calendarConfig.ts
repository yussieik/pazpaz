import timeGridPlugin from '@fullcalendar/timegrid'
import dayGridPlugin from '@fullcalendar/daygrid'
import interactionPlugin from '@fullcalendar/interaction'

/**
 * FullCalendar plugins configuration
 * Centralized array of required plugins
 */
export const CALENDAR_PLUGINS = [timeGridPlugin, dayGridPlugin, interactionPlugin]

/**
 * Time slot configuration for calendar views
 */
export const TIME_SLOT_CONFIG = {
  slotMinTime: '08:00:00',
  slotMaxTime: '20:00:00',
  slotDuration: '00:30:00',
} as const

/**
 * Time format configuration for calendar
 */
export const TIME_FORMAT_CONFIG = {
  eventTimeFormat: {
    hour: '2-digit' as const,
    minute: '2-digit' as const,
    meridiem: 'short' as const,
  },
  slotLabelFormat: {
    hour: '2-digit' as const,
    minute: '2-digit' as const,
    meridiem: 'short' as const,
  },
}

/**
 * Base calendar options shared across all views
 */
export const BASE_CALENDAR_OPTIONS = {
  headerToolbar: false,
  height: 'auto',
  allDaySlot: false,
  nowIndicator: true,
  editable: false,
  selectable: false,
  selectMirror: true,
  dayMaxEvents: true,
  weekends: true,
  ...TIME_SLOT_CONFIG,
  ...TIME_FORMAT_CONFIG,
} as const
