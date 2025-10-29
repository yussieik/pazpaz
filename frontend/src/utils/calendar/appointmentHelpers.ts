/**
 * Status color mappings for FullCalendar events
 */
const STATUS_COLORS: Record<string, string> = {
  scheduled: '#10b981', // emerald-500
  attended: '#10b981', // emerald-500 (positive completion)
  cancelled: '#ef4444', // red-500
  no_show: '#f59e0b', // amber-500
}

/**
 * Status badge class mappings for UI
 */
const STATUS_BADGE_CLASSES: Record<string, string> = {
  scheduled: 'bg-emerald-50 text-emerald-700 ring-emerald-600/20',
  attended: 'bg-green-50 text-green-700 ring-green-600/20',
  cancelled: 'bg-red-50 text-red-700 ring-red-600/20',
  no_show: 'bg-amber-50 text-amber-700 ring-amber-600/20',
}

/**
 * Get background color for appointment based on status
 * Used for FullCalendar event styling
 */
export function getStatusColor(status: string): string {
  return (STATUS_COLORS[status] ?? STATUS_COLORS.scheduled) as string
}

/**
 * Get Tailwind classes for status badge
 * Includes background, text color, and ring border
 */
export function getStatusBadgeClass(status: string): string {
  const baseClass = 'px-2.5 py-1 text-xs font-medium rounded-full ring-1 ring-inset'
  const statusClass = (STATUS_BADGE_CLASSES[status] ??
    STATUS_BADGE_CLASSES.scheduled) as string
  return `${baseClass} ${statusClass}`
}
