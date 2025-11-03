import timeGridPlugin from '@fullcalendar/timegrid'
import dayGridPlugin from '@fullcalendar/daygrid'
import interactionPlugin from '@fullcalendar/interaction'
import heLocale from '@fullcalendar/core/locales/he'

/**
 * FullCalendar plugins configuration
 * Centralized array of required plugins
 */
export const CALENDAR_PLUGINS = [timeGridPlugin, dayGridPlugin, interactionPlugin]

/**
 * FullCalendar locales
 */
export const CALENDAR_LOCALES = [heLocale]

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
 * Returns locale-specific time format (12h for English, 24h for Hebrew)
 */
export function getTimeFormatConfig(locale: string) {
  const is24Hour = locale === 'he'

  return {
    eventTimeFormat: {
      hour: '2-digit' as const,
      minute: '2-digit' as const,
      hour12: !is24Hour,
      ...(is24Hour ? {} : { meridiem: 'short' as const }),
    },
    slotLabelFormat: {
      hour: '2-digit' as const,
      minute: '2-digit' as const,
      hour12: !is24Hour,
      ...(is24Hour ? {} : { meridiem: 'short' as const }),
    },
  }
}

/**
 * Default time format config (for backwards compatibility)
 */
export const TIME_FORMAT_CONFIG = getTimeFormatConfig('en')

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
 * Get locale-specific calendar options
 * Configures locale, first day of week, and time format based on current language
 */
export function getCalendarOptions(currentLocale: string) {
  const timeFormatConfig = getTimeFormatConfig(currentLocale)

  return {
    headerToolbar: false,
    allDaySlot: false,
    nowIndicator: true,
    editable: true,
    selectable: false,
    selectMirror: true,
    dayMaxEvents: true,
    weekends: true,
    eventDurationEditable: false,
    eventStartEditable: true,
    snapDuration: '00:15:00',
    displayEventEnd: true,
    forceEventDuration: true,
    defaultTimedEventDuration: '01:00:00',
    locale: currentLocale,
    locales: CALENDAR_LOCALES,
    firstDay: currentLocale === 'he' ? 0 : 1, // Sunday for Hebrew, Monday for English
    ...TIME_SLOT_CONFIG,
    ...timeFormatConfig,
    ...BUSINESS_HOURS_CONFIG,
  }
}

/**
 * Base calendar options shared across all views (default English)
 */
export const BASE_CALENDAR_OPTIONS = getCalendarOptions('en')

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
