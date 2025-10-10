import { format } from 'date-fns'

export type ViewType = 'timeGridWeek' | 'timeGridDay' | 'dayGridMonth'

/**
 * Format date using date-fns
 */
export function formatDate(dateString: string, formatStr: string): string {
  return format(new Date(dateString), formatStr)
}

/**
 * Format date range for toolbar based on current view
 * Provides concise, view-appropriate formatting
 */
export function formatDateRange(
  start: Date,
  end: Date,
  view: ViewType,
  currentDate?: Date
): string {
  if (view === 'timeGridDay') {
    // For day view, always use currentDate to avoid flicker during view transitions
    // When switching views, currentDateRange updates before the view stabilizes,
    // but currentDate remains stable thanks to the isViewChanging flag
    const dateToFormat = currentDate || start
    return format(dateToFormat, 'MMMM d, yyyy')
  } else if (view === 'timeGridWeek') {
    const startMonth = format(start, 'MMM')
    const endMonth = format(end, 'MMM')
    const startDay = format(start, 'd')
    const endDay = format(end, 'd')
    const year = format(start, 'yyyy')

    if (startMonth === endMonth) {
      return `${startMonth} ${startDay} - ${endDay}, ${year}`
    }
    return `${startMonth} ${startDay} - ${endMonth} ${endDay}, ${year}`
  } else {
    // For month view, use currentDate to avoid showing previous month
    // when calendar includes padding days from previous/next months
    const dateToFormat = currentDate || start
    return format(dateToFormat, 'MMMM yyyy')
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
 * Example: "January 15, 2025"
 */
export function formatLongDate(dateString: string): string {
  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}
