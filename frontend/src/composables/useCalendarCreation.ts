import type { DateClickArg } from '@fullcalendar/interaction'

/**
 * Composable for handling single-click appointment creation on calendar
 *
 * Features:
 * - Single-click to open appointment creation modal
 * - Time rounding to nearest 15-minute increment
 * - View-specific defaults (month view vs. time grid views)
 * - Pre-fills date/time with 60-minute default duration
 */
export function useCalendarCreation(
  openCreateModal: (prefillData: { start: Date; end: Date }) => void
) {
  /**
   * Round date to nearest 15-minute increment
   * Matches existing snapDuration: '00:15:00' in calendar config
   */
  function roundToNearestQuarterHour(date: Date): Date {
    const ms = 1000 * 60 * 15 // 15 minutes
    return new Date(Math.round(date.getTime() / ms) * ms)
  }

  /**
   * Handle calendar date click - opens appointment creation modal
   *
   * @param info - FullCalendar DateClickArg with date, dateStr, allDay, view
   */
  function handleDateClick(info: DateClickArg) {
    handleClick(info.date, info.view.type)
  }

  /**
   * Handle click - open modal with pre-filled date/time
   *
   * @param date - Clicked date/time
   * @param viewType - Calendar view type (timeGridWeek, timeGridDay, dayGridMonth)
   */
  function handleClick(date: Date, viewType: string) {
    let startTime: Date
    let endTime: Date

    if (viewType === 'dayGridMonth') {
      // Month view: Default to 9 AM with 1-hour duration
      startTime = new Date(date)
      startTime.setHours(9, 0, 0, 0)
      endTime = new Date(startTime)
      endTime.setHours(10, 0, 0, 0)
    } else {
      // Week/Day view: Use clicked time (rounded) with 1-hour duration
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
