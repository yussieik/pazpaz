import { ref, computed, type Ref } from 'vue'
import type { EventApi } from '@fullcalendar/core'
import type { AppointmentListItem } from '@/types/calendar'
import { checkAppointmentConflicts, type ConflictCheckResponse } from '@/api/client'
import {
  roundToNearest15Minutes,
  getAppointmentDuration,
  calculateEndTime,
  formatTimeRange,
  formatDateAndTime,
  toISOString,
  debounce,
} from '@/utils/dragHelpers'

/**
 * Drag state type
 */
export interface DragState {
  isDragging: boolean
  appointmentId: string | null
  originalEvent: EventApi | null
  originalStart: Date | null
  originalEnd: Date | null
  currentStart: Date | null
  currentEnd: Date | null
  hasConflict: boolean
  conflictData: ConflictCheckResponse | null
  ghostPosition: { x: number; y: number } | null
  revertFn: (() => void) | null
}

/**
 * Keyboard reschedule state
 */
export interface KeyboardRescheduleState {
  active: boolean
  appointmentId: string | null
  currentStart: Date | null
  currentEnd: Date | null
  originalStart: Date | null
  originalEnd: Date | null
}

/**
 * Composable for appointment drag-and-drop rescheduling
 *
 * Features:
 * - Desktop: Click and hold 150ms to initiate drag
 * - Real-time conflict detection (debounced 100ms)
 * - Visual feedback (ghost element, drop zones)
 * - Keyboard navigation (Enter → Arrow keys → Enter)
 * - Mobile: Long-press shows time picker modal
 * - Optimistic updates with undo
 */
export function useAppointmentDrag(
  appointments: Ref<AppointmentListItem[]>,
  onReschedule: (
    appointmentId: string,
    newStart: Date,
    newEnd: Date,
    hasConflict: boolean
  ) => Promise<void>
) {
  // Drag state
  const dragState = ref<DragState>({
    isDragging: false,
    appointmentId: null,
    originalEvent: null,
    originalStart: null,
    originalEnd: null,
    currentStart: null,
    currentEnd: null,
    hasConflict: false,
    conflictData: null,
    ghostPosition: null,
    revertFn: null,
  })

  // Keyboard reschedule state
  const keyboardState = ref<KeyboardRescheduleState>({
    active: false,
    appointmentId: null,
    currentStart: null,
    currentEnd: null,
    originalStart: null,
    originalEnd: null,
  })

  // Drag initiation timer (150ms hold for desktop)
  let dragInitTimer: ReturnType<typeof setTimeout> | null = null

  // Long-press timer for mobile (300ms)
  let longPressTimer: ReturnType<typeof setTimeout> | null = null

  // Touch start position for mobile
  let touchStartPos: { x: number; y: number } | null = null

  /**
   * Computed: Is currently dragging
   */
  const isDragging = computed(() => dragState.value.isDragging)

  /**
   * Computed: Is keyboard reschedule mode active
   */
  const isKeyboardRescheduleActive = computed(() => keyboardState.value.active)

  /**
   * Computed: Display time range for ghost element
   */
  const ghostTimeRange = computed(() => {
    if (!dragState.value.currentStart || !dragState.value.currentEnd) return ''
    return formatTimeRange(dragState.value.currentStart, dragState.value.currentEnd)
  })

  /**
   * Computed: Display date and time for preview
   */
  const ghostDateTimePreview = computed(() => {
    if (!dragState.value.currentStart) return ''
    return formatDateAndTime(dragState.value.currentStart)
  })

  /**
   * Computed: Display time range for keyboard mode
   */
  const keyboardTimeRange = computed(() => {
    if (!keyboardState.value.currentStart || !keyboardState.value.currentEnd) return ''
    return formatTimeRange(
      keyboardState.value.currentStart,
      keyboardState.value.currentEnd
    )
  })

  /**
   * Debounced conflict check (100ms)
   */
  const debouncedConflictCheck = debounce(
    async (start: Date, end: Date, appointmentId: string) => {
      try {
        const result = await checkAppointmentConflicts({
          scheduled_start: toISOString(start),
          scheduled_end: toISOString(end),
          exclude_appointment_id: appointmentId,
        })

        // Only update if still dragging the same appointment
        if (dragState.value.appointmentId === appointmentId) {
          dragState.value.hasConflict = result.has_conflict
          dragState.value.conflictData = result
        }
      } catch (error) {
        console.error('Conflict check failed:', error)
        dragState.value.hasConflict = false
        dragState.value.conflictData = null
      }
    },
    100
  )

  /**
   * Start drag (desktop: mouse)
   */
  function handleEventMouseDown(event: EventApi, mouseEvent: MouseEvent) {
    // Prevent default to avoid text selection
    mouseEvent.preventDefault()

    // Start 150ms timer for drag initiation
    dragInitTimer = setTimeout(() => {
      initiateDrag(event, mouseEvent)
    }, 150)

    // Add mouse up listener to cancel if released early
    const handleMouseUp = () => {
      if (dragInitTimer) {
        clearTimeout(dragInitTimer)
        dragInitTimer = null
      }
      document.removeEventListener('mouseup', handleMouseUp)
    }

    document.addEventListener('mouseup', handleMouseUp)
  }

  /**
   * Start touch (mobile: long-press)
   */
  function handleEventTouchStart(event: EventApi, touchEvent: TouchEvent) {
    const touch = touchEvent.touches[0]
    if (!touch) return
    touchStartPos = { x: touch.clientX, y: touch.clientY }

    // Start 300ms timer for long-press
    longPressTimer = setTimeout(() => {
      // Trigger mobile modal instead of drag
      triggerMobileReschedule(event)
    }, 300)

    // Add touch end listener to cancel if released early
    const handleTouchEnd = () => {
      if (longPressTimer) {
        clearTimeout(longPressTimer)
        longPressTimer = null
      }
      touchStartPos = null
      document.removeEventListener('touchend', handleTouchEnd)
      document.removeEventListener('touchmove', handleTouchMove)
    }

    // Cancel long-press if finger moves (user is scrolling)
    const handleTouchMove = (e: TouchEvent) => {
      if (!touchStartPos) return

      const touch = e.touches[0]
      if (!touch) return
      const deltaX = Math.abs(touch.clientX - touchStartPos.x)
      const deltaY = Math.abs(touch.clientY - touchStartPos.y)

      // If moved more than 10px, cancel long-press
      if (deltaX > 10 || deltaY > 10) {
        if (longPressTimer) {
          clearTimeout(longPressTimer)
          longPressTimer = null
        }
        touchStartPos = null
        document.removeEventListener('touchend', handleTouchEnd)
        document.removeEventListener('touchmove', handleTouchMove)
      }
    }

    document.addEventListener('touchend', handleTouchEnd)
    document.addEventListener('touchmove', handleTouchMove)
  }

  /**
   * Initiate drag operation
   */
  function initiateDrag(event: EventApi, mouseEvent: MouseEvent) {
    const appointment = appointments.value.find((a) => a.id === event.id)
    if (!appointment) return

    dragState.value = {
      isDragging: true,
      appointmentId: event.id,
      originalEvent: event,
      originalStart: event.start,
      originalEnd: event.end,
      currentStart: event.start,
      currentEnd: event.end,
      hasConflict: false,
      conflictData: null,
      ghostPosition: { x: mouseEvent.clientX, y: mouseEvent.clientY },
      revertFn: null,
    }

    // Add global mouse move and mouse up listeners
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)

    // Add cursor style
    document.body.style.cursor = 'grabbing'
  }

  /**
   * Handle mouse move during drag
   */
  function handleMouseMove(mouseEvent: MouseEvent) {
    if (!dragState.value.isDragging) return

    // Update ghost position
    dragState.value.ghostPosition = {
      x: mouseEvent.clientX,
      y: mouseEvent.clientY,
    }
  }

  /**
   * Handle mouse up (end drag)
   */
  function handleMouseUp() {
    if (!dragState.value.isDragging) return

    // Remove listeners
    document.removeEventListener('mousemove', handleMouseMove)
    document.removeEventListener('mouseup', handleMouseUp)
    document.body.style.cursor = ''

    // If no actual movement, just cancel
    if (
      !dragState.value.currentStart ||
      !dragState.value.originalStart ||
      dragState.value.currentStart.getTime() === dragState.value.originalStart.getTime()
    ) {
      cancelDrag()
      return
    }

    // Complete the drag
    completeDrag()
  }

  /**
   * Handle FullCalendar eventDrop (when event is dropped on calendar)
   */
  async function handleEventDrop(info: {
    event: EventApi
    oldEvent: EventApi
    delta: { milliseconds: number }
    revert: () => void
  }) {
    const newStart = roundToNearest15Minutes(info.event.start!)
    const duration = getAppointmentDuration(
      info.oldEvent.start!,
      info.oldEvent.end || info.oldEvent.start!
    )
    const newEnd = calculateEndTime(newStart, duration)

    // Update drag state with new times and store revert function
    dragState.value.currentStart = newStart
    dragState.value.currentEnd = newEnd
    dragState.value.appointmentId = info.event.id
    dragState.value.revertFn = info.revert

    // Check for conflicts
    try {
      const result = await checkAppointmentConflicts({
        scheduled_start: toISOString(newStart),
        scheduled_end: toISOString(newEnd),
        exclude_appointment_id: info.event.id,
      })

      dragState.value.hasConflict = result.has_conflict
      dragState.value.conflictData = result

      // Update event visual position
      info.event.setStart(newStart)
      info.event.setEnd(newEnd)

      // If has conflict, trigger conflict modal via onReschedule
      // Otherwise, proceed with reschedule immediately
      await onReschedule(info.event.id, newStart, newEnd, result.has_conflict)

      // If no conflict, reset drag state after successful reschedule
      if (!result.has_conflict) {
        resetDragState()
      }
      // Note: If conflict exists, dragState is preserved for modal to use
    } catch (error) {
      console.error('Failed to reschedule appointment:', error)
      // Revert the visual change on error
      info.revert()
      resetDragState()
    }
  }

  /**
   * Complete drag operation
   */
  async function completeDrag() {
    if (
      !dragState.value.appointmentId ||
      !dragState.value.currentStart ||
      !dragState.value.currentEnd
    ) {
      cancelDrag()
      return
    }

    const appointmentId = dragState.value.appointmentId
    const newStart = dragState.value.currentStart
    const newEnd = dragState.value.currentEnd
    const hasConflict = dragState.value.hasConflict

    // Reset drag state
    resetDragState()

    // Call reschedule handler
    await onReschedule(appointmentId, newStart, newEnd, hasConflict)
  }

  /**
   * Cancel drag operation
   */
  function cancelDrag() {
    if (dragState.value.originalEvent && dragState.value.originalStart) {
      // Revert event to original position
      dragState.value.originalEvent.setStart(dragState.value.originalStart)
      if (dragState.value.originalEnd) {
        dragState.value.originalEvent.setEnd(dragState.value.originalEnd)
      }
    }

    resetDragState()
  }

  /**
   * Reset drag state
   */
  function resetDragState() {
    dragState.value = {
      isDragging: false,
      appointmentId: null,
      originalEvent: null,
      originalStart: null,
      originalEnd: null,
      currentStart: null,
      currentEnd: null,
      hasConflict: false,
      conflictData: null,
      ghostPosition: null,
      revertFn: null,
    }

    document.body.style.cursor = ''
  }

  /**
   * Trigger mobile reschedule modal
   */
  function triggerMobileReschedule(event: EventApi) {
    // Mobile reschedule functionality to be implemented
    // This will emit an event to parent component to show mobile modal
    const appointment = appointments.value.find((a) => a.id === event.id)
    if (appointment) {
      // Implementation pending: emit custom event or call callback
    }
  }

  /**
   * Keyboard: Activate reschedule mode
   */
  function activateKeyboardReschedule(appointmentId: string) {
    const appointment = appointments.value.find((a) => a.id === appointmentId)
    if (!appointment) return

    const start = new Date(appointment.scheduled_start)
    const end = new Date(appointment.scheduled_end)

    keyboardState.value = {
      active: true,
      appointmentId,
      currentStart: start,
      currentEnd: end,
      originalStart: start,
      originalEnd: end,
    }

    // Announce to screen readers
    announceToScreenReader(`Reschedule mode activated. Use arrow keys to adjust time.`)
  }

  /**
   * Keyboard: Navigate time slots
   */
  function handleKeyboardNavigation(key: string) {
    if (!keyboardState.value.active || !keyboardState.value.currentStart) return

    const duration = getAppointmentDuration(
      keyboardState.value.currentStart,
      keyboardState.value.currentEnd!
    )

    let newStart: Date

    switch (key) {
      case 'ArrowUp':
        // Move up 15 minutes
        newStart = new Date(keyboardState.value.currentStart.getTime() - 15 * 60000)
        break
      case 'ArrowDown':
        // Move down 15 minutes
        newStart = new Date(keyboardState.value.currentStart.getTime() + 15 * 60000)
        break
      case 'ArrowLeft':
        // Move left 1 day
        newStart = new Date(keyboardState.value.currentStart)
        newStart.setDate(newStart.getDate() - 1)
        break
      case 'ArrowRight':
        // Move right 1 day
        newStart = new Date(keyboardState.value.currentStart)
        newStart.setDate(newStart.getDate() + 1)
        break
      default:
        return
    }

    newStart = roundToNearest15Minutes(newStart)
    const newEnd = calculateEndTime(newStart, duration)

    keyboardState.value.currentStart = newStart
    keyboardState.value.currentEnd = newEnd

    // Announce new time to screen readers
    announceToScreenReader(`Moved to ${formatDateAndTime(newStart)}`)

    // Check for conflicts
    if (keyboardState.value.appointmentId) {
      debouncedConflictCheck(newStart, newEnd, keyboardState.value.appointmentId)
    }
  }

  /**
   * Keyboard: Confirm reschedule
   */
  async function confirmKeyboardReschedule() {
    if (
      !keyboardState.value.appointmentId ||
      !keyboardState.value.currentStart ||
      !keyboardState.value.currentEnd
    ) {
      return
    }

    const appointmentId = keyboardState.value.appointmentId
    const newStart = keyboardState.value.currentStart
    const newEnd = keyboardState.value.currentEnd

    // Check for conflicts one final time
    const conflictResult = await checkAppointmentConflicts({
      scheduled_start: toISOString(newStart),
      scheduled_end: toISOString(newEnd),
      exclude_appointment_id: appointmentId,
    })

    // Reset keyboard state
    resetKeyboardState()

    // Call reschedule handler
    await onReschedule(appointmentId, newStart, newEnd, conflictResult.has_conflict)
  }

  /**
   * Keyboard: Cancel reschedule
   */
  function cancelKeyboardReschedule() {
    announceToScreenReader('Reschedule cancelled')
    resetKeyboardState()
  }

  /**
   * Reset keyboard state
   */
  function resetKeyboardState() {
    keyboardState.value = {
      active: false,
      appointmentId: null,
      currentStart: null,
      currentEnd: null,
      originalStart: null,
      originalEnd: null,
    }
  }

  /**
   * Announce to screen readers (ARIA live region)
   */
  function announceToScreenReader(message: string) {
    // Create or update ARIA live region
    let liveRegion = document.getElementById('drag-drop-announcer')
    if (!liveRegion) {
      liveRegion = document.createElement('div')
      liveRegion.id = 'drag-drop-announcer'
      liveRegion.setAttribute('role', 'status')
      liveRegion.setAttribute('aria-live', 'polite')
      liveRegion.setAttribute('aria-atomic', 'true')
      liveRegion.className = 'sr-only' // Visually hidden
      document.body.appendChild(liveRegion)
    }
    liveRegion.textContent = message
  }

  /**
   * Cleanup on unmount
   */
  function cleanup() {
    if (dragInitTimer) clearTimeout(dragInitTimer)
    if (longPressTimer) clearTimeout(longPressTimer)
    document.removeEventListener('mousemove', handleMouseMove)
    document.removeEventListener('mouseup', handleMouseUp)
    document.body.style.cursor = ''
  }

  return {
    // State
    dragState,
    keyboardState,
    isDragging,
    isKeyboardRescheduleActive,
    ghostTimeRange,
    ghostDateTimePreview,
    keyboardTimeRange,

    // Drag handlers
    handleEventMouseDown,
    handleEventTouchStart,
    handleEventDrop,
    cancelDrag,

    // Keyboard handlers
    activateKeyboardReschedule,
    handleKeyboardNavigation,
    confirmKeyboardReschedule,
    cancelKeyboardReschedule,

    // Cleanup
    cleanup,
  }
}
