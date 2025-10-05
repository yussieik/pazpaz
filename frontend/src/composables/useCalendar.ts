import { ref, computed } from 'vue'
import type { CalendarOptions } from '@fullcalendar/core'
import type { ViewType } from '@/types/calendar'
import { formatDateRange } from '@/utils/calendar/dateFormatters'
import {
  CALENDAR_PLUGINS,
  BASE_CALENDAR_OPTIONS,
} from '@/utils/calendar/calendarConfig'
import { useAppointmentsStore } from '@/stores/appointments'

/**
 * Composable for managing calendar state and navigation
 *
 * Handles:
 * - Current view (week/day/month)
 * - Current date and date range
 * - Navigation (prev/next/today)
 * - View switching with date preservation
 * - Date range fetching
 */
export function useCalendar() {
  const appointmentsStore = useAppointmentsStore()

  // Core calendar state
  const currentView = ref<ViewType>('timeGridWeek')
  const currentDate = ref<Date>(new Date())
  const currentDateRange = ref<{ start: Date; end: Date }>({
    start: new Date(),
    end: new Date(),
  })

  // Note: Removed lastFetchedRange tracking - now handled by store's loadedRange
  // The store's ensureAppointmentsLoaded() method implements sliding window pattern

  // Track if we're in the middle of a view change to prevent currentDate updates
  const isViewChanging = ref(false)

  // Track last stable formatted date range to prevent flicker during view transitions
  const lastStableDateRange = ref<string>('')

  /**
   * Formatted date range for display in toolbar
   * During view transitions, maintain the last stable value to prevent flicker
   */
  const formattedDateRange = computed(() => {
    const formatted = formatDateRange(
      currentDateRange.value.start,
      currentDateRange.value.end,
      currentView.value,
      currentDate.value
    )

    // During view changes, keep showing the last stable value to prevent flicker
    if (isViewChanging.value) {
      return lastStableDateRange.value || formatted
    }

    // Update last stable value when not changing views
    lastStableDateRange.value = formatted
    return formatted
  })

  /**
   * Handle date range changes when user navigates
   *
   * IMPORTANT: Only update currentDate during user-initiated navigation (prev/next/today),
   * NOT during view changes. This prevents date drift when switching between Day/Week/Month views.
   *
   * When switching views:
   * - isViewChanging flag is set to true in changeView()
   * - FullCalendar fires datesSet with new visible range
   * - We skip updating currentDate to preserve the user's original date
   * - isViewChanging flag is reset in changeView() via nextTick
   * - This function also resets it defensively as a safety measure
   *
   * PERFORMANCE OPTIMIZATION:
   * Uses store's ensureAppointmentsLoaded() with actual visible range:
   * - Fetches appointments for the exact range FullCalendar is displaying
   * - Only fetches if the visible range is not fully covered by loaded data
   * - Prevents unnecessary API calls when navigating within loaded range
   */
  function handleDatesSet(dateInfo: { start: Date; end: Date }) {
    currentDateRange.value = {
      start: dateInfo.start,
      end: dateInfo.end,
    }

    // Only update currentDate during user navigation, not during view changes
    // This prevents the date from drifting to the center of the month when switching to Month view
    if (!isViewChanging.value) {
      // Update currentDate to center of visible range for user-initiated navigation
      const centerTime = (dateInfo.start.getTime() + dateInfo.end.getTime()) / 2
      currentDate.value = new Date(centerTime)
    }

    // Always reset flag as a safety measure (redundant with nextTick in changeView, but provides defense in depth)
    if (isViewChanging.value) {
      isViewChanging.value = false
    }

    // Fetch appointments for the visible range
    // This ensures we always have data for what the user is looking at
    appointmentsStore.ensureAppointmentsLoaded(dateInfo.start, dateInfo.end)
  }

  /**
   * Navigation: Go to previous period
   * Update the reactive currentDate, which triggers calendar re-render via computed options
   */
  function handlePrev() {
    const date = new Date(currentDate.value)

    if (currentView.value === 'timeGridDay') {
      date.setDate(date.getDate() - 1)
    } else if (currentView.value === 'timeGridWeek') {
      date.setDate(date.getDate() - 7)
    } else {
      date.setMonth(date.getMonth() - 1)
    }

    currentDate.value = date
  }

  /**
   * Navigation: Go to next period
   * Update the reactive currentDate, which triggers calendar re-render via computed options
   */
  function handleNext() {
    const date = new Date(currentDate.value)

    if (currentView.value === 'timeGridDay') {
      date.setDate(date.getDate() + 1)
    } else if (currentView.value === 'timeGridWeek') {
      date.setDate(date.getDate() + 7)
    } else {
      date.setMonth(date.getMonth() + 1)
    }

    currentDate.value = date
  }

  /**
   * Navigation: Go to today
   * Reset currentDate to now, which triggers calendar re-render via computed options
   */
  function handleToday() {
    currentDate.value = new Date()
  }

  /**
   * Change calendar view - simplest reliable approach
   *
   * Strategy:
   * 1. Set isViewChanging flag to prevent date drift in handleDatesSet
   * 2. Update currentView state
   * 3. Key change triggers full re-mount with new view (100% reliable)
   * 4. Flag gets reset in handleDatesSet after re-mount completes
   *
   * This ensures:
   * - 100% reliable view switching (no edge cases)
   * - Date preservation across view changes (flag prevents updates)
   * - Simple code with no API timing issues
   */
  function changeView(view: ViewType) {
    isViewChanging.value = true
    currentView.value = view
    // Key change triggers re-mount, isViewChanging prevents date drift
    // Flag will be reset in handleDatesSet
  }

  /**
   * Build FullCalendar options computed property
   * Must be computed so it updates when currentDate or currentView change
   *
   * NOTE: events and eventClick will be provided by useCalendarEvents
   * datesSet callback will be provided by the consumer
   */
  function buildCalendarOptions(
    events: CalendarOptions['events'],
    eventClick: CalendarOptions['eventClick']
  ): CalendarOptions {
    return {
      plugins: CALENDAR_PLUGINS,
      initialView: currentView.value,
      initialDate: currentDate.value,
      events,
      eventClick,
      datesSet: handleDatesSet,
      ...BASE_CALENDAR_OPTIONS,
    }
  }

  return {
    // State
    currentView,
    currentDate,
    currentDateRange,
    formattedDateRange,

    // Methods
    changeView,
    handlePrev,
    handleNext,
    handleToday,
    buildCalendarOptions,
  }
}
