<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppointmentsStore } from '@/stores/appointments'
import FullCalendar from '@fullcalendar/vue3'
import type { EventDropArg } from '@fullcalendar/core'
import type { AppointmentListItem, AppointmentFormData } from '@/types/calendar'
import { useCalendar } from '@/composables/useCalendar'
import { useCalendarEvents } from '@/composables/useCalendarEvents'
import { useCalendarKeyboardShortcuts } from '@/composables/useCalendarKeyboardShortcuts'
import { useCalendarLoading } from '@/composables/useCalendarLoading'
import { useAppointmentDrag } from '@/composables/useAppointmentDrag'
import { useCalendarCreation } from '@/composables/useCalendarCreation'
import { useScreenReader } from '@/composables/useScreenReader'
import { toISOString } from '@/utils/dragHelpers'
import type { ConflictingAppointment } from '@/api/client'
import type { AppointmentStatus } from '@/types/calendar'
import PageHeader from '@/components/common/PageHeader.vue'
import CalendarToolbar from '@/components/calendar/CalendarToolbar.vue'
import AppointmentDetailsModal from '@/components/calendar/AppointmentDetailsModal.vue'
import AppointmentFormModal from '@/components/calendar/AppointmentFormModal.vue'
import CancelAppointmentDialog from '@/components/calendar/CancelAppointmentDialog.vue'
import DeleteAppointmentDialog from '@/components/calendar/DeleteAppointmentDialog.vue'
import CalendarLoadingState from '@/components/calendar/CalendarLoadingState.vue'
import DragConflictModal from '@/components/calendar/DragConflictModal.vue'
import MobileRescheduleModal from '@/components/calendar/MobileRescheduleModal.vue'
import UndoToast from '@/components/common/UndoToast.vue'

/**
 * Calendar View - appointment scheduling with weekly/day/month views
 *
 * Implemented (M2):
 * - Appointment creation/editing modals
 * - Cancel appointment dialog
 * - Conflict detection with soft warning
 * - Drag-and-drop rescheduling (desktop)
 * - Keyboard navigation for rescheduling
 * - Mobile time picker modal
 * - Optimistic updates with undo
 */

const route = useRoute()
const router = useRouter()
const appointmentsStore = useAppointmentsStore()
const calendarRef = ref<InstanceType<typeof FullCalendar>>()
const toolbarRef = ref<InstanceType<typeof CalendarToolbar>>()

// Modal/dialog state
const showCreateModal = ref(false)
const showEditModal = ref(false)
const showCancelDialog = ref(false)
const showDeleteDialog = ref(false)
const appointmentToEdit = ref<AppointmentListItem | null>(null)
const appointmentToCancel = ref<AppointmentListItem | null>(null)
const appointmentToDelete = ref<AppointmentListItem | null>(null)

// Double-click create state
const createModalPrefillData = ref<{ start: Date; end: Date } | null>(null)

// Drag-and-drop state
const showDragConflictModal = ref(false)
const showMobileRescheduleModal = ref(false)
const dragConflictData = ref<{
  appointmentId: string
  newStart: Date
  newEnd: Date
  conflicts: ConflictingAppointment[]
} | null>(null)
const mobileRescheduleAppointment = ref<AppointmentListItem | null>(null)
const undoTimeout = ref<ReturnType<typeof setTimeout> | null>(null)
const showUndoToast = ref(false)
const undoToastMessage = ref('')
const undoData = ref<{
  appointmentId: string
  originalStart: string
  originalEnd: string
} | null>(null)

// Cancellation undo state (separate from reschedule undo)
const showCancelUndoToast = ref(false)
const undoCancelTimeout = ref<ReturnType<typeof setTimeout> | null>(null)
const undoCancelData = ref<{
  appointmentId: string
  originalStatus: AppointmentStatus
  originalNotes?: string
} | null>(null)

// Screen reader announcements
const { announcement: screenReaderAnnouncement, announce } = useScreenReader()

// Calendar state and navigation
const {
  currentView,
  currentDate,
  currentDateRange,
  formattedDateRange,
  changeView,
  handlePrev,
  handleNext,
  handleToday,
  buildCalendarOptions,
} = useCalendar()

// Calendar events and selection
const { selectedAppointment, calendarEvents, handleEventClick } = useCalendarEvents()

// Debounced loading state
const { showLoadingSpinner } = useCalendarLoading()

/**
 * Open create modal with pre-filled date/time from calendar double-click
 */
function openCreateModalWithPrefill(prefillData: { start: Date; end: Date }) {
  createModalPrefillData.value = prefillData
  showCreateModal.value = true

  // Screen reader announcement
  const dateStr = prefillData.start.toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  })
  const timeStr = prefillData.start.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
  })

  announce(
    `Creating new appointment for ${dateStr} at ${timeStr}. Fill in client and details.`
  )
}

// Initialize calendar creation composable
const { handleDateClick } = useCalendarCreation(openCreateModalWithPrefill)

// Cell hover highlighting for timeGrid views using overlay
const hoverOverlayVisible = ref(false)
const hoverOverlayStyle = ref({ top: '0px', left: '0px', width: '0px', height: '0px' })
const isHoverInOffHours = ref(false)

function handleCalendarMouseMove(event: MouseEvent) {
  // Only apply to timeGrid views (week/day)
  if (!currentView.value.includes('timeGrid')) {
    hoverOverlayVisible.value = false
    return
  }

  const target = event.target as HTMLElement

  // Find the time slot lane (horizontal row)
  // The .fc-non-business overlay sits on top of slots in off-hours, blocking direct access
  let slotLane = target.closest('.fc-timegrid-slot-lane')

  if (!slotLane) {
    // Off-hours: .fc-non-business overlay blocks the slot lane
    // Use elementsFromPoint to find the slot lane underneath
    const allElements = document.elementsFromPoint(event.clientX, event.clientY)
    slotLane = allElements.find((el) => el.classList.contains('fc-timegrid-slot-lane')) as
      | HTMLElement
      | undefined
  }

  if (!slotLane || !(slotLane instanceof HTMLElement)) {
    hoverOverlayVisible.value = false
    return
  }

  // FullCalendar's structure: the background grid and events are in separate layers
  // We need to find which day column we're in by looking at the mouse X position
  // and comparing it to the column positions

  // Get all day columns in the current view
  const dayColumns = document.querySelectorAll('.fc-timegrid-col')

  if (dayColumns.length === 0) {
    hoverOverlayVisible.value = false
    return
  }

  // Find which column the mouse is over based on X coordinate
  const mouseX = event.clientX
  let targetColumn: HTMLElement | null = null

  for (const col of dayColumns) {
    const rect = col.getBoundingClientRect()
    if (mouseX >= rect.left && mouseX <= rect.right) {
      targetColumn = col as HTMLElement
      break
    }
  }

  if (!targetColumn) {
    hoverOverlayVisible.value = false
    return
  }

  // Now we have both the row (slotLane) and column (targetColumn)
  const slotRect = slotLane.getBoundingClientRect()
  const colRect = targetColumn.getBoundingClientRect()

  // Check if there's an event in this cell
  // Look for events at multiple points within the cell to catch events that don't fill the full width
  const eventsAtPosition = document.elementsFromPoint(event.clientX, event.clientY)
  const hasEventAtCursor = eventsAtPosition.some((el) => el.classList.contains('fc-event'))

  // Check center of the cell and left/right edges for events
  const centerX = colRect.left + colRect.width / 2
  const leftX = colRect.left + 10
  const rightX = colRect.right - 10
  const centerY = slotRect.top + slotRect.height / 2

  const hasEventInCell = [
    document.elementsFromPoint(centerX, centerY),
    document.elementsFromPoint(leftX, centerY),
    document.elementsFromPoint(rightX, centerY),
  ].some((elements) => elements.some((el) => el.classList.contains('fc-event')))

  if (hasEventAtCursor || hasEventInCell) {
    // Don't show hover effect if there's an event in this cell
    hoverOverlayVisible.value = false
    return
  }

  // Check if we're hovering over an off-hours cell
  // Off-hours cells have .fc-non-business class overlay
  const isNonBusiness = eventsAtPosition.some((el) => el.classList.contains('fc-non-business'))
  isHoverInOffHours.value = isNonBusiness

  const calendarContainer = document.querySelector('.calendar-container')

  if (calendarContainer) {
    const containerRect = calendarContainer.getBoundingClientRect()

    // Calculate the intersection of the row and column (this is our cell!)
    const cellTop = slotRect.top - containerRect.top
    const cellLeft = colRect.left - containerRect.left
    const cellWidth = colRect.width
    const cellHeight = slotRect.height

    // Update overlay position and size
    hoverOverlayStyle.value = {
      top: `${cellTop}px`,
      left: `${cellLeft}px`,
      width: `${cellWidth}px`,
      height: `${cellHeight}px`,
    }
    hoverOverlayVisible.value = true
  } else {
    hoverOverlayVisible.value = false
  }
}

function handleCalendarMouseLeave() {
  hoverOverlayVisible.value = false
}

// Drag-and-drop rescheduling
const {
  isDragging,
  isKeyboardRescheduleActive,
  ghostTimeRange,
  ghostDateTimePreview,
  keyboardTimeRange,
  dragState,
  handleEventDrop,
  activateKeyboardReschedule,
  handleKeyboardNavigation,
  confirmKeyboardReschedule,
  cancelKeyboardReschedule,
  cleanup: cleanupDrag,
} = useAppointmentDrag(
  computed(() => appointmentsStore.appointments),
  handleAppointmentReschedule
)

// Button refs for keyboard shortcut visual feedback
const toolbarButtonRefs = computed(() => ({
  todayButton: toolbarRef.value?.todayButtonRef,
  previousButton: toolbarRef.value?.previousButtonRef,
  nextButton: toolbarRef.value?.nextButtonRef,
  weekButton: toolbarRef.value?.weekButtonRef,
  dayButton: toolbarRef.value?.dayButtonRef,
  monthButton: toolbarRef.value?.monthButtonRef,
}))

// Keyboard shortcuts with button visual feedback
useCalendarKeyboardShortcuts({
  onToday: handleToday,
  onPrevious: handlePrev,
  onNext: handleNext,
  onChangeView: changeView,
  onCreateAppointment: createNewAppointment,
  selectedAppointment,
  buttonRefs: toolbarButtonRefs,
})

// Build calendar options with events and handlers
// Wrap in computed to make it reactive to view/date/event changes
const calendarOptions = computed(() => ({
  ...buildCalendarOptions(calendarEvents.value, handleEventClick, handleDateClick),
  eventDrop: handleEventDrop as (arg: EventDropArg) => void,
}))

/**
 * Handle appointment reschedule (from drag-and-drop or mobile modal)
 */
async function handleAppointmentReschedule(
  appointmentId: string,
  newStart: Date,
  newEnd: Date,
  hasConflict: boolean
) {
  // If has conflict, show conflict modal
  if (hasConflict && dragState.value.conflictData) {
    dragConflictData.value = {
      appointmentId,
      newStart,
      newEnd,
      conflicts: dragState.value.conflictData.conflicting_appointments as ConflictingAppointment[],
    }
    showDragConflictModal.value = true
    return
  }

  // No conflict, proceed with reschedule
  await performReschedule(appointmentId, newStart, newEnd)
}

/**
 * Perform the actual reschedule with optimistic update
 */
async function performReschedule(appointmentId: string, newStart: Date, newEnd: Date) {
  const appointment = appointmentsStore.appointments.find(
    (a: AppointmentListItem) => a.id === appointmentId
  )
  if (!appointment) return

  // Store original times for undo
  const originalStart = appointment.scheduled_start
  const originalEnd = appointment.scheduled_end

  // Optimistic update
  try {
    await appointmentsStore.updateAppointment(appointmentId, {
      scheduled_start: toISOString(newStart),
      scheduled_end: toISOString(newEnd),
    })

    // Show success toast with undo button
    undoData.value = {
      appointmentId,
      originalStart,
      originalEnd,
    }
    showUndoToast.value = true

    // Set 5-second undo timeout
    if (undoTimeout.value) {
      clearTimeout(undoTimeout.value)
    }
    undoTimeout.value = setTimeout(() => {
      showUndoToast.value = false
      undoData.value = null
    }, 5000)
  } catch (error) {
    console.error('Failed to reschedule appointment:', error)
    // TODO: Show error toast
  }
}

/**
 * Undo reschedule
 */
async function handleUndoReschedule() {
  if (!undoData.value) return

  const { appointmentId, originalStart, originalEnd } = undoData.value

  try {
    await appointmentsStore.updateAppointment(appointmentId, {
      scheduled_start: originalStart,
      scheduled_end: originalEnd,
    })

    // Clear undo state
    if (undoTimeout.value) {
      clearTimeout(undoTimeout.value)
    }
    showUndoToast.value = false
    undoData.value = null
  } catch (error) {
    console.error('Failed to undo reschedule:', error)
  }
}

/**
 * Confirm reschedule with conflict (Keep Both Appointments)
 */
async function handleConfirmConflictReschedule() {
  if (!dragConflictData.value) return

  const { appointmentId, newStart, newEnd } = dragConflictData.value

  // Store original times for undo
  const appointment = appointmentsStore.appointments.find(
    (a: AppointmentListItem) => a.id === appointmentId
  )
  if (!appointment) return

  const originalStart = appointment.scheduled_start
  const originalEnd = appointment.scheduled_end

  try {
    // Force update even with conflict by passing allowConflict: true
    await appointmentsStore.updateAppointment(
      appointmentId,
      {
        scheduled_start: toISOString(newStart),
        scheduled_end: toISOString(newEnd),
      },
      { allowConflict: true }
    )

    // Show success toast with undo button
    undoData.value = {
      appointmentId,
      originalStart,
      originalEnd,
    }
    showUndoToast.value = true

    // Set 5-second undo timeout
    if (undoTimeout.value) {
      clearTimeout(undoTimeout.value)
    }
    undoTimeout.value = setTimeout(() => {
      showUndoToast.value = false
      undoData.value = null
    }, 5000)

    // Close conflict modal and reset drag state
    showDragConflictModal.value = false
    dragConflictData.value = null
  } catch (error) {
    console.error('Failed to force reschedule appointment:', error)
    // Revert on error
    if (dragState.value.revertFn) {
      dragState.value.revertFn()
    }
    showDragConflictModal.value = false
    dragConflictData.value = null
  }
}

/**
 * Cancel conflict reschedule (snap back to original position)
 */
function handleCancelConflictReschedule() {
  // Call revert function to snap appointment back to original position
  if (dragState.value.revertFn) {
    dragState.value.revertFn()
  }

  // Close the modal and clear drag state
  showDragConflictModal.value = false
  dragConflictData.value = null
}

/**
 * Handle mobile reschedule
 */
async function handleMobileReschedule(data: { newStart: Date; newEnd: Date }) {
  if (!mobileRescheduleAppointment.value) return

  await performReschedule(
    mobileRescheduleAppointment.value.id,
    data.newStart,
    data.newEnd
  )

  showMobileRescheduleModal.value = false
  mobileRescheduleAppointment.value = null
}

/**
 * Helper function to check if appointment is within date range
 */
function isAppointmentInRange(
  appointment: AppointmentListItem,
  start: Date,
  end: Date
): boolean {
  const aptDate = new Date(appointment.scheduled_start)
  return aptDate >= start && aptDate <= end
}

/**
 * Appointment summary filtered by visible date range
 * Shows appointment count for currently visible calendar period (week/day/month)
 *
 * Uses the actual FullCalendar date range from currentDateRange instead of recalculating,
 * ensuring perfect alignment with what's visually displayed.
 */
const appointmentSummary = computed(() => {
  const appointments = appointmentsStore.appointments

  if (appointments.length === 0) {
    return null
  }

  // Use actual FullCalendar date range for filtering
  const visibleAppointments = appointments.filter((apt: AppointmentListItem) =>
    isAppointmentInRange(apt, currentDateRange.value.start, currentDateRange.value.end)
  )

  const appointmentCount = visibleAppointments.length

  // Don't show metadata if no appointments in visible range
  if (appointmentCount === 0) {
    return null
  }

  const parts = []
  parts.push(`${appointmentCount} appointment${appointmentCount === 1 ? '' : 's'}`)

  // TODO: Add conflict detection logic when implemented
  // const conflicts = detectConflicts(visibleAppointments)
  // if (conflicts > 0) parts.push(`${conflicts} conflict${conflicts === 1 ? '' : 's'}`)

  // TODO (M4): Add session notes status
  // const needsNotes = visibleAppointments.filter(a => a.status === 'completed' && !a.has_notes).length
  // if (needsNotes > 0) parts.push(`${needsNotes} session${needsNotes === 1 ? '' : 's'} need notes`)

  return parts.join(' · ') || null
})

/**
 * Action handlers for appointment modal
 */
function viewClientDetails(clientId: string) {
  const appointmentData = selectedAppointment.value

  // Store in sessionStorage for reliable state passing across navigation
  if (appointmentData) {
    sessionStorage.setItem(
      'navigationContext',
      JSON.stringify({
        type: 'appointment',
        appointment: appointmentData,
        timestamp: Date.now(),
      })
    )
  }

  // Navigate to client detail (will pick up appointment from sessionStorage)
  router.push({
    name: 'client-detail',
    params: { id: clientId },
  })

  // Close modal after navigation starts
  selectedAppointment.value = null
}

/**
 * Refresh appointments after auto-save updates
 * Updates the calendar to reflect the saved changes without closing the modal
 */
async function refreshAppointments() {
  if (!selectedAppointment.value) return

  const appointmentId = selectedAppointment.value.id

  // Find the updated appointment in the store
  // The store was already updated by the auto-save composable's PUT request
  const updatedAppointment = appointmentsStore.appointments.find(
    (apt) => apt.id === appointmentId
  )

  // Update the selected appointment to show fresh data in the modal
  if (updatedAppointment) {
    selectedAppointment.value = { ...updatedAppointment }
  }

  // The calendar will automatically update because it's computed from appointmentsStore.appointments
}

function editAppointment(appointment: AppointmentListItem) {
  selectedAppointment.value = null // Close detail modal
  appointmentToEdit.value = appointment
  showEditModal.value = true
}

function startSessionNotes(_appointment: AppointmentListItem) {
  selectedAppointment.value = null // Close modal
  // TODO (M4): Open session notes drawer
}

function cancelAppointment(appointment: AppointmentListItem) {
  selectedAppointment.value = null // Close detail modal
  appointmentToCancel.value = appointment
  showCancelDialog.value = true
}

function deleteAppointment(appointment: AppointmentListItem) {
  selectedAppointment.value = null // Close detail modal
  appointmentToDelete.value = appointment
  showDeleteDialog.value = true
}

function createNewAppointment() {
  createModalPrefillData.value = null // Clear any prefill data
  showCreateModal.value = true
}

// Clear prefill data when modal closes
watch(
  () => showCreateModal.value,
  (isVisible) => {
    if (!isVisible) {
      createModalPrefillData.value = null
    }
  }
)

/**
 * Form submission handlers
 */
async function handleCreateAppointment(data: AppointmentFormData) {
  try {
    // Create appointment via store (calls API and updates local state)
    await appointmentsStore.createAppointment({
      client_id: data.client_id,
      scheduled_start: new Date(data.scheduled_start).toISOString(),
      scheduled_end: new Date(data.scheduled_end).toISOString(),
      location_type: data.location_type,
      location_details: data.location_details || null,
      notes: data.notes || null,
    })

    // Close modal on success
    showCreateModal.value = false

    // TODO (M3): Add success toast notification
  } catch (error) {
    console.error('Failed to create appointment:', error)
    // TODO (M3): Add error toast notification
    // Keep modal open on error so user can retry
  }
}

async function handleEditAppointment(data: AppointmentFormData) {
  if (!appointmentToEdit.value) return

  try {
    // Update appointment in store (calls API and updates local state)
    await appointmentsStore.updateAppointment(appointmentToEdit.value.id, data)

    // Close modal and clear edit state
    showEditModal.value = false
    appointmentToEdit.value = null

    // TODO (M3): Add success toast notification
  } catch (error) {
    console.error('Failed to update appointment:', error)
    // TODO (M3): Add error toast notification
    // Keep modal open on error so user can retry
  }
}

async function handleConfirmCancel(reason: string) {
  if (!appointmentToCancel.value) return

  const appointment = appointmentToCancel.value

  try {
    // Prepare notes with reason if provided
    const updatedNotes = reason
      ? `${appointment.notes || ''}\n\nCancellation reason: ${reason}`.trim()
      : appointment.notes

    // Update appointment status to 'cancelled' via store
    await appointmentsStore.updateAppointment(appointment.id, {
      status: 'cancelled',
      notes: updatedNotes,
    })

    // Store undo data
    undoCancelData.value = {
      appointmentId: appointment.id,
      originalStatus: appointment.status,
      originalNotes: appointment.notes || undefined,
    }

    // Show undo toast
    undoToastMessage.value = 'Appointment cancelled'
    showCancelUndoToast.value = true

    // Screen reader announcement
    await announce(
      `Appointment with ${appointment.client?.full_name || 'client'} on ${new Date(
        appointment.scheduled_start
      ).toLocaleDateString('en-US', { month: 'long', day: 'numeric' })} cancelled. Undo within 8 seconds.`
    )

    // Set timeout to hide toast
    if (undoCancelTimeout.value) {
      clearTimeout(undoCancelTimeout.value)
    }
    undoCancelTimeout.value = setTimeout(() => {
      showCancelUndoToast.value = false
      undoCancelData.value = null
    }, 8000) // 8 seconds

    // Close dialog and clear cancel state
    showCancelDialog.value = false
    appointmentToCancel.value = null
  } catch (error) {
    console.error('Failed to cancel appointment:', error)
    // TODO (M3): Add error toast notification
    // Keep dialog open on error so user can retry
  }
}

/**
 * Undo cancellation
 */
async function handleUndoCancel() {
  if (!undoCancelData.value) return

  const { appointmentId, originalStatus, originalNotes } = undoCancelData.value

  try {
    await appointmentsStore.updateAppointment(appointmentId, {
      status: originalStatus as 'scheduled' | 'completed' | 'cancelled' | 'no_show',
      notes: originalNotes,
    })

    // Clear undo state
    if (undoCancelTimeout.value) {
      clearTimeout(undoCancelTimeout.value)
    }
    showCancelUndoToast.value = false
    undoCancelData.value = null

    // Screen reader announcement
    await announce('Appointment cancellation undone')
  } catch (error) {
    console.error('Failed to undo cancellation:', error)
  }
}

/**
 * Restore cancelled appointment
 */
async function handleRestoreAppointment(appointment: AppointmentListItem) {
  try {
    // Update appointment status back to scheduled
    await appointmentsStore.updateAppointment(appointment.id, {
      status: 'scheduled',
    })

    // Close modal
    selectedAppointment.value = null

    // Screen reader announcement
    await announce('Appointment restored')
  } catch (error) {
    console.error('Failed to restore appointment:', error)
  }
}

/**
 * Confirm and perform appointment deletion
 */
async function handleConfirmDelete() {
  if (!appointmentToDelete.value) return

  const appointment = appointmentToDelete.value

  try {
    // Permanently delete appointment via store
    await appointmentsStore.deleteAppointment(appointment.id)

    // Screen reader announcement
    await announce(
      `Appointment with ${appointment.client?.full_name || 'client'} on ${new Date(
        appointment.scheduled_start
      ).toLocaleDateString('en-US', { month: 'long', day: 'numeric' })} permanently deleted.`
    )

    // Close dialog and clear delete state
    showDeleteDialog.value = false
    appointmentToDelete.value = null

    // TODO (M3): Add success toast notification
  } catch (error) {
    console.error('Failed to delete appointment:', error)
    // TODO (M3): Add error toast notification
    // Keep dialog open on error so user can retry
  }
}

// Open appointment from query param (for "return to appointment" flow)
watch(
  () => route.query.appointment,
  (appointmentId) => {
    if (appointmentId && typeof appointmentId === 'string') {
      const appointment = appointmentsStore.appointments.find(
        (a: AppointmentListItem) => a.id === appointmentId
      )
      if (appointment) {
        selectedAppointment.value = appointment
      }
      // Clear query param
      router.replace({ query: {} })
    }
  },
  { immediate: true }
)

// Keyboard shortcuts for reschedule mode
onMounted(() => {
  document.addEventListener('keydown', handleGlobalKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleGlobalKeydown)
  cleanupDrag()
  if (undoTimeout.value) {
    clearTimeout(undoTimeout.value)
  }
  if (undoCancelTimeout.value) {
    clearTimeout(undoCancelTimeout.value)
  }
})

/**
 * Global keydown handler for reschedule mode
 */
function handleGlobalKeydown(event: KeyboardEvent) {
  // Activate reschedule mode with 'R' key (when appointment is selected)
  if (event.key === 'r' || event.key === 'R') {
    if (selectedAppointment.value && !isKeyboardRescheduleActive.value) {
      event.preventDefault()
      activateKeyboardReschedule(selectedAppointment.value.id)
      selectedAppointment.value = null // Close detail modal
      return
    }
  }

  // Handle keyboard navigation in reschedule mode
  if (isKeyboardRescheduleActive.value) {
    if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) {
      event.preventDefault()
      handleKeyboardNavigation(event.key)
    } else if (event.key === 'Enter') {
      event.preventDefault()
      confirmKeyboardReschedule()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      cancelKeyboardReschedule()
    }
  }

  // Undo with Ctrl+Z or Cmd+Z
  if ((event.ctrlKey || event.metaKey) && event.key === 'z') {
    // Prioritize cancellation undo if both are showing
    if (showCancelUndoToast.value) {
      event.preventDefault()
      handleUndoCancel()
    } else if (showUndoToast.value) {
      event.preventDefault()
      handleUndoReschedule()
    }
  }
}
</script>

<template>
  <div class="container mx-auto px-4 py-8">
    <!-- Header -->
    <PageHeader title="Calendar">
      <template #actions>
        <button
          @click="createNewAppointment"
          class="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-emerald-700 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none sm:w-auto sm:justify-start"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 4v16m8-8H4"
            />
          </svg>
          <span>New Appointment</span>
        </button>
      </template>
    </PageHeader>

    <!-- Loading State (Only show for initial load with no appointments) -->
    <CalendarLoadingState
      v-if="showLoadingSpinner && appointmentsStore.appointments.length === 0"
    />

    <!-- Error State -->
    <div
      v-else-if="appointmentsStore.error"
      class="rounded-lg border border-red-200 bg-red-50 p-4 text-red-800"
    >
      <p class="font-semibold">Error loading appointments</p>
      <p class="mt-1 text-sm">{{ appointmentsStore.error }}</p>
    </div>

    <!-- Calendar View -->
    <div
      v-else
      class="calendar-card-wrapper relative rounded-lg border border-gray-200 bg-white shadow-sm"
    >
      <!-- Toolbar -->
      <CalendarToolbar
        ref="toolbarRef"
        :current-view="currentView"
        :formatted-date-range="formattedDateRange"
        :appointment-summary="appointmentSummary"
        @update:view="changeView"
        @previous="handlePrev"
        @next="handleNext"
        @today="handleToday"
      />

      <!-- Calendar Content Area (Fixed Height Container) -->
      <div class="calendar-content-area">
        <!-- FullCalendar Component with Transition -->
        <div
          class="calendar-container relative p-4"
          @mousemove="handleCalendarMouseMove"
          @mouseleave="handleCalendarMouseLeave"
        >
          <!-- Hover overlay for timeGrid individual cells -->
          <!-- z-[3] sits above background layers but below events (which are z-[4] and higher) -->
          <div
            v-if="hoverOverlayVisible"
            :class="[
              'cell-hover-overlay pointer-events-none absolute z-[3] ring-1 ring-inset ring-gray-200 transition-all duration-75',
              isHoverInOffHours ? 'bg-white' : 'bg-gray-50',
            ]"
            :style="hoverOverlayStyle"
          ></div>

          <Transition name="calendar-fade" mode="out-in">
            <FullCalendar
              ref="calendarRef"
              :key="`${currentView}-${currentDate.toISOString()}`"
              :options="calendarOptions"
            />
          </Transition>
        </div>
      </div>
    </div>

    <!-- Appointment Detail Modal -->
    <AppointmentDetailsModal
      :appointment="selectedAppointment"
      :visible="!!selectedAppointment"
      @update:visible="selectedAppointment = null"
      @edit="editAppointment"
      @start-session-notes="startSessionNotes"
      @cancel="cancelAppointment"
      @delete="deleteAppointment"
      @restore="handleRestoreAppointment"
      @view-client="viewClientDetails"
      @refresh="refreshAppointments"
    />

    <!-- Create Appointment Modal -->
    <AppointmentFormModal
      :visible="showCreateModal"
      mode="create"
      :prefill-date-time="createModalPrefillData"
      @update:visible="showCreateModal = $event"
      @submit="handleCreateAppointment"
    />

    <!-- Edit Appointment Modal -->
    <AppointmentFormModal
      :visible="showEditModal"
      :appointment="appointmentToEdit"
      mode="edit"
      @update:visible="showEditModal = $event"
      @submit="handleEditAppointment"
    />

    <!-- Cancel Appointment Dialog -->
    <CancelAppointmentDialog
      :visible="showCancelDialog"
      :appointment="appointmentToCancel"
      @update:visible="showCancelDialog = $event"
      @confirm="handleConfirmCancel"
    />

    <!-- Delete Appointment Dialog -->
    <DeleteAppointmentDialog
      :visible="showDeleteDialog"
      :appointment="appointmentToDelete"
      @update:visible="showDeleteDialog = $event"
      @confirm="handleConfirmDelete"
    />

    <!-- Drag Conflict Modal -->
    <DragConflictModal
      :visible="showDragConflictModal"
      :conflicts="dragConflictData?.conflicts || []"
      :new-time-range="
        dragConflictData
          ? { start: dragConflictData.newStart, end: dragConflictData.newEnd }
          : null
      "
      :position="dragState.ghostPosition"
      @confirm="handleConfirmConflictReschedule"
      @cancel="handleCancelConflictReschedule"
      @update:visible="showDragConflictModal = $event"
    />

    <!-- Mobile Reschedule Modal -->
    <MobileRescheduleModal
      :visible="showMobileRescheduleModal"
      :appointment="mobileRescheduleAppointment"
      @update:visible="showMobileRescheduleModal = $event"
      @reschedule="handleMobileReschedule"
    />

    <!-- Screen Reader Announcements -->
    <div role="status" aria-live="polite" aria-atomic="true" class="sr-only">
      {{ screenReaderAnnouncement }}
    </div>

    <!-- Reschedule Undo Toast -->
    <Transition name="toast-slide">
      <div
        v-if="showUndoToast"
        class="fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 items-center gap-3 rounded-lg bg-gray-900 px-4 py-3 text-white shadow-2xl"
        role="status"
        aria-live="polite"
      >
        <svg class="h-5 w-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M5 13l4 4L19 7"
          />
        </svg>
        <span class="text-sm font-medium">Appointment rescheduled</span>
        <button
          type="button"
          class="ml-2 rounded-md bg-white/10 px-3 py-1.5 text-sm font-medium transition-colors hover:bg-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900"
          @click="handleUndoReschedule"
        >
          Undo
        </button>
        <button
          type="button"
          class="ml-1 rounded-lg p-1 transition-colors hover:bg-white/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
          @click="showUndoToast = false"
          aria-label="Dismiss"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>
      </div>
    </Transition>

    <!-- Cancellation Undo Toast -->
    <UndoToast
      :show="showCancelUndoToast"
      :message="undoToastMessage"
      @undo="handleUndoCancel"
      @close="showCancelUndoToast = false"
    />

    <!-- Keyboard Reschedule Mode Indicator -->
    <Transition name="fade">
      <div
        v-if="isKeyboardRescheduleActive"
        class="fixed bottom-6 right-6 z-50 rounded-lg bg-blue-600 px-4 py-3 text-white shadow-2xl"
        role="status"
        aria-live="polite"
      >
        <div class="flex items-start gap-3">
          <svg class="h-5 w-5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 6v6m0 0v6m0-6h6m-6 0H6"
            />
          </svg>
          <div>
            <p class="text-sm font-semibold">Reschedule Mode</p>
            <p class="mt-1 text-xs opacity-90">{{ keyboardTimeRange }}</p>
            <p class="mt-2 text-xs opacity-75">
              <kbd class="rounded bg-white/20 px-1 py-0.5">↑↓</kbd> 15 min •
              <kbd class="rounded bg-white/20 px-1 py-0.5">←→</kbd> 1 day •
              <kbd class="rounded bg-white/20 px-1 py-0.5">Enter</kbd> confirm •
              <kbd class="rounded bg-white/20 px-1 py-0.5">Esc</kbd> cancel
            </p>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Drag Ghost Element -->
    <Transition name="ghost-fade">
      <div
        v-if="isDragging && dragState.ghostPosition"
        class="pointer-events-none fixed z-50 animate-ghost-float"
        :style="{
          left: `${dragState.ghostPosition.x + 10}px`,
          top: `${dragState.ghostPosition.y + 10}px`,
        }"
      >
        <div
          class="rotate-2 rounded-lg border-2 border-blue-400 bg-white px-4 py-3 opacity-95 shadow-2xl ring-2 ring-blue-400/20"
        >
          <div class="flex items-center gap-2">
            <svg
              class="h-5 w-5 text-blue-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <span class="text-sm font-semibold text-gray-900">{{ ghostTimeRange }}</span>
          </div>
          <p class="mt-1 text-xs text-gray-600">{{ ghostDateTimePreview }}</p>
          <div
            v-if="dragState.hasConflict"
            class="mt-2 flex items-center gap-1 text-xs font-medium text-amber-600"
          >
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            Conflict detected
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style>
/* Calendar Transition Animations */
.calendar-fade-enter-active,
.calendar-fade-leave-active {
  transition: opacity 150ms ease-in-out;
}

.calendar-fade-enter-from {
  opacity: 0;
}

.calendar-fade-leave-to {
  opacity: 0;
}

/* Respect user's motion preferences for accessibility */
@media (prefers-reduced-motion: reduce) {
  .calendar-fade-enter-active,
  .calendar-fade-leave-active {
    transition: none;
  }
}

/**
 * Responsive Height System for Calendar Views
 *
 * Architecture:
 * 1. calendar-content-area: Viewport-based height for responsive sizing
 * 2. View-specific height strategies applied via VIEW_SPECIFIC_OPTIONS:
 *    - Week/Day views: height: '100%' fills container
 *    - Month view: height: 'auto' with spacious date cells
 *
 * This ensures consistent visual experience across views with smooth transitions.
 */

/* Calendar content container - responsive viewport-based height */
.calendar-content-area {
  position: relative;
  min-height: 700px; /* Comfortable minimum for month view */
  height: calc(100vh - 280px); /* Full viewport minus header/toolbar/padding */
  overflow: visible; /* Allow natural page scroll */
}

/* Month view: Ensure spacious date cells for better appointment visibility */
:deep(.fc-dayGridMonth-view) {
  min-height: 650px; /* Prevent over-compression on small screens */
}

:deep(.fc-daygrid-day-frame) {
  min-height: 120px; /* Larger cells = more room for appointment details */
}

/* Calendar container - must have height for child's height: 100% to work */
.calendar-container {
  position: relative;
  z-index: 1;
  height: 100%; /* Allow FullCalendar's height: 100% to reference this */
}

/* FullCalendar custom styling to match PazPaz design */
:root {
  --fc-border-color: #e5e7eb;
  --fc-button-bg-color: #3b82f6;
  --fc-button-border-color: #3b82f6;
  --fc-button-hover-bg-color: #2563eb;
  --fc-button-hover-border-color: #2563eb;
  --fc-button-active-bg-color: #1d4ed8;
  --fc-button-active-border-color: #1d4ed8;
  --fc-today-bg-color: #eff6ff;
}

.fc {
  font-family: inherit;
}

.fc-theme-standard td,
.fc-theme-standard th {
  border-color: #e5e7eb;
}

.fc-scrollgrid {
  border-color: #e5e7eb !important;
}

.fc-col-header-cell {
  background-color: #f9fafb;
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.75rem;
  letter-spacing: 0.05em;
  color: #6b7280;
}

/* PHASE 1: Increased slot height for better appointment readability */
.fc-timegrid-slot {
  height: 4.5rem; /* 72px per hour - allows 3 lines of text in appointments (was 3rem/48px) */
}

/* Business hours background (8 AM - 6 PM) */
.fc-non-business {
  background-color: #fafafa; /* Light gray for early/late hours (6-8 AM, 6-10 PM) */
}

/* Off-hours hover effect - reverse contrast for visibility */
/* Note: .cell-hover-overlay is positioned absolutely in .calendar-container,
   not inside .fc-non-business, so we need to detect off-hours via JavaScript */

/* PHASE 2: Improved time labels styling */
.fc-timegrid-slot-label {
  color: #374151; /* gray-700 - stronger contrast than default gray-500 */
  font-size: 0.875rem;
  font-weight: 500; /* Medium weight for better scannability */
  font-variant-numeric: tabular-nums; /* Align digits vertically */
  vertical-align: top;
  padding-top: 0.25rem;
}

.fc-event {
  border-radius: 0.375rem;
  padding: 4px 6px; /* Increased from 2px 4px for better spacing */
  font-size: 0.875rem;
  line-height: 1.3; /* Tighter line height for multi-line content */
  cursor: pointer;
  transition: opacity 0.2s;
}

.fc-event:hover {
  opacity: 0.9;
}

.fc-event-title {
  font-weight: 500;
}

.fc-daygrid-event {
  white-space: normal;
}

/* PHASE 2: Current time indicator - emerald to match PazPaz brand */
.fc-timegrid-now-indicator-line {
  border-color: #10b981; /* emerald-500 */
  border-width: 2px;
  opacity: 0.7;
}

.fc-timegrid-now-indicator-arrow {
  border-top-color: #10b981;
  border-bottom-color: #10b981;
  border-width: 6px;
}

/* PHASE 2: Responsive adjustments */

/* Desktop: Full height strategy */
@media (min-width: 1024px) {
  .calendar-content-area {
    height: calc(100vh - 280px);
    min-height: 700px;
  }

  :deep(.fc-daygrid-day-frame) {
    min-height: 120px;
  }
}

/* Tablet: Slightly reduced sizing (641px - 1023px) */
@media (min-width: 641px) and (max-width: 1023px) {
  .calendar-content-area {
    height: calc(100vh - 240px);
    min-height: 600px;
  }

  :deep(.fc-daygrid-day-frame) {
    min-height: 100px;
  }

  .fc-timegrid-slot {
    height: 4rem; /* 64px on tablet - balanced readability */
  }
}

/* Mobile: Compact sizing (≤640px) */
@media (max-width: 640px) {
  .calendar-content-area {
    height: calc(100vh - 200px);
    min-height: 500px;
  }

  :deep(.fc-daygrid-day-frame) {
    min-height: 80px;
  }

  .fc-header-toolbar {
    flex-direction: column;
    gap: 0.5rem;
  }

  .fc-toolbar-chunk {
    width: 100%;
    display: flex;
    justify-content: center;
  }

  /* Reduce slot height on mobile for better viewport usage */
  .fc-timegrid-slot {
    height: 3.5rem; /* 56px on mobile - still readable */
  }

  .fc-timegrid-slot-label {
    font-size: 0.75rem; /* 12px on mobile */
  }

  .fc-event {
    padding: 2px 4px; /* Tighter padding on mobile */
    font-size: 0.8125rem; /* 13px */
  }
}

/* Conflict Detection Visual Indicators */

/* Striped pattern and border for conflicting appointments */
.fc-event.has-conflict {
  border: 2px solid #f59e0b !important; /* amber-500 */
  background-image: repeating-linear-gradient(
    45deg,
    transparent,
    transparent 10px,
    rgba(251, 191, 36, 0.15) 10px,
    rgba(251, 191, 36, 0.15) 20px
  ) !important;
  position: relative;
}

/* Warning icon badge in top-right corner */
.fc-event.has-conflict::after {
  content: '⚠️';
  position: absolute;
  top: 4px;
  right: 4px;
  width: 18px;
  height: 18px;
  background: white;
  border: 1.5px solid #f59e0b;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  z-index: 10;
  line-height: 1;
  pointer-events: none;
}

/* Ensure conflict indicators work in month view */
.fc-daygrid-event.has-conflict::after {
  top: 2px;
  right: 2px;
  width: 14px;
  height: 14px;
  font-size: 8px;
}

/* Hover state for conflicting appointments */
.fc-event.has-conflict:hover {
  opacity: 1;
  border-color: #d97706; /* amber-600 for stronger visual on hover */
}

/* Drag-and-Drop Visual States */

/* Event hover state - indicate draggable */
.fc-event:not(.fc-event-past) {
  cursor: grab;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.fc-event:not(.fc-event-past):hover {
  transform: scale(1.02);
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
}

/* Event being dragged - placeholder state */
.fc-event.fc-event-dragging {
  opacity: 0.4;
  cursor: grabbing;
}

/* Valid drop zone - pulse effect */
.fc-timegrid-col:hover {
  animation: pulse-border 1.5s ease-in-out infinite;
}

/* Toast slide-up transition */
.toast-slide-enter-active,
.toast-slide-leave-active {
  transition: all 0.3s ease;
}

.toast-slide-enter-from {
  transform: translate(-50%, 100px);
  opacity: 0;
}

.toast-slide-leave-to {
  transform: translate(-50%, 20px);
  opacity: 0;
}

/* Fade transition for indicators */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Ghost element fade transition */
.ghost-fade-enter-active,
.ghost-fade-leave-active {
  transition: opacity 0.15s ease;
}

.ghost-fade-enter-from,
.ghost-fade-leave-to {
  opacity: 0;
}

/* Keyboard reschedule mode - highlight selected appointment */
.fc-event.keyboard-reschedule-active {
  box-shadow: 0 0 0 3px rgb(59 130 246 / 0.5);
  animation: pulse-border 1.5s ease-in-out infinite;
}

/* Respect reduced motion preference for all new animations */
@media (prefers-reduced-motion: reduce) {
  .fc-event:not(.fc-event-past):hover {
    transform: none;
  }

  .fc-timegrid-col:hover {
    animation: none;
  }

  .toast-slide-enter-active,
  .toast-slide-leave-active,
  .fade-enter-active,
  .fade-leave-active,
  .ghost-fade-enter-active,
  .ghost-fade-leave-active {
    transition: none;
  }

  .fc-event.keyboard-reschedule-active {
    animation: none;
  }
}

/* Cancelled appointment visual treatment */
.fc-event.is-cancelled {
  opacity: 0.5;
  filter: grayscale(40%);
  transition: opacity 0.2s ease, filter 0.2s ease;
}

.fc-event.is-cancelled .fc-event-title {
  text-decoration: line-through;
  text-decoration-color: currentColor;
  text-decoration-thickness: 1.5px;
}

.fc-event.is-cancelled:hover {
  opacity: 0.75;
  cursor: pointer;
}

/* Reduced motion support for cancelled appointments */
@media (prefers-reduced-motion: reduce) {
  .fc-event.is-cancelled {
    transition: none !important;
  }

  .undo-toast-progress {
    transition: none !important;
  }
}

/* Screen reader only class */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}

/* Double-click to create - Cursor affordance */

/* Week/Day view timeslots - cell cursor for clickability */
:deep(.fc-timegrid-body) {
  cursor: cell;
}

/* Month view day cells - cell cursor and hover background */
:deep(.fc-daygrid-day) {
  cursor: cell;
  transition: background-color 150ms ease, box-shadow 150ms ease;
}

:deep(.fc-daygrid-day:hover) {
  background-color: rgb(249 250 251); /* gray-50 */
  box-shadow: inset 0 0 0 1px rgb(229 231 235); /* gray-200 subtle border */
}

/* Don't show hover on days with events already (less visual noise) */
:deep(.fc-daygrid-day:has(.fc-event):hover) {
  background-color: transparent;
}

/* Respect reduced motion for hover transitions */
@media (prefers-reduced-motion: reduce) {
  .cell-hover-overlay {
    transition: none !important;
  }

  :deep(.fc-daygrid-day) {
    transition: none;
  }
}
</style>
