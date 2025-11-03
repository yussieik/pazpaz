import { format } from 'date-fns'
import { he } from 'date-fns/locale'

export type ViewType = 'timeGridWeek' | 'timeGridDay' | 'dayGridMonth'

/**
 * Get date-fns locale based on current language
 * Used internally by formatting functions
 */
function getDateFnsLocale(locale?: string): Locale | undefined {
  return locale === 'he' ? he : undefined
}

/**
 * Format date using date-fns with locale support
 */
export function formatDate(
  dateString: string,
  formatStr: string,
  locale?: string
): string {
  return format(new Date(dateString), formatStr, {
    locale: getDateFnsLocale(locale),
  })
}

/**
 * Format date range for toolbar based on current view
 * Provides concise, view-appropriate formatting
 */
export function formatDateRange(
  start: Date,
  end: Date,
  view: ViewType,
  currentDate?: Date,
  locale?: string
): string {
  const localeObj = getDateFnsLocale(locale)

  if (view === 'timeGridDay') {
    // For day view, always use currentDate to avoid flicker during view transitions
    // When switching views, currentDateRange updates before the view stabilizes,
    // but currentDate remains stable thanks to the isViewChanging flag
    const dateToFormat = currentDate || start
    return format(dateToFormat, 'MMMM d, yyyy', { locale: localeObj })
  } else if (view === 'timeGridWeek') {
    const startMonth = format(start, 'MMM', { locale: localeObj })
    const endMonth = format(end, 'MMM', { locale: localeObj })
    const startDay = format(start, 'd', { locale: localeObj })
    const endDay = format(end, 'd', { locale: localeObj })
    const year = format(start, 'yyyy', { locale: localeObj })

    if (startMonth === endMonth) {
      return `${startMonth} ${startDay} - ${endDay}, ${year}`
    }
    return `${startMonth} ${startDay} - ${endMonth} ${endDay}, ${year}`
  } else {
    // For month view, use currentDate to avoid showing previous month
    // when calendar includes padding days from previous/next months
    const dateToFormat = currentDate || start
    return format(dateToFormat, 'MMMM yyyy', { locale: localeObj })
  }
}

/**
 * Calculate duration between two timestamps
 * Returns formatted string like "1h 30min", "45min", or "2h"
 */
export function calculateDuration(start: string, end: string): string {
  const startDate = new Date(start)
  const endDate = new Date(end)
  const durationMs = endDate.getTime() - startDate.getTime()
  const durationMinutes = Math.floor(durationMs / (1000 * 60))
  const hours = Math.floor(durationMinutes / 60)
  const minutes = durationMinutes % 60

  if (hours === 0) return `${minutes}min`
  if (minutes === 0) return `${hours}h`
  return `${hours}h ${minutes}min`
}

/**
 * Calculate days remaining between now and a future date
 * Returns positive number for future dates, negative for past dates
 * Rounds up to ensure we show at least 1 day if within 24 hours
 */
export function getDaysRemaining(futureDate: string): number {
  const targetDate = new Date(futureDate)
  const now = new Date()
  const diffMs = targetDate.getTime() - now.getTime()
  return Math.ceil(diffMs / (1000 * 60 * 60 * 24))
}

/**
 * Format relative time from a past date (e.g., "5 days ago", "Deleted today")
 * Used for displaying deletion timestamps and other historical events
 */
export function formatRelativeTime(pastDate: string): string {
  const past = new Date(pastDate)
  const now = new Date()
  const diffMs = now.getTime() - past.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  return `${diffDays} days ago`
}

/**
 * Format a date for display in long form
 * Example: "January 15, 2025" or "15 בינואר 2025"
 */
export function formatLongDate(dateString: string, locale?: string): string {
  const localeObj = getDateFnsLocale(locale)
  return format(new Date(dateString), 'PPP', { locale: localeObj })
}

/**
 * Format Date to datetime-local input format (YYYY-MM-DDTHH:mm)
 * Used for datetime-local input fields in forms
 */
export function formatDateTimeForInput(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hours = String(d.getHours()).padStart(2, '0')
  const minutes = String(d.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day}T${hours}:${minutes}`
}

/**
 * Add minutes to a datetime string
 * Returns formatted datetime-local string (YYYY-MM-DDTHH:mm)
 */
export function addMinutes(datetimeString: string, minutes: number): string {
  const date = new Date(datetimeString)
  date.setMinutes(date.getMinutes() + minutes)
  return formatDateTimeForInput(date)
}

/**
 * Calculate duration in minutes between two datetime strings
 */
export function getDurationMinutes(start: string, end: string): number {
  const startDate = new Date(start)
  const endDate = new Date(end)
  return Math.round((endDate.getTime() - startDate.getTime()) / (1000 * 60))
}

/**
 * Extract date in YYYY-MM-DD format from datetime string
 * Used for date input fields
 */
export function extractDate(datetimeString: string): string {
  if (!datetimeString) return ''
  const date = new Date(datetimeString)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/**
 * Parse datetime-local input value to ISO string
 * Converts YYYY-MM-DDTHH:mm to ISO 8601 format
 */
export function parseDateTimeLocal(dateTimeLocal: string): string {
  const date = new Date(dateTimeLocal)
  return date.toISOString()
}

/**
 * Format relative date with human-readable time units
 * Examples: "2 days ago", "1 week ago", "3 months ago", "Yesterday", "Today"
 * Used for displaying previous session timestamps
 */
export function formatRelativeDate(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  // Today
  if (diffDays === 0) return 'today'

  // Yesterday
  if (diffDays === 1) return 'yesterday'

  // Less than a week
  if (diffDays < 7) return `${diffDays} days ago`

  // Less than a month (30 days)
  if (diffDays < 30) {
    const weeks = Math.floor(diffDays / 7)
    return weeks === 1 ? '1 week ago' : `${weeks} weeks ago`
  }

  // Less than a year (365 days)
  if (diffDays < 365) {
    const months = Math.floor(diffDays / 30)
    return months === 1 ? '1 month ago' : `${months} months ago`
  }

  // Over a year
  const years = Math.floor(diffDays / 365)
  return years === 1 ? '1 year ago' : `${years} years ago`
}
