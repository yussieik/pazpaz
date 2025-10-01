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
