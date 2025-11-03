/**
 * Locale-aware date formatting utility
 * =====================================
 * Wraps date-fns format() with automatic locale detection
 *
 * Usage:
 *   const { formatDate } = useDateFormat()
 *   formatDate(new Date(), 'PPP') // "January 5, 2025" or "5 בינואר 2025"
 */

import { format as dateFnsFormat } from 'date-fns'
import { he } from 'date-fns/locale'
import { useI18n } from '@/composables/useI18n'

export function useDateFormat() {
  const { locale } = useI18n()

  /**
   * Format a date with locale-aware formatting
   *
   * @param date - Date object or ISO string
   * @param formatStr - date-fns format string (e.g., 'PPP', 'MMM d, yyyy')
   * @returns Formatted date string in current locale
   *
   * @example
   * formatDate(new Date(), 'PPP')
   * // English: "January 5, 2025"
   * // Hebrew: "5 בינואר 2025"
   */
  function formatDate(date: Date | string, formatStr: string): string {
    const dateObj = typeof date === 'string' ? new Date(date) : date

    return dateFnsFormat(dateObj, formatStr, {
      locale: locale.value === 'he' ? he : undefined,
    })
  }

  return { formatDate }
}
