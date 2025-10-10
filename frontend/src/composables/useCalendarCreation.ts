import { ref } from 'vue'
import type { DateClickArg } from '@fullcalendar/interaction'

/**
 * Composable for handling double-click appointment creation on calendar
 *
 * Features:
 * - Double-click detection with 500ms threshold
 * - Time rounding to nearest 15-minute increment
 * - View-specific defaults (month view vs. time grid views)
 * - Pre-fills date/time with 60-minute default duration
 */
export function useCalendarCreation(
  openCreateModal: (prefillData: { start: Date; end: Date }) => void
) {
  const lastClickTime = ref(0)
  const lastClickDate = ref<string | null>(null)
  const DOUBLE_CLICK_THRESHOLD = 500

  /**
   * Round date to nearest 15-minute increment
   * Matches existing snapDuration: '00:15:00' in calendar config
   */
  function roundToNearestQuarterHour(date: Date): Date {
    const ms = 1000 * 60 * 15 // 15 minutes
    return new Date(Math.round(date.getTime() / ms) * ms)
  }

  /**
   * Handle calendar date click - detects double-clicks
   *
   * @param info - FullCalendar DateClickArg with date, dateStr, allDay, view
   */
  function handleDateClick(info: DateClickArg) {
    const now = Date.now()
    const dateStr = info.dateStr

    if (
      now - lastClickTime.value < DOUBLE_CLICK_THRESHOLD &&
      lastClickDate.value === dateStr
    ) {
      handleDoubleClick(info.date, info.view.type)
      lastClickTime.value = 0
      lastClickDate.value = null
    } else {
      lastClickTime.value = now
      lastClickDate.value = dateStr
    }
  }

  /**
   * Handle double-click - open modal with pre-filled date/time
   *
   * @param date - Clicked date/time
   * @param viewType - Calendar view type (timeGridWeek, timeGridDay, dayGridMonth)
   */
  function handleDoubleClick(date: Date, viewType: string) {
    let startTime: Date
    let endTime: Date

    if (viewType === 'dayGridMonth') {
      startTime = new Date(date)
      startTime.setHours(9, 0, 0, 0)
      endTime = new Date(startTime)
      endTime.setHours(10, 0, 0, 0)
    } else {
      startTime = roundToNearestQuarterHour(date)
      endTime = new Date(startTime.getTime() + 60 * 60 * 1000)
    }

    openCreateModal({
      start: startTime,
      end: endTime,
    })
  }

  return {
    handleDateClick,
  }
}
