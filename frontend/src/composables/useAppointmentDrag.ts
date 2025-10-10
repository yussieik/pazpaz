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

  const keyboardState = ref<KeyboardRescheduleState>({
    active: false,
    appointmentId: null,
    currentStart: null,
    currentEnd: null,
    originalStart: null,
    originalEnd: null,
  })

  let dragInitTimer: ReturnType<typeof setTimeout> | null = null
  let longPressTimer: ReturnType<typeof setTimeout> | null = null
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
    mouseEvent.preventDefault()

    dragInitTimer = setTimeout(() => {
      initiateDrag(event, mouseEvent)
    }, 150)

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

    longPressTimer = setTimeout(() => {
      triggerMobileReschedule(event)
    }, 300)

    const handleTouchEnd = () => {
      if (longPressTimer) {
        clearTimeout(longPressTimer)
        longPressTimer = null
      }
      touchStartPos = null
      document.removeEventListener('touchend', handleTouchEnd)
      document.removeEventListener('touchmove', handleTouchMove)
    }

    const handleTouchMove = (e: TouchEvent) => {
      if (!touchStartPos) return

      const touch = e.touches[0]
      if (!touch) return
      const deltaX = Math.abs(touch.clientX - touchStartPos.x)
      const deltaY = Math.abs(touch.clientY - touchStartPos.y)

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

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
    document.body.style.cursor = 'grabbing'
  }

  /**
   * Handle mouse move during drag
   */
  function handleMouseMove(mouseEvent: MouseEvent) {
    if (!dragState.value.isDragging) return

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

    document.removeEventListener('mousemove', handleMouseMove)
    document.removeEventListener('mouseup', handleMouseUp)
    document.body.style.cursor = ''

    if (
      !dragState.value.currentStart ||
      !dragState.value.originalStart ||
      dragState.value.currentStart.getTime() === dragState.value.originalStart.getTime()
    ) {
      cancelDrag()
      return
    }

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

    dragState.value.currentStart = newStart
    dragState.value.currentEnd = newEnd
    dragState.value.appointmentId = info.event.id
    dragState.value.revertFn = info.revert

    try {
      const result = await checkAppointmentConflicts({
        scheduled_start: toISOString(newStart),
        scheduled_end: toISOString(newEnd),
        exclude_appointment_id: info.event.id,
      })

      dragState.value.hasConflict = result.has_conflict
      dragState.value.conflictData = result

      info.event.setStart(newStart)
      info.event.setEnd(newEnd)

      await onReschedule(info.event.id, newStart, newEnd, result.has_conflict)

      if (!result.has_conflict) {
        resetDragState()
      }
    } catch (error) {
      console.error('Failed to reschedule appointment:', error)
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

    resetDragState()
    await onReschedule(appointmentId, newStart, newEnd, hasConflict)
  }

  /**
   * Cancel drag operation
   */
  function cancelDrag() {
    if (dragState.value.originalEvent && dragState.value.originalStart) {
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
        newStart = new Date(keyboardState.value.currentStart.getTime() - 15 * 60000)
        break
      case 'ArrowDown':
        newStart = new Date(keyboardState.value.currentStart.getTime() + 15 * 60000)
        break
      case 'ArrowLeft':
        newStart = new Date(keyboardState.value.currentStart)
        newStart.setDate(newStart.getDate() - 1)
        break
      case 'ArrowRight':
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

    announceToScreenReader(`Moved to ${formatDateAndTime(newStart)}`)

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

    const conflictResult = await checkAppointmentConflicts({
      scheduled_start: toISOString(newStart),
      scheduled_end: toISOString(newEnd),
      exclude_appointment_id: appointmentId,
    })

    resetKeyboardState()
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
    dragState,
    keyboardState,
    isDragging,
    isKeyboardRescheduleActive,
    ghostTimeRange,
    ghostDateTimePreview,
    keyboardTimeRange,
    handleEventMouseDown,
    handleEventTouchStart,
    handleEventDrop,
    cancelDrag,
    activateKeyboardReschedule,
    handleKeyboardNavigation,
    confirmKeyboardReschedule,
    cancelKeyboardReschedule,
    cleanup,
  }
}
