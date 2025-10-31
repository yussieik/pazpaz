/**
 * Drag and Drop Helper Utilities
 *
 * Provides utility functions for appointment drag-and-drop rescheduling:
 * - Time calculations and rounding
 * - Grid snapping
 * - Date/time formatting
 * - Conflict detection helpers
 */

/**
 * Round time to nearest 15-minute increment
 * @param date - Date to round
 * @returns Rounded date
 */
export function roundToNearest15Minutes(date: Date): Date {
  const ms = 1000 * 60 * 15 // 15 minutes in milliseconds
  return new Date(Math.round(date.getTime() / ms) * ms)
}

/**
 * Calculate appointment duration in milliseconds
 * @param start - Start time
 * @param end - End time
 * @returns Duration in milliseconds
 */
export function getAppointmentDuration(
  start: Date | string,
  end: Date | string
): number {
  const startDate = typeof start === 'string' ? new Date(start) : start
  const endDate = typeof end === 'string' ? new Date(end) : end
  return endDate.getTime() - startDate.getTime()
}

/**
 * Calculate new end time based on start time and duration
 * @param start - New start time
 * @param durationMs - Duration in milliseconds
 * @returns New end time
 */
export function calculateEndTime(start: Date, durationMs: number): Date {
  return new Date(start.getTime() + durationMs)
}

/**
 * Format time range for display (e.g., "2:00 PM → 3:30 PM")
 * @param start - Start time
 * @param end - End time
 * @returns Formatted time range string
 */
export function formatTimeRange(start: Date | string, end: Date | string): string {
  const startDate = typeof start === 'string' ? new Date(start) : start
  const endDate = typeof end === 'string' ? new Date(end) : end

  const formatTime = (date: Date) => {
    const hours = date.getHours()
    const minutes = date.getMinutes()
    const ampm = hours >= 12 ? 'PM' : 'AM'
    const displayHours = hours % 12 || 12
    const displayMinutes = minutes.toString().padStart(2, '0')
    return `${displayHours}:${displayMinutes} ${ampm}`
  }

  return `${formatTime(startDate)} → ${formatTime(endDate)}`
}

/**
 * Format date and time for display (e.g., "Mon, Jan 15 • 2:00 PM")
 * @param date - Date to format
 * @returns Formatted date and time string
 */
export function formatDateAndTime(date: Date | string): string {
  const dateObj = typeof date === 'string' ? new Date(date) : date

  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
  const monthNames = [
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ]

  const dayName = dayNames[dateObj.getDay()]
  const monthName = monthNames[dateObj.getMonth()]
  const day = dateObj.getDate()

  const hours = dateObj.getHours()
  const minutes = dateObj.getMinutes()
  const ampm = hours >= 12 ? 'PM' : 'AM'
  const displayHours = hours % 12 || 12
  const displayMinutes = minutes.toString().padStart(2, '0')
  const time = `${displayHours}:${displayMinutes} ${ampm}`

  return `${dayName}, ${monthName} ${day} • ${time}`
}

/**
 * Check if two appointments overlap
 * @param start1 - Start time of first appointment
 * @param end1 - End time of first appointment
 * @param start2 - Start time of second appointment
 * @param end2 - End time of second appointment
 * @returns True if appointments overlap
 */
export function checkTimeOverlap(
  start1: Date | string,
  end1: Date | string,
  start2: Date | string,
  end2: Date | string
): boolean {
  const s1 = typeof start1 === 'string' ? new Date(start1) : start1
  const e1 = typeof end1 === 'string' ? new Date(end1) : end1
  const s2 = typeof start2 === 'string' ? new Date(start2) : start2
  const e2 = typeof end2 === 'string' ? new Date(end2) : end2

  // Check for overlap
  const hasOverlap = s2 < e1 && e2 > s1

  // Exclude exact back-to-back (adjacency is OK)
  const isBackToBack = e2.getTime() === s1.getTime() || s2.getTime() === e1.getTime()

  return hasOverlap && !isBackToBack
}

/**
 * Convert ISO date string to Date object
 * @param isoString - ISO date string
 * @returns Date object
 */
export function parseISOString(isoString: string): Date {
  return new Date(isoString)
}

/**
 * Convert Date to ISO string for API
 * @param date - Date object
 * @returns ISO string
 */
export function toISOString(date: Date): string {
  return date.toISOString()
}

/**
 * Check if drag crosses day boundary
 * @param originalDate - Original appointment date
 * @param newDate - New appointment date
 * @returns True if crosses day boundary
 */
export function crossesDayBoundary(
  originalDate: Date | string,
  newDate: Date | string
): boolean {
  const orig = typeof originalDate === 'string' ? new Date(originalDate) : originalDate
  const updated = typeof newDate === 'string' ? new Date(newDate) : newDate

  return (
    orig.getDate() !== updated.getDate() ||
    orig.getMonth() !== updated.getMonth() ||
    orig.getFullYear() !== updated.getFullYear()
  )
}

/**
 * Add minutes to a date
 * @param date - Original date
 * @param minutes - Minutes to add (can be negative)
 * @returns New date with minutes added
 */
export function addMinutes(date: Date, minutes: number): Date {
  return new Date(date.getTime() + minutes * 60000)
}

/**
 * Add days to a date
 * @param date - Original date
 * @param days - Days to add (can be negative)
 * @returns New date with days added
 */
export function addDays(date: Date, days: number): Date {
  const result = new Date(date)
  result.setDate(result.getDate() + days)
  return result
}

/**
 * Check if time is within business hours (8 AM - 6 PM)
 * @param date - Date to check
 * @returns True if within business hours
 */
export function isWithinBusinessHours(date: Date): boolean {
  const hours = date.getHours()
  return hours >= 8 && hours < 18
}

/**
 * Debounce function for performance optimization
 * @param func - Function to debounce
 * @param wait - Wait time in milliseconds
 * @returns Debounced function
 */
export function debounce<T extends (...args: never[]) => unknown>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: ReturnType<typeof setTimeout> | null = null

  return function executedFunction(...args: Parameters<T>) {
    const later = () => {
      timeout = null
      func(...args)
    }

    if (timeout) {
      clearTimeout(timeout)
    }
    timeout = setTimeout(later, wait)
  }
}
