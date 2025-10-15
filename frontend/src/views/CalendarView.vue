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
import { useToast } from '@/composables/useToast'
import { toISOString } from '@/utils/dragHelpers'
import type { ConflictingAppointment } from '@/api/client'
import type { AppointmentStatus } from '@/types/calendar'
import apiClient from '@/api/client'
import PageHeader from '@/components/common/PageHeader.vue'
import CalendarToolbar from '@/components/calendar/CalendarToolbar.vue'
import AppointmentDetailsModal from '@/components/calendar/AppointmentDetailsModal.vue'
import AppointmentFormModal from '@/components/calendar/AppointmentFormModal.vue'
import CancelAppointmentDialog from '@/components/calendar/CancelAppointmentDialog.vue'
import CalendarLoadingState from '@/components/calendar/CalendarLoadingState.vue'
import DragConflictModal from '@/components/calendar/DragConflictModal.vue'
import MobileRescheduleModal from '@/components/calendar/MobileRescheduleModal.vue'
import DeleteAppointmentModal from '@/components/appointments/DeleteAppointmentModal.vue'
import MobileActionToolbar from '@/components/calendar/MobileActionToolbar.vue'
import IconWarning from '@/components/icons/IconWarning.vue'
import IconClock from '@/components/icons/IconClock.vue'
import { format } from 'date-fns'

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

const showCreateModal = ref(false)
const showEditModal = ref(false)
const showCancelDialog = ref(false)
const showDeleteModal = ref(false)
const appointmentToEdit = ref<AppointmentListItem | null>(null)
const appointmentToCancel = ref<AppointmentListItem | null>(null)
const appointmentToDelete = ref<AppointmentListItem | null>(null)

const createModalPrefillData = ref<{ start: Date; end: Date } | null>(null)

const showDragConflictModal = ref(false)
const showMobileRescheduleModal = ref(false)
const dragConflictData = ref<{
  appointmentId: string
  newStart: Date
  newEnd: Date
  conflicts: ConflictingAppointment[]
} | null>(null)
const mobileRescheduleAppointment = ref<AppointmentListItem | null>(null)
const undoData = ref<{
  appointmentId: string
  originalStart: string
  originalEnd: string
} | null>(null)

const undoCancelData = ref<{
  appointmentId: string
  originalStatus: AppointmentStatus
  originalNotes?: string
} | null>(null)

const showEditSuccessBadge = ref(false)

// Mobile action toolbar state
const selectedAppointmentForActions = ref<string | null>(null)
const isMobile = computed(() => typeof window !== 'undefined' && window.innerWidth <= 640)

const { announcement: screenReaderAnnouncement, announce } = useScreenReader()
const { showSuccess, showAppointmentSuccess, showSuccessWithUndo, showError } =
  useToast()

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

const { selectedAppointment, calendarEvents, handleEventClick: composableHandleEventClick, sessionStatusMap } =
  useCalendarEvents()

// Wrap handleEventClick to capture times before modal opens
function handleEventClick(clickInfo: any) {
  // Mobile behavior: tap-to-select with floating toolbar
  if (isMobile.value) {
    const appointmentId = clickInfo.event.id

    // If this appointment is already selected, open detail modal (second tap)
    if (selectedAppointmentForActions.value === appointmentId) {
      selectedAppointmentForActions.value = null // Clear selection
      composableHandleEventClick(clickInfo) // Open modal

      // Capture times for modal
      if (selectedAppointment.value) {
        previousAppointmentTimes.value.set(selectedAppointment.value.id, {
          start: selectedAppointment.value.scheduled_start,
          end: selectedAppointment.value.scheduled_end
        })
      }
    } else {
      // First tap: select appointment and show toolbar
      // Immediately add visual class to prevent flash
      const eventEl = clickInfo.el
      if (eventEl) {
        eventEl.classList.add('is-selected-for-action')
      }

      selectedAppointmentForActions.value = appointmentId
    }
    return
  }

  // Desktop behavior: open modal immediately
  composableHandleEventClick(clickInfo)

  // Then, if an appointment was selected, capture its current times IMMEDIATELY
  // This happens BEFORE any auto-save or reactive updates
  if (selectedAppointment.value) {
    previousAppointmentTimes.value.set(selectedAppointment.value.id, {
      start: selectedAppointment.value.scheduled_start,
      end: selectedAppointment.value.scheduled_end
    })
  }
}

const { showLoadingSpinner } = useCalendarLoading()

/**
 * Apply correct height to calendar event
 * FullCalendar v6 bug: ignores end time and defaults to 1-hour events
 */
function applyEventHeight(eventEl: HTMLElement, start: Date, end: Date) {
  const durationMinutes = (end.getTime() - start.getTime()) / (1000 * 60)
  const heightPx = (durationMinutes / 60) * 48 // FullCalendar uses 48px per hour

  const harness = eventEl.closest('.fc-timegrid-event-harness')

  if (!harness) return // Early exit if not a time-grid event

  const harnessEl = harness as HTMLElement

  // P3: Performance guard - Skip if height is already correct (within 1px tolerance)
  const currentHeight = harnessEl.getBoundingClientRect().height
  if (Math.abs(currentHeight - heightPx) < 1) {
    return // Height is already correct, skip expensive DOM updates
  }

  const currentStyle = harnessEl.getAttribute('style') || ''

  // Try to get computed style instead
  const computedStyle = window.getComputedStyle(harnessEl)
  const computedTop = computedStyle.top

  // Try to extract top position from either inline style or computed style
  let topPx: number | null = null

  // First try inline style with inset
  const insetMatch = currentStyle.match(/inset:\s*([0-9.]+)px/)
  if (insetMatch && insetMatch[1]) {
    topPx = parseFloat(insetMatch[1])
  }

  // If no inset, try computed top
  if (topPx === null && computedTop && computedTop !== 'auto') {
    topPx = parseFloat(computedTop)
  }

  if (topPx !== null && !isNaN(topPx)) {
    const bottomPx = -(topPx + heightPx)

    // Set correct height on harness container
    harnessEl.style.setProperty('top', `${topPx}px`, 'important')
    harnessEl.style.setProperty('bottom', `${bottomPx}px`, 'important')
    harnessEl.style.setProperty('left', '0%', 'important')
    harnessEl.style.setProperty('right', '0%', 'important')
    harnessEl.style.setProperty('height', `${heightPx}px`, 'important')
    harnessEl.style.setProperty('visibility', 'visible', 'important')

    // CRITICAL: Make event element fill the harness container
    eventEl.style.setProperty('height', '100%', 'important')
    eventEl.style.setProperty('min-height', `${heightPx}px`, 'important')
  }
}

/**
 * Update a specific event's height when its duration changes
 * Called when refreshAppointments() detects a duration change
 *
 * Strategy: FullCalendar's calendarEvents computed property already has the updated times,
 * but the DOM hasn't been updated with the correct height due to FullCalendar v6 bug.
 * We directly find and update the DOM element's height.
 *
 * P2: Includes retry logic with exponential backoff for slower devices
 */
function updateEventHeight(appointmentId: string, retryCount = 0) {
  // Find the appointment in the store to get latest times
  const appointment = appointmentsStore.appointments.find(a => a.id === appointmentId)
  if (!appointment) return

  const newStart = new Date(appointment.scheduled_start)
  const newEnd = new Date(appointment.scheduled_end)

  // Find the event DOM element and apply height fix directly
  // Use multiple animation frames to ensure FullCalendar has finished its render cycle
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const eventEl = document.querySelector(`[data-event-id="${appointmentId}"]`) as HTMLElement
        if (eventEl) {
          applyEventHeight(eventEl, newStart, newEnd)
        } else if (retryCount < 3) {
          // P2: Retry with exponential backoff if DOM element not found
          // This ensures height updates don't silently fail on slower devices
          const backoffMs = 100 * (retryCount + 1) // 100ms, 200ms, 300ms
          setTimeout(() => updateEventHeight(appointmentId, retryCount + 1), backoffMs)
        }
      })
    })
  })
}

/**
 * Open create modal with pre-filled date/time from calendar double-click
 */
function openCreateModalWithPrefill(prefillData: { start: Date; end: Date }) {
  createModalPrefillData.value = prefillData
  showCreateModal.value = true

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

const { handleDateClick } = useCalendarCreation(openCreateModalWithPrefill)

const hoverOverlayVisible = ref(false)
const hoverOverlayStyle = ref({ top: '0px', left: '0px', width: '0px', height: '0px' })
const isHoverInOffHours = ref(false)

function handleCalendarMouseMove(event: MouseEvent) {
  if (!currentView.value.includes('timeGrid')) {
    hoverOverlayVisible.value = false
    return
  }

  const target = event.target as HTMLElement

  let slotLane: HTMLElement | null = target.closest('.fc-timegrid-slot-lane')

  if (!slotLane) {
    const allElements = document.elementsFromPoint(event.clientX, event.clientY)
    const found = allElements.find((el) =>
      el.classList.contains('fc-timegrid-slot-lane')
    )
    slotLane = found instanceof HTMLElement ? found : null
  }

  if (!slotLane) {
    hoverOverlayVisible.value = false
    return
  }

  const dayColumns = document.querySelectorAll('.fc-timegrid-col')

  if (dayColumns.length === 0) {
    hoverOverlayVisible.value = false
    return
  }

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

  const slotRect = slotLane.getBoundingClientRect()
  const colRect = targetColumn.getBoundingClientRect()

  const eventsAtPosition = document.elementsFromPoint(event.clientX, event.clientY)
  const hasEventAtCursor = eventsAtPosition.some((el) =>
    el.classList.contains('fc-event')
  )

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
    hoverOverlayVisible.value = false
    return
  }

  const isNonBusiness = eventsAtPosition.some((el) =>
    el.classList.contains('fc-non-business')
  )
  isHoverInOffHours.value = isNonBusiness

  const calendarContainer = document.querySelector('.calendar-container')

  if (calendarContainer) {
    const containerRect = calendarContainer.getBoundingClientRect()

    const cellTop = slotRect.top - containerRect.top
    const cellLeft = colRect.left - containerRect.left
    const cellWidth = colRect.width
    const cellHeight = slotRect.height

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

const toolbarButtonRefs = computed(() => ({
  todayButton: toolbarRef.value?.todayButtonRef,
  previousButton: toolbarRef.value?.previousButtonRef,
  nextButton: toolbarRef.value?.nextButtonRef,
  weekButton: toolbarRef.value?.weekButtonRef,
  dayButton: toolbarRef.value?.dayButtonRef,
  monthButton: toolbarRef.value?.monthButtonRef,
}))

useCalendarKeyboardShortcuts({
  onToday: handleToday,
  onPrevious: handlePrev,
  onNext: handleNext,
  onChangeView: changeView,
  onCreateAppointment: createNewAppointment,
  selectedAppointment,
  buttonRefs: toolbarButtonRefs,
})


/**
 * Quick complete action handler
 * Marks a past scheduled appointment as completed
 */
async function handleQuickComplete(appointmentId: string) {
  const appointment = appointmentsStore.appointments.find(
    (a: AppointmentListItem) => a.id === appointmentId
  )
  if (!appointment) return

  try {
    await appointmentsStore.updateAppointmentStatus(appointmentId, 'completed')

    // Show success toast with client name
    const clientName = appointment.client?.first_name || 'Appointment'
    showSuccess(`${clientName} completed`, {
      toastId: `completion-${appointmentId}-${Date.now()}`,
    })

    // Screen reader announcement
    announce(`Appointment marked as completed`)
  } catch (error) {
    console.error('Failed to mark appointment as completed:', error)
    showError('Failed to mark appointment as completed')
  }
}

/**
 * Handle complete from mobile toolbar
 */
function handleMobileComplete() {
  if (!selectedAppointmentForActions.value) return
  handleQuickComplete(selectedAppointmentForActions.value)
  selectedAppointmentForActions.value = null
}

/**
 * Handle delete from mobile toolbar
 */
function handleMobileDelete() {
  if (!selectedAppointmentForActions.value) return
  handleQuickDelete(selectedAppointmentForActions.value)
  selectedAppointmentForActions.value = null
}

/**
 * Close mobile toolbar
 */
function handleCloseMobileToolbar() {
  selectedAppointmentForActions.value = null
}

/**
 * Quick delete action handler
 * Opens delete modal for confirmation
 */
function handleQuickDelete(appointmentId: string) {
  const appointment = appointmentsStore.appointments.find(
    (a: AppointmentListItem) => a.id === appointmentId
  )
  if (!appointment) return

  // Open delete modal with the appointment
  appointmentToDelete.value = appointment
  showDeleteModal.value = true
}

/**
 * Handle delete confirmation from modal
 */
async function handleDeleteConfirm(payload: {
  reason?: string
  session_note_action?: 'delete' | 'keep'
  deletion_reason?: string
}) {
  if (!appointmentToDelete.value) return

  try {
    await appointmentsStore.deleteAppointment(appointmentToDelete.value.id, payload)
    showDeleteModal.value = false

    // Show appropriate success message
    const message =
      payload.session_note_action === 'delete'
        ? 'Appointment and session note deleted'
        : payload.session_note_action === 'keep'
          ? 'Appointment deleted (session note kept)'
          : 'Appointment deleted'

    showSuccess(message)

    // Close the modal and clear state
    appointmentToDelete.value = null
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : 'Failed to delete appointment'
    showError(errorMessage)
  }
}

/**
 * Handle delete cancellation
 */
function handleDeleteCancel() {
  showDeleteModal.value = false
  appointmentToDelete.value = null
}

const calendarOptions = computed(() => ({
  ...buildCalendarOptions(calendarEvents.value, handleEventClick, handleDateClick),
  eventDrop: handleEventDrop as (arg: EventDropArg) => void,

  // Use eventContent to declaratively render event content with quick action buttons
  // This ensures buttons persist across all FullCalendar renders (initial, updates, etc.)
  eventContent: (arg: any) => {
    const event = arg.event
    const now = new Date()
    const canComplete =
      event.extendedProps.status === 'scheduled' &&
      event.end &&
      new Date(event.end) < now

    // Create wrapper with relative positioning for absolute buttons
    const wrapper = document.createElement('div')
    wrapper.className = 'fc-event-main-frame relative group h-full'
    wrapper.style.position = 'relative'

    // Title container
    const titleContainer = document.createElement('div')
    titleContainer.className = 'fc-event-title-container'

    const title = document.createElement('div')
    title.className = 'fc-event-title fc-sticky'
    title.textContent = event.title || 'Untitled'
    titleContainer.appendChild(title)
    wrapper.appendChild(titleContainer)

    // Quick action buttons container (desktop only - hidden on mobile ≤640px)
    const actionsContainer = document.createElement('div')
    actionsContainer.className =
      'calendar-quick-actions absolute top-1 right-1 flex gap-1 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity duration-150 z-10'

    // Complete button (only for past scheduled appointments)
    if (canComplete) {
      const completeBtn = document.createElement('button')
      completeBtn.className =
        'p-1 rounded bg-white/90 hover:bg-emerald-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 shadow-sm'
      completeBtn.title = 'Mark completed (C)'
      completeBtn.setAttribute('aria-label', 'Mark appointment as completed')
      completeBtn.innerHTML = `
        <svg class="h-3.5 w-3.5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
        </svg>
      `
      completeBtn.addEventListener('click', (e) => {
        e.stopPropagation()
        handleQuickComplete(event.id)
      })
      actionsContainer.appendChild(completeBtn)
    }

    // Delete button (always shown)
    const deleteBtn = document.createElement('button')
    deleteBtn.className =
      'p-1 rounded bg-white/90 hover:bg-red-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 shadow-sm'
    deleteBtn.title = 'Delete (Del)'
    deleteBtn.setAttribute('aria-label', 'Delete appointment')
    deleteBtn.innerHTML = `
      <svg class="h-3.5 w-3.5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
      </svg>
    `
    deleteBtn.addEventListener('click', (e) => {
      e.stopPropagation()
      handleQuickDelete(event.id)
    })
    actionsContainer.appendChild(deleteBtn)

    wrapper.appendChild(actionsContainer)

    return { domNodes: [wrapper] }
  },

  eventDidMount: (info: { event: any; el: HTMLElement }) => {
    const event = info.event
    const hasSession = event.extendedProps?.hasSession
    const isDraft = event.extendedProps?.isDraft
    const duration = event.extendedProps?.duration_minutes

    // Add data attribute so we can find this element later
    info.el.setAttribute('data-event-id', event.id)

    // Add selected state class for mobile toolbar
    if (selectedAppointmentForActions.value === event.id) {
      info.el.classList.add('is-selected-for-action')
    }

    // Apply height fix for FullCalendar v6 bug
    if (event.start && event.end) {
      applyEventHeight(info.el, event.start, event.end)
    }

    // Build tooltip text
    let tooltipText = event.title

    if (hasSession) {
      tooltipText += isDraft
        ? '\n📄 Session note: Draft'
        : '\n📄 Session note: Finalized'
    } else if (event.extendedProps?.status === 'completed') {
      tooltipText += '\n📝 No session note yet'
    }

    if (duration) {
      tooltipText += `\n⏱️ ${duration} minutes`
    }

    if (event.extendedProps?.location_type) {
      const locationEmoji: Record<string, string> = {
        clinic: '🏥',
        home: '🏠',
        online: '💻',
      }
      const emoji = locationEmoji[event.extendedProps.location_type] || '📍'
      tooltipText += `\n${emoji} ${event.extendedProps.location_type}`
    }

    info.el.title = tooltipText
  },
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
      conflicts: dragState.value.conflictData
        .conflicting_appointments as ConflictingAppointment[],
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

  // Store original times for undo (captured in closure)
  const originalStart = appointment.scheduled_start
  const originalEnd = appointment.scheduled_end

  // Get client name for toast message
  const clientName =
    appointment.client?.first_name || appointment.client?.full_name || 'Appointment'

  // Optimistic update
  try {
    await appointmentsStore.updateAppointment(appointmentId, {
      scheduled_start: toISOString(newStart),
      scheduled_end: toISOString(newEnd),
    })

    // Create a specific undo handler for this reschedule (closure captures the original times)
    const handleUndo = async () => {
      try {
        await appointmentsStore.updateAppointment(appointmentId, {
          scheduled_start: originalStart,
          scheduled_end: originalEnd,
        })

        // Clear the keyboard undo data if this was the most recent
        if (undoData.value?.appointmentId === appointmentId) {
          undoData.value = null
        }
      } catch (error) {
        console.error('Failed to undo reschedule:', error)
      }
    }

    // Store for keyboard shortcut (Ctrl+Z)
    undoData.value = {
      appointmentId,
      originalStart,
      originalEnd,
    }

    // Show toast with specific undo handler
    showSuccessWithUndo(`${clientName} rescheduled`, handleUndo)
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

  // Store original times for undo (captured in closure)
  const appointment = appointmentsStore.appointments.find(
    (a: AppointmentListItem) => a.id === appointmentId
  )
  if (!appointment) return

  const originalStart = appointment.scheduled_start
  const originalEnd = appointment.scheduled_end

  // Get client name for toast message
  const clientName =
    appointment.client?.first_name || appointment.client?.full_name || 'Appointment'

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

    // Create a specific undo handler for this reschedule (closure captures the original times)
    const handleUndo = async () => {
      try {
        await appointmentsStore.updateAppointment(appointmentId, {
          scheduled_start: originalStart,
          scheduled_end: originalEnd,
        })

        // Clear the keyboard undo data if this was the most recent
        if (undoData.value?.appointmentId === appointmentId) {
          undoData.value = null
        }
      } catch (error) {
        console.error('Failed to undo reschedule:', error)
      }
    }

    // Store for keyboard shortcut (Ctrl+Z)
    undoData.value = {
      appointmentId,
      originalStart,
      originalEnd,
    }

    // Show toast with specific undo handler
    showSuccessWithUndo(`${clientName} rescheduled`, handleUndo)

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

/**
 * Handle status update from AppointmentDetailsModal
 * Updates appointment status with optimistic UI and error handling
 */
async function handleUpdateStatus(appointmentId: string, newStatus: string) {
  try {
    await appointmentsStore.updateAppointmentStatus(appointmentId, newStatus)

    // Refresh appointments to update calendar colors
    await refreshAppointments()
  } catch (error) {
    console.error('Failed to update appointment status:', error)
    const errorMessage =
      error instanceof Error ? error.message : 'Failed to update status'
    alert(`Error: ${errorMessage}`)
  }
}

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
 * Navigate to session view (from appointment modal)
 */
function viewSession(sessionId: string) {
  // Close appointment modal
  selectedAppointment.value = null

  // Navigate to session with return context
  router.push({
    path: `/sessions/${sessionId}`,
  })

  // Set history state after navigation
  window.history.replaceState(
    {
      ...window.history.state,
      from: 'appointment',
      returnTo: 'calendar',
    },
    ''
  )
}

// Track previous appointment times to detect duration changes
// Times are captured in handleEventClick when user clicks an appointment
const previousAppointmentTimes = ref<Map<string, { start: string; end: string }>>(new Map())

// P1: Watch appointments and clean up stale entries from Map to prevent memory leak
watch(
  () => appointmentsStore.appointments,
  (newAppointments) => {
    // Clean up stale entries
    const currentIds = new Set(newAppointments.map((a) => a.id))
    for (const [id] of previousAppointmentTimes.value) {
      if (!currentIds.has(id)) {
        previousAppointmentTimes.value.delete(id)
      }
    }
  }
)

/**
 * Refresh appointments after auto-save updates
 * Updates the calendar to reflect the saved changes without closing the modal
 */
async function refreshAppointments() {
  if (!selectedAppointment.value) return

  const appointmentId = selectedAppointment.value.id

  // Get previous times from our tracking map
  const prevTimes = previousAppointmentTimes.value.get(appointmentId)

  // Find the updated appointment in the store
  // The store was already updated by the auto-save composable's PUT request
  const updatedAppointment = appointmentsStore.appointments.find(
    (apt) => apt.id === appointmentId
  )

  // Update the selected appointment to show fresh data in the modal
  if (updatedAppointment) {
    // Check if duration changed by comparing with previous tracked times
    const durationChanged = prevTimes &&
      (prevTimes.start !== updatedAppointment.scheduled_start ||
       prevTimes.end !== updatedAppointment.scheduled_end)

    // Update tracked times for next comparison
    previousAppointmentTimes.value.set(appointmentId, {
      start: updatedAppointment.scheduled_start,
      end: updatedAppointment.scheduled_end
    })

    selectedAppointment.value = { ...updatedAppointment }

    // If duration changed, manually update the event height
    if (durationChanged) {
      updateEventHeight(appointmentId)
    }
  }

  // The calendar will automatically update because it's computed from appointmentsStore.appointments
}

function editAppointment(appointment: AppointmentListItem) {
  selectedAppointment.value = null // Close detail modal
  appointmentToEdit.value = appointment
  showEditModal.value = true
}

/**
 * Calculate duration in minutes between two dates
 */
function calculateDuration(start: Date, end: Date): number {
  const diffMs = end.getTime() - start.getTime()
  const diffMinutes = Math.round(diffMs / (1000 * 60))
  return Math.max(0, diffMinutes) // Ensure non-negative
}

/**
 * Start session notes for an appointment
 * Creates a draft session linked to the appointment and navigates to editor
 */
async function startSessionNotes(appointment: AppointmentListItem) {
  try {
    // If appointment is scheduled, mark as completed first
    if (appointment.status === 'scheduled') {
      await appointmentsStore.updateAppointmentStatus(appointment.id, 'completed')
      // Show toast notification for auto-completion with client name and unique ID
      const clientName = appointment.client?.first_name || 'Appointment'
      showSuccess(`${clientName} completed`, {
        toastId: `completion-${appointment.id}-${Date.now()}`,
      })
    }

    // Calculate duration from appointment times
    const durationMinutes = calculateDuration(
      new Date(appointment.scheduled_start),
      new Date(appointment.scheduled_end)
    )

    // Create new draft session linked to appointment
    const response = await apiClient.post('/sessions', {
      client_id: appointment.client_id,
      appointment_id: appointment.id,
      session_date: appointment.scheduled_start,
      duration_minutes: durationMinutes,
      is_draft: true,
      // Optional: Pre-fill Subjective with appointment notes
      subjective: appointment.notes || null,
    })

    // Immediately update session status map (optimistic update)
    // This ensures the green border appears when user returns to calendar
    sessionStatusMap.value.set(appointment.id, {
      hasSession: true,
      sessionId: response.data.id,
      isDraft: true,
    })

    // Close appointment modal
    selectedAppointment.value = null

    // Navigate to session editor with context
    // Note: Vue Router doesn't support state in route definition,
    // so we use window.history.state which is preserved by router.push
    await router.push(`/sessions/${response.data.id}`)

    // Set history state after navigation
    window.history.replaceState(
      {
        ...window.history.state,
        from: 'appointment',
        appointmentId: appointment.id,
        returnTo: 'calendar',
      },
      ''
    )
  } catch (error) {
    console.error('Failed to create session:', error)
    // TODO (M3): Show error toast notification
    // For now, log the error and keep modal open
    alert('Failed to create session note. Please try again.')
  }
}

function cancelAppointment(appointment: AppointmentListItem) {
  selectedAppointment.value = null // Close detail modal
  appointmentToCancel.value = appointment
  showCancelDialog.value = true
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
    const newAppt = await appointmentsStore.createAppointment({
      client_id: data.client_id,
      scheduled_start: new Date(data.scheduled_start).toISOString(),
      scheduled_end: new Date(data.scheduled_end).toISOString(),
      location_type: data.location_type,
      location_details: data.location_details || null,
      notes: data.notes || null,
    })

    // Close modal on success
    showCreateModal.value = false
    createModalPrefillData.value = null

    // Show success toast with rich content
    showAppointmentSuccess('Appointment created', {
      clientName: newAppt.client?.full_name || 'Unknown Client',
      datetime: format(new Date(newAppt.scheduled_start), "MMM d 'at' h:mm a"),
      actions: [
        {
          label: 'View Details',
          onClick: () => {
            const appointment = appointmentsStore.appointments.find(
              (a) => a.id === newAppt.id
            )
            if (appointment) {
              selectedAppointment.value = appointment
            }
          },
        },
      ],
    })

    // Screen reader announcement
    announce(`Appointment created for ${newAppt.client?.full_name || 'Unknown Client'}`)
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

    // Close Edit Modal
    showEditModal.value = false

    // Reopen Details Modal with updated data
    const updatedAppointment = appointmentsStore.appointments.find(
      (a) => a.id === appointmentToEdit.value!.id
    )
    if (updatedAppointment) {
      selectedAppointment.value = updatedAppointment
    }

    appointmentToEdit.value = null

    // Show edit success badge (3 seconds)
    showEditSuccessBadge.value = true
    setTimeout(() => {
      showEditSuccessBadge.value = false
    }, 3000)

    // Screen reader announcement
    announce('Appointment updated')
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

    // Show undo toast with client name
    const clientName = appointment.client?.first_name || 'Appointment'
    showSuccessWithUndo(`${clientName} cancelled`, handleUndoCancel)

    // Screen reader announcement
    await announce(
      `Appointment with ${appointment.client?.full_name || 'client'} on ${new Date(
        appointment.scheduled_start
      ).toLocaleDateString('en-US', {
        month: 'long',
        day: 'numeric',
      })} cancelled. Undo within 5 seconds.`
    )

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

// Watch for selection changes and update event classes
watch(
  () => selectedAppointmentForActions.value,
  (newId, oldId) => {
    // Remove selected class from previous appointment
    if (oldId) {
      const oldEl = document.querySelector(`[data-event-id="${oldId}"]`)
      if (oldEl) {
        oldEl.classList.remove('is-selected-for-action')
      }
    }

    // Add selected class to new appointment
    if (newId) {
      const newEl = document.querySelector(`[data-event-id="${newId}"]`)
      if (newEl) {
        newEl.classList.add('is-selected-for-action')
      }
    }
  }
)

// Keyboard shortcuts for reschedule mode
onMounted(() => {
  document.addEventListener('keydown', handleGlobalKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleGlobalKeydown)
  cleanupDrag()
  // P1: Clear Map on unmount to prevent memory leak
  previousAppointmentTimes.value.clear()
})

/**
 * Global keydown handler for reschedule mode and quick actions
 */
function handleGlobalKeydown(event: KeyboardEvent) {
  // Quick action: Complete appointment with 'C' key (when appointment is selected)
  if ((event.key === 'c' || event.key === 'C') && !event.ctrlKey && !event.metaKey) {
    if (selectedAppointment.value) {
      // Check if appointment can be completed
      const now = new Date()
      const canComplete =
        selectedAppointment.value.status === 'scheduled' &&
        new Date(selectedAppointment.value.scheduled_end) < now

      if (canComplete) {
        event.preventDefault()
        handleQuickComplete(selectedAppointment.value.id)
        selectedAppointment.value = null // Close detail modal
        return
      }
    }
  }

  // Quick action: Delete appointment with 'Delete' or 'Backspace' key (when appointment is selected)
  if (event.key === 'Delete' || event.key === 'Backspace') {
    if (selectedAppointment.value && !isKeyboardRescheduleActive.value) {
      event.preventDefault()
      handleQuickDelete(selectedAppointment.value.id)
      selectedAppointment.value = null // Close detail modal
      return
    }
  }

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
    // Prioritize cancellation undo if both undo data exists
    if (undoCancelData.value) {
      event.preventDefault()
      handleUndoCancel()
    } else if (undoData.value) {
      event.preventDefault()
      handleUndoReschedule()
    }
  }
}
</script>

<template>
  <div class="container mx-auto px-5 py-6 sm:px-6 sm:py-8">
    <!-- Header -->
    <PageHeader title="Calendar">
      <template #actions>
        <button
          @click="createNewAppointment"
          class="inline-flex min-h-[44px] w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-emerald-700 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none sm:min-h-0 sm:w-auto sm:justify-start sm:py-2"
        >
          <svg
            class="h-4 w-4 flex-shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
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
              'cell-hover-overlay pointer-events-none absolute z-[3] ring-1 ring-gray-200 transition-all duration-75 ring-inset',
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
      :show-edit-success="showEditSuccessBadge"
      :session-status="
        selectedAppointment
          ? sessionStatusMap.get(selectedAppointment.id) || null
          : null
      "
      @update:visible="selectedAppointment = null"
      @edit="editAppointment"
      @start-session-notes="startSessionNotes"
      @update-status="handleUpdateStatus"
      @cancel="cancelAppointment"
      @restore="handleRestoreAppointment"
      @view-client="viewClientDetails"
      @view-session="viewSession"
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

    <!-- Delete Appointment Modal -->
    <DeleteAppointmentModal
      :appointment="appointmentToDelete"
      :session-status="
        appointmentToDelete
          ? sessionStatusMap.get(appointmentToDelete.id) || null
          : null
      "
      :open="showDeleteModal"
      @confirm="handleDeleteConfirm"
      @cancel="handleDeleteCancel"
    />

    <!-- Mobile Action Toolbar -->
    <MobileActionToolbar
      :visible="!!selectedAppointmentForActions"
      :appointment-id="selectedAppointmentForActions"
      :can-complete="
        selectedAppointmentForActions
          ? (() => {
              const appt = appointmentsStore.appointments.find(
                (a) => a.id === selectedAppointmentForActions
              )
              if (!appt) return false
              const now = new Date()
              return (
                appt.status === 'scheduled' &&
                new Date(appt.scheduled_end) < now
              )
            })()
          : false
      "
      @complete="handleMobileComplete"
      @delete="handleMobileDelete"
      @close="handleCloseMobileToolbar"
    />

    <!-- Screen Reader Announcements -->
    <div role="status" aria-live="polite" aria-atomic="true" class="sr-only">
      {{ screenReaderAnnouncement }}
    </div>

    <!-- Keyboard Reschedule Mode Indicator (desktop only) -->
    <Transition name="fade">
      <div
        v-if="isKeyboardRescheduleActive"
        class="fixed right-6 bottom-6 z-50 hidden rounded-lg bg-blue-600 px-4 py-3 text-white shadow-2xl sm:block"
        role="status"
        aria-live="polite"
      >
        <div class="flex items-start gap-3">
          <svg
            class="h-5 w-5 shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
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
        class="animate-ghost-float pointer-events-none fixed z-50"
        :style="{
          left: `${dragState.ghostPosition.x + 10}px`,
          top: `${dragState.ghostPosition.y + 10}px`,
        }"
      >
        <div
          class="rotate-2 rounded-lg border-2 border-blue-400 bg-white px-4 py-3 opacity-95 shadow-2xl ring-2 ring-blue-400/20"
        >
          <div class="flex items-center gap-2">
            <IconClock size="md" class="text-blue-600" />
            <span class="text-sm font-semibold text-gray-900">{{
              ghostTimeRange
            }}</span>
          </div>
          <p class="mt-1 text-xs text-gray-600">{{ ghostDateTimePreview }}</p>
          <div
            v-if="dragState.hasConflict"
            class="mt-2 flex items-center gap-1 text-xs font-medium text-amber-600"
          >
            <IconWarning size="sm" />
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
/* REMOVED: Custom slot height was breaking FullCalendar's event height calculation
.fc-timegrid-slot {
  height: 4.5rem;
}
*/

/* Business hours background (8 AM - 6 PM) */
.fc-non-business {
  background-color: #fafafa; /* Light gray for early/late hours (6-8 AM, 6-10 PM) */
}

/* Off-hours hover effect - reverse contrast for visibility */
/* Note: .cell-hover-overlay is positioned absolutely in .calendar-container,
   not inside .fc-non-business, so we need to detect off-hours via JavaScript */

/* PHASE 2: Improved time labels styling - mobile-friendly */
.fc-timegrid-slot-label {
  color: #374151; /* gray-700 - stronger contrast than default gray-500 */
  font-size: 0.875rem; /* 14px on desktop */
  font-weight: 500; /* Medium weight for better scannability */
  font-variant-numeric: tabular-nums; /* Align digits vertically */
  vertical-align: top;
  padding-top: 0.25rem;
}

/* Larger time labels on mobile for better readability */
@media (max-width: 640px) {
  .fc-timegrid-slot-label {
    font-size: 0.8125rem; /* 13px on mobile - still readable but more compact */
    font-weight: 600; /* Bolder for mobile screens */
  }
}

.fc-event {
  border-radius: 0.375rem;
  padding: 6px 8px; /* Larger padding for better mobile touch */
  font-size: 0.875rem;
  line-height: 1.3; /* Tighter line height for multi-line content */
  cursor: pointer;
  transition: opacity 0.2s;
  min-height: 44px; /* Ensure minimum touch target size on mobile */
}

.fc-event:hover {
  opacity: 0.9;
}

.fc-event-title {
  font-weight: 500;
}

.fc-daygrid-event {
  white-space: normal;
  min-height: 32px; /* Month view events can be slightly smaller */
}

/* Desktop: Restore tighter spacing */
@media (min-width: 641px) {
  .fc-event {
    padding: 4px 6px;
    min-height: auto; /* Remove minimum on desktop */
  }

  .fc-daygrid-event {
    min-height: auto;
  }
}

/* PHASE 2: Current time indicator - emerald to match PazPaz brand, thicker on mobile */
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

/* Thicker current time indicator on mobile for better visibility */
@media (max-width: 640px) {
  .fc-timegrid-now-indicator-line {
    border-width: 3px;
    opacity: 0.8;
  }

  .fc-timegrid-now-indicator-arrow {
    border-width: 8px;
  }
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

  /* REMOVED: Custom slot height override
  .fc-timegrid-slot {
    height: 4rem;
  }
  */
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

  /* REMOVED: Custom slot height override
  .fc-timegrid-slot {
    height: 3.5rem;
  }
  */

  .fc-timegrid-slot-label {
    font-size: 0.75rem; /* 12px on mobile */
  }

  .fc-event {
    padding: 2px 4px; /* Tighter padding on mobile */
    font-size: 0.8125rem; /* 13px */
  }
}

/* Session Status Indicators (P0 Feature) */

/* Green left border for appointments with session notes */
:deep(.fc-event.event-with-session) {
  border-left: 3px solid #10b981 !important; /* emerald-500 green accent */
  padding-left: 4px; /* Adjust padding to accommodate thicker border */
}

/* Ensure session indicator works in month view */
:deep(.fc-daygrid-event.event-with-session) {
  border-left: 3px solid #10b981 !important;
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
  transition:
    transform 0.2s ease,
    box-shadow 0.2s ease;
}

.fc-event:not(.fc-event-past):hover {
  transform: scale(1.02);
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.1),
    0 2px 4px -1px rgba(0, 0, 0, 0.06);
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
  transition:
    opacity 0.2s ease,
    filter 0.2s ease;
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
  transition:
    background-color 150ms ease,
    box-shadow 150ms ease;
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

/* Mobile Action Toolbar - Selected Appointment State */

/* Hide desktop quick action buttons on mobile */
@media (max-width: 640px) {
  .calendar-quick-actions {
    display: none !important;
  }

  /* Prevent tap highlight flash on FullCalendar elements */
  :deep(.fc-col-header-cell),
  :deep(.fc-daygrid-day),
  :deep(.fc-timegrid-col),
  :deep(.fc-timegrid-slot-lane) {
    -webkit-tap-highlight-color: transparent;
    -webkit-touch-callout: none;
    -webkit-user-select: none;
    user-select: none;
  }

  /* Selected appointment state - blue pulsing border */
  :deep(.fc-event.is-selected-for-action) {
    box-shadow: 0 0 0 2px #3b82f6 !important;
    z-index: 10 !important;
    animation: subtle-pulse 1.5s ease-in-out infinite;
  }

  /* Pulse animation for selected appointment */
  @keyframes subtle-pulse {
    0%,
    100% {
      box-shadow: 0 0 0 2px #3b82f6;
    }
    50% {
      box-shadow: 0 0 0 2px #3b82f6, 0 0 8px rgba(59, 130, 246, 0.4);
    }
  }

  /* Disable pulse animation if user prefers reduced motion */
  @media (prefers-reduced-motion: reduce) {
    :deep(.fc-event.is-selected-for-action) {
      animation: none !important;
    }
  }
}
</style>
