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
 *
 * Time Range: 6 AM - 10 PM (16 hours total)
 * - Covers early morning and evening appointments
 * - Business hours (8 AM - 6 PM) highlighted with white background
 * - Off-hours (6-8 AM, 6-10 PM) have light gray background
 */
export const TIME_SLOT_CONFIG = {
  slotMinTime: '06:00:00', // Start at 6 AM (changed from 8 AM)
  slotMaxTime: '22:00:00', // End at 10 PM (changed from 8 PM)
  slotDuration: '00:30:00',
  scrollTime: '08:00:00', // Auto-scroll to 8 AM on load
  scrollTimeReset: false, // Preserve scroll position on view change
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
 * Business hours configuration
 * Highlights 8 AM - 6 PM as primary working hours
 * Off-hours (6-8 AM, 6-10 PM) will have light gray background
 */
export const BUSINESS_HOURS_CONFIG = {
  businessHours: {
    daysOfWeek: [0, 1, 2, 3, 4, 5, 6], // All days (therapists work weekends)
    startTime: '08:00',
    endTime: '18:00',
  },
} as const

/**
 * Base calendar options shared across all views
 */
export const BASE_CALENDAR_OPTIONS = {
  headerToolbar: false,
  allDaySlot: false,
  nowIndicator: true,
  editable: true, // Enable drag-and-drop rescheduling
  selectable: false,
  selectMirror: true,
  dayMaxEvents: true,
  weekends: true,
  eventDurationEditable: false, // Duration is preserved when dragging
  eventStartEditable: true, // Allow changing start time
  snapDuration: '00:15:00', // Snap to 15-minute increments
  displayEventEnd: true, // CRITICAL: Show end times so FullCalendar uses actual duration for visual height
  forceEventDuration: true, // Force FullCalendar to use provided end time instead of defaultTimedEventDuration
  defaultTimedEventDuration: '01:00:00', // Set explicit default (shouldn't matter with forceEventDuration)
  ...TIME_SLOT_CONFIG,
  ...TIME_FORMAT_CONFIG,
  ...BUSINESS_HOURS_CONFIG,
} as const

/**
 * Per-view height strategies for visual consistency
 *
 * All views: Fill container height for consistent experience
 * Month view: fixedWeekCount: false shows only actual weeks (4-6 weeks)
 */
export const VIEW_SPECIFIC_OPTIONS = {
  timeGridWeek: {
    height: '100%',
  },
  timeGridDay: {
    height: '100%',
  },
  dayGridMonth: {
    height: '100%', // Fill container like other views
    fixedWeekCount: false, // Show only weeks that exist (4-6 weeks, not always 6)
  },
} as const
