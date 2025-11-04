<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppointmentsStore } from '@/stores/appointments'
import FullCalendar from '@fullcalendar/vue3'
import type {
  EventDropArg,
  EventClickArg,
  EventContentArg,
  EventMountArg,
} from '@fullcalendar/core'
import type { AppointmentListItem, AppointmentFormData } from '@/types/calendar'
import { useCalendar } from '@/composables/useCalendar'
import { useCalendarEvents } from '@/composables/useCalendarEvents'
import { useCalendarKeyboardShortcuts } from '@/composables/useCalendarKeyboardShortcuts'
import { useCalendarLoading } from '@/composables/useCalendarLoading'
import { useAppointmentDrag } from '@/composables/useAppointmentDrag'
import { useCalendarCreation } from '@/composables/useCalendarCreation'
import { useCalendarSwipe } from '@/composables/useCalendarSwipe'
import { useCalendarDragScrollLock } from '@/composables/useCalendarDragScrollLock'
import { useScreenReader } from '@/composables/useScreenReader'
import { useToast } from '@/composables/useToast'
import { usePayments } from '@/composables/usePayments'
import { useI18n } from '@/composables/useI18n'
import { toISOString } from '@/utils/dragHelpers'
import type { ConflictingAppointment } from '@/api/client'
import type { AppointmentStatus } from '@/types/calendar'
import apiClient from '@/api/client'
import CalendarToolbar from '@/components/calendar/CalendarToolbar.vue'
import AppointmentDetailsModal from '@/components/calendar/AppointmentDetailsModal.vue'
import AppointmentFormModal from '@/components/calendar/AppointmentFormModal.vue'
import CancelAppointmentDialog from '@/components/calendar/CancelAppointmentDialog.vue'
import CalendarLoadingState from '@/components/calendar/CalendarLoadingState.vue'
import DragConflictModal from '@/components/calendar/DragConflictModal.vue'
import MobileRescheduleModal from '@/components/calendar/MobileRescheduleModal.vue'
import DeleteAppointmentModal from '@/components/appointments/DeleteAppointmentModal.vue'
import FloatingActionButton from '@/components/common/FloatingActionButton.vue'
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
const calendarContainerRef = ref<HTMLElement | null>(null)

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

const { announcement: screenReaderAnnouncement, announce } = useScreenReader()
const { showSuccess, showAppointmentSuccess, showSuccessWithUndo, showError } =
  useToast()
const { paymentsEnabled, getPaymentStatusBadge } = usePayments()
const { t } = useI18n()

const {
  currentView,
  currentDate,
  currentDateRange,
  formattedDateRange,
  isToolbarNavigating,
  changeView,
  handlePrev,
  handleNext,
  handleToday,
  buildCalendarOptions,
} = useCalendar()

const {
  selectedAppointment,
  calendarEvents,
  handleEventClick: composableHandleEventClick,
  sessionStatusMap,
} = useCalendarEvents()

// Wrap handleEventClick to capture times before modal opens
function handleEventClick(clickInfo: EventClickArg) {
  // Both mobile and desktop: open modal immediately
  composableHandleEventClick(clickInfo)

  // Then, if an appointment was selected, capture its current times IMMEDIATELY
  // This happens BEFORE any auto-save or reactive updates
  if (selectedAppointment.value) {
    previousAppointmentTimes.value.set(selectedAppointment.value.id, {
      start: selectedAppointment.value.scheduled_start,
      end: selectedAppointment.value.scheduled_end,
    })
  }
}

const { showLoadingSpinner } = useCalendarLoading()

// Mobile swipe navigation - hidden on desktop (≥640px)
const { isNavigating } = useCalendarSwipe(
  calendarContainerRef,
  handlePrev,
  handleNext
)

// Mobile drag scroll isolation - locks body scroll during drag on mobile (<768px)
const { activateScrollIsolation, deactivateScrollIsolation } =
  useCalendarDragScrollLock()

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
  const appointment = appointmentsStore.appointments.find((a) => a.id === appointmentId)
  if (!appointment) return

  const newStart = new Date(appointment.scheduled_start)
  const newEnd = new Date(appointment.scheduled_end)

  // Find the event DOM element and apply height fix directly
  // Use multiple animation frames to ensure FullCalendar has finished its render cycle
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const eventEl = document.querySelector(
          `[data-event-id="${appointmentId}"]`
        ) as HTMLElement
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
 * Open create modal with pre-filled date/time from calendar click
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
  ghostTimeRange,
  ghostDateTimePreview,
  dragState,
  handleEventDrop,
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
 * Marks a past scheduled appointment as attended
 */
async function handleQuickComplete(appointmentId: string) {
  const appointment = appointmentsStore.appointments.find(
    (a: AppointmentListItem) => a.id === appointmentId
  )
  if (!appointment) return

  try {
    await appointmentsStore.updateAppointmentStatus(appointmentId, 'attended')

    // Show success toast with client name
    const clientName = appointment.client?.first_name || t('calendar.calendarView.appointmentFallback')
    showSuccess(t('calendar.calendarView.messages.attended', { clientName }), {
      toastId: `attendance-${appointmentId}-${Date.now()}`,
    })

    // Screen reader announcement
    announce(t('calendar.calendarView.messages.attendedAnnouncement'))
  } catch (error) {
    console.error('Failed to mark appointment as attended:', error)
    showError(t('calendar.calendarView.messages.attendedError'))
  }
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
        ? t('calendar.calendarView.messages.deletedWithNote')
        : payload.session_note_action === 'keep'
          ? t('calendar.calendarView.messages.deletedNoteKept')
          : t('calendar.calendarView.messages.deleted')

    showSuccess(message)

    // Close the modal and clear state
    appointmentToDelete.value = null
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : t('calendar.calendarView.messages.deleteError')
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

  // Mobile drag scroll isolation - activate/deactivate on drag start/stop
  eventDragStart: () => {
    const calendarContentArea = document.querySelector(
      '.calendar-content-area'
    ) as HTMLElement
    if (calendarContentArea) {
      activateScrollIsolation(calendarContentArea)
    }
  },
  eventDragStop: () => {
    deactivateScrollIsolation()
  },

  // Use eventContent to declaratively render event content with quick action buttons
  // This ensures buttons persist across all FullCalendar renders (initial, updates, etc.)
  eventContent: (arg: EventContentArg) => {
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

    // Detect mobile format (newline-separated) vs desktop format
    const eventTitle = event.title || 'Untitled'
    const isMobileFormat = eventTitle.includes('\n')

    if (isMobileFormat) {
      // Mobile: Parse newline-separated parts and render vertically
      title.className = 'fc-event-title flex flex-col items-start gap-0.5'

      const parts = eventTitle.split('\n')
      parts.forEach((part: string, index: number) => {
        const span = document.createElement('span')

        if (index === 0) {
          // Patient initials - primary, bold, larger
          span.className = 'text-base font-bold tracking-wide'
          span.textContent = part
        } else {
          // Status/session indicators - smaller, reduced opacity
          span.className = 'text-sm opacity-85'
          span.textContent = part
        }

        title.appendChild(span)
      })
    } else {
      // Desktop: Render as plain text (existing behavior)
      title.textContent = eventTitle
    }

    titleContainer.appendChild(title)
    wrapper.appendChild(titleContainer)

    // Payment status indicator (only if payments enabled and status exists)
    const paymentStatus = event.extendedProps?.payment_status
    if (paymentsEnabled.value && paymentStatus) {
      const badge = getPaymentStatusBadge(paymentStatus)

      if (badge?.showBadge) {
        const paymentBadge = document.createElement('div')
        paymentBadge.className = 'payment-badge absolute top-2 right-2 z-10'
        paymentBadge.setAttribute('role', 'img')
        paymentBadge.setAttribute('aria-label', `Payment: ${badge.label}`)
        paymentBadge.title = `Payment: ${badge.label}`

        // Icon container with background circle
        const iconContainer = document.createElement('div')
        iconContainer.className = 'payment-icon-container'
        iconContainer.style.cssText = `
          width: 16px;
          height: 16px;
          background: white;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
        `

        // SVG icon
        const iconWrapper = document.createElement('div')
        iconWrapper.innerHTML = badge.iconSvg || ''
        iconWrapper.style.cssText = `
          width: 12px;
          height: 12px;
          color: ${badge.iconColor};
          filter: drop-shadow(0 0.5px 1px rgba(0, 0, 0, 0.15));
        `

        iconContainer.appendChild(iconWrapper)
        paymentBadge.appendChild(iconContainer)
        wrapper.appendChild(paymentBadge)
      }
    }

    // Quick action buttons container (desktop only - hidden on mobile ≤640px)
    const actionsContainer = document.createElement('div')
    actionsContainer.className =
      'calendar-quick-actions absolute top-1 right-1 flex gap-1 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity duration-150 z-10'

    // Complete button (only for past scheduled appointments)
    if (canComplete) {
      const completeBtn = document.createElement('button')
      completeBtn.className =
        'p-1 rounded bg-white/90 hover:bg-emerald-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 shadow-sm'
      completeBtn.title = 'Mark attended (C)'
      completeBtn.setAttribute('aria-label', 'Mark appointment as attended')
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
    deleteBtn.title = t('calendar.calendarView.deleteKeyHint')
    deleteBtn.setAttribute('aria-label', t('calendar.calendarView.deleteAriaLabel'))
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

  eventDidMount: (info: EventMountArg) => {
    const event = info.event
    const hasSession = event.extendedProps?.hasSession
    const isDraft = event.extendedProps?.isDraft
    const duration = event.extendedProps?.duration_minutes

    // Add data attribute so we can find this element later
    info.el.setAttribute('data-event-id', event.id)

    // Apply height fix for FullCalendar v6 bug
    if (event.start && event.end) {
      applyEventHeight(info.el, event.start, event.end)
    }

    // Build tooltip text - always use full name for accessibility
    // On mobile, the title contains initials, so we need to get the full name from appointments store
    const appointment = appointmentsStore.appointments.find((a) => a.id === event.id)
    const fullName =
      appointment?.client?.full_name ||
      (appointment?.client_id
        ? `Client ${appointment.client_id.slice(0, 8)}`
        : 'Unknown Client')

    let tooltipText = fullName

    if (hasSession) {
      tooltipText += isDraft
        ? '\n📄 Session note: Draft'
        : '\n📄 Session note: Finalized'
    } else if (event.extendedProps?.status === 'attended') {
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

// Watch for view changes and update FullCalendar
watch(currentView, (newView) => {
  const calendarApi = calendarRef.value?.getApi()
  if (calendarApi) {
    calendarApi.changeView(newView)
  }
})

// Watch for date changes and navigate FullCalendar
watch(currentDate, (newDate) => {
  const calendarApi = calendarRef.value?.getApi()
  if (calendarApi) {
    calendarApi.gotoDate(newDate)
  }
})

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
    appointment.client?.first_name || appointment.client?.full_name || t('calendar.calendarView.appointmentFallback')

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
    showSuccessWithUndo(t('calendar.calendarView.messages.rescheduled', { clientName }), handleUndo)
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
    appointment.client?.first_name || appointment.client?.full_name || t('calendar.calendarView.appointmentFallback')

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
    showSuccessWithUndo(t('calendar.calendarView.messages.rescheduled', { clientName }), handleUndo)

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

  // Use locale-aware appointment count
  const countKey =
    appointmentCount === 1
      ? 'calendar.toolbar.appointmentCountSingular'
      : 'calendar.toolbar.appointmentCountPlural'
  parts.push(t(countKey, { count: appointmentCount }))

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
      error instanceof Error ? error.message : t('calendar.calendarView.messages.statusUpdateError')
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
const previousAppointmentTimes = ref<Map<string, { start: string; end: string }>>(
  new Map()
)

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
    const durationChanged =
      prevTimes &&
      (prevTimes.start !== updatedAppointment.scheduled_start ||
        prevTimes.end !== updatedAppointment.scheduled_end)

    // Update tracked times for next comparison
    previousAppointmentTimes.value.set(appointmentId, {
      start: updatedAppointment.scheduled_start,
      end: updatedAppointment.scheduled_end,
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
    // Only auto-complete if appointment has ENDED (not just in progress)
    const now = new Date()
    const appointmentEnd = new Date(appointment.scheduled_end)
    const isAppointmentPast = appointmentEnd < now

    if (appointment.status === 'scheduled' && isAppointmentPast) {
      await appointmentsStore.updateAppointmentStatus(appointment.id, 'attended')
      // Show toast notification for auto-completion with client name and unique ID
      const clientName = appointment.client?.first_name || 'Appointment'
      showSuccess(`${clientName} attended`, {
        toastId: `attendance-${appointment.id}-${Date.now()}`,
      })
    }
    // For in-progress appointments: status stays "scheduled", no toast notification

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
      payment_status: 'not_paid',
    })

    // Close modal on success
    showCreateModal.value = false
    createModalPrefillData.value = null

    // Show success toast with rich content
    const clientName = newAppt.client?.full_name || t('calendar.calendarView.appointmentFallback')
    showAppointmentSuccess(t('calendar.calendarView.messages.created'), {
      clientName,
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
    announce(t('calendar.calendarView.messages.createdAnnouncement', { clientName }))
  } catch (error) {
    console.error('Failed to create appointment:', error)
    // TODO (M3): Add error toast notification
    // Keep modal open on error so user can retry
  }
}

async function handleEditAppointment(data: AppointmentFormData) {
  if (!appointmentToEdit.value) return

  try {
    // Convert payment_price from number to string for API (backend expects Decimal as string)
    const updateData = {
      ...data,
      payment_price:
        data.payment_price !== null && data.payment_price !== undefined
          ? String(data.payment_price)
          : data.payment_price,
    }

    // Update appointment in store (calls API and updates local state)
    await appointmentsStore.updateAppointment(appointmentToEdit.value.id, updateData)

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
    announce(t('calendar.calendarView.messages.updatedAnnouncement'))
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
    const clientName = appointment.client?.first_name || t('calendar.calendarView.appointmentFallback')
    showSuccessWithUndo(t('calendar.calendarView.messages.cancelled', { clientName }), handleUndoCancel)

    // Screen reader announcement
    await announce(
      t('calendar.calendarView.messages.cancelledAnnouncement', { clientName: appointment.client?.full_name || 'client' })
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
      status: originalStatus as 'scheduled' | 'attended' | 'cancelled' | 'no_show',
      notes: originalNotes,
    })

    // Clear undo state
    undoCancelData.value = null

    // Screen reader announcement
    await announce(t('calendar.calendarView.messages.undoCancelled'))
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
    await announce(t('calendar.calendarView.messages.restored'))
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
  // Quick action: Get directions with 'G' key (when appointment is selected and has address)
  if ((event.key === 'g' || event.key === 'G') && !event.ctrlKey && !event.metaKey) {
    if (selectedAppointment.value) {
      // Check if appointment has a physical address (home visit or clinic with address)
      const address = selectedAppointment.value.location_details
      if (address && selectedAppointment.value.location_type !== 'online') {
        event.preventDefault()
        const url = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(address)}`
        window.open(url, '_blank', 'noopener,noreferrer')
        return
      }
    }
  }

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
  // Only trigger if NOT typing in an input field
  if (event.key === 'Delete' || event.key === 'Backspace') {
    const target = event.target as HTMLElement
    const isTyping =
      target.tagName === 'INPUT' ||
      target.tagName === 'TEXTAREA' ||
      target.isContentEditable

    if (selectedAppointment.value && !isTyping) {
      event.preventDefault()
      handleQuickDelete(selectedAppointment.value.id)
      selectedAppointment.value = null // Close detail modal
      return
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
  <div class="container mx-auto px-5 py-6 pb-20 sm:px-6 sm:py-8">
    <!-- Loading State (Only show for initial load with no appointments, not during navigation) -->
    <CalendarLoadingState
      v-if="
        showLoadingSpinner &&
        appointmentsStore.appointments.length === 0 &&
        !isNavigating &&
        !isToolbarNavigating
      "
    />

    <!-- Error State -->
    <div
      v-else-if="appointmentsStore.error"
      class="rounded-lg border border-red-200 bg-red-50 p-4 text-red-800"
    >
      <p class="font-semibold">{{ t('calendar.calendarView.errorLoading') }}</p>
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
      <div class="calendar-content-area relative overflow-hidden">
        <!-- FullCalendar Component -->
        <div
          ref="calendarContainerRef"
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

          <FullCalendar
            ref="calendarRef"
            :options="calendarOptions"
          />
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

    <!-- Floating Action Button -->
    <FloatingActionButton
      :label="t('calendar.calendarView.newAppointmentButton')"
      :title="t('calendar.calendarView.newAppointmentTitle')"
      @click="createNewAppointment"
    />

    <!-- Screen Reader Announcements -->
    <div role="status" aria-live="polite" aria-atomic="true" class="sr-only">
      {{ screenReaderAnnouncement }}
    </div>

    <!-- Drag-and-Drop Screen Reader Announcements -->
    <div
      id="drag-drop-announcer"
      role="status"
      aria-live="polite"
      aria-atomic="true"
      class="sr-only"
    >
      <!-- Announces drag state changes for screen readers -->
    </div>

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
/* ===========================
   Calendar Swipe Transitions
   =========================== */

/*
 * Mobile-Native Slide Transitions
 *
 * Both entering and exiting calendars animate simultaneously for smooth,
 * native-feeling transitions. Entering calendar slides in from the side
 * while exiting calendar slides out partially (creating depth effect).
 *
 * Key Design Decisions:
 * - Simultaneous animation (no mode="out-in") for smoother feel
 * - Absolute positioning during transition to overlap calendars
 * - Entering calendar on top (z-index: 1), exiting behind (z-index: 0)
 * - Partial exit slide (-30% instead of -100%) creates depth
 * - iOS spring curve: cubic-bezier(0.33, 1, 0.68, 1)
 * - Fast duration: 140ms matches native calendar apps
 */

/* Slide Left - Swipe left → Next period (forward in time) */
.calendar-slide-left-enter-active,
.calendar-slide-left-leave-active {
  transition:
    transform 140ms cubic-bezier(0.33, 1, 0.68, 1),
    opacity 120ms ease-out;
  will-change: transform, opacity;
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
}

.calendar-slide-left-enter-active {
  z-index: 1; /* Entering calendar on top */
}

.calendar-slide-left-leave-active {
  z-index: 0; /* Exiting calendar behind */
}

.calendar-slide-left-enter-from {
  transform: translateX(100%); /* Enter from right */
  opacity: 0;
}

.calendar-slide-left-enter-to {
  transform: translateX(0); /* Slide to center */
  opacity: 1;
}

.calendar-slide-left-leave-from {
  transform: translateX(0); /* Start at center */
  opacity: 1;
}

.calendar-slide-left-leave-to {
  transform: translateX(-30%); /* Partial slide creates depth */
  opacity: 0;
}

/* Slide Right - Swipe right → Previous period (backward in time) */
.calendar-slide-right-enter-active,
.calendar-slide-right-leave-active {
  transition:
    transform 140ms cubic-bezier(0.33, 1, 0.68, 1),
    opacity 120ms ease-out;
  will-change: transform, opacity;
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
}

.calendar-slide-right-enter-active {
  z-index: 1; /* Entering calendar on top */
}

.calendar-slide-right-leave-active {
  z-index: 0; /* Exiting calendar behind */
}

.calendar-slide-right-enter-from {
  transform: translateX(-100%); /* Enter from left */
  opacity: 0;
}

.calendar-slide-right-enter-to {
  transform: translateX(0); /* Slide to center */
  opacity: 1;
}

.calendar-slide-right-leave-from {
  transform: translateX(0); /* Start at center */
  opacity: 1;
}

.calendar-slide-right-leave-to {
  transform: translateX(30%); /* Partial slide creates depth */
  opacity: 0;
}

/* Fallback fade for non-swipe navigation (toolbar clicks) */
.calendar-fade-enter-active,
.calendar-fade-leave-active {
  transition: opacity 150ms ease-in-out;
}

.calendar-fade-enter-from,
.calendar-fade-leave-to {
  opacity: 0;
}

/* ===========================
   Mobile Drag Scroll Isolation (Phase 1)
   =========================== */

/* Body scroll lock during drag (mobile only) */
body.drag-mode-active {
  overflow: hidden !important;
  position: fixed !important;
  width: 100% !important;
  /* top is set dynamically via inline style to preserve scroll position */
}

html.drag-mode-active {
  overflow: hidden !important;
}

/* Overlay dimming effect during drag (5% black - very subtle) */
body.drag-mode-active::before {
  content: '';
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.05);
  z-index: 5;
  pointer-events: none;
  transition: opacity 150ms ease-out;
}

/* Calendar elevated during drag with subtle blue glow */
.calendar-content-area.drag-active {
  position: relative;
  z-index: 10;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
  transition: box-shadow 150ms ease-out;
}

/* Accessibility: Respect user's motion preferences */
@media (prefers-reduced-motion: reduce) {
  .calendar-slide-left-enter-active,
  .calendar-slide-left-leave-active,
  .calendar-slide-right-enter-active,
  .calendar-slide-right-leave-active {
    transition: opacity 150ms ease-in-out;
  }

  .calendar-slide-left-enter-from,
  .calendar-slide-right-enter-from {
    transform: none; /* Disable sliding */
    opacity: 0;
  }

  .calendar-slide-left-leave-to,
  .calendar-slide-right-leave-to {
    transform: none; /* Disable sliding */
    opacity: 0;
  }

  .calendar-fade-enter-active,
  .calendar-fade-leave-active {
    transition: none; /* Instant swap for maximum reduced motion */
  }

  /* Disable scroll lock transitions for reduced motion */
  .calendar-content-area.drag-active {
    transition: none;
  }

  body.drag-mode-active::before {
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
  /* Enable smooth touch scrolling on mobile */
  -webkit-overflow-scrolling: touch;
  /* Prevent text selection during swipe gestures on mobile */
  -webkit-user-select: none;
  user-select: none;
}

/* Re-enable text selection on desktop */
@media (min-width: 641px) {
  .calendar-container {
    -webkit-user-select: auto;
    user-select: auto;
  }
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

/* Payment status left border accent (Phase 1.5) */
:deep(.fc-event.payment-not-paid) {
  border-left: 3px solid #d1d5db !important; /* gray-300 */
  padding-left: 4px;
}

:deep(.fc-event.payment-paid) {
  border-left: 3px solid #10b981 !important; /* emerald-500 */
  padding-left: 4px;
}

:deep(.fc-event.payment-sent) {
  border-left: 3px solid #f59e0b !important; /* amber-500 */
  padding-left: 4px;
}

:deep(.fc-event.payment-waived) {
  border-left: 3px solid #8b5cf6 !important; /* violet-500 */
  padding-left: 4px;
}

/* Priority: Session note border overrides payment border */
:deep(.fc-event.event-with-session) {
  border-left: 3px solid #10b981 !important; /* emerald-500 - session takes precedence */
  padding-left: 4px;
}

/* Mobile: Slightly larger icon badge for better visibility */
@media (max-width: 640px) {
  .payment-badge .payment-icon-container {
    width: 18px !important;
    height: 18px !important;
  }

  .payment-badge .payment-icon-container > div {
    width: 14px !important;
    height: 14px !important;
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
    padding: 8px 6px; /* Larger padding for vertical stacking */
    font-size: 0.875rem;
    min-height: 60px; /* Ensure space for 3 lines (initials + status + session) */
  }

  /* Mobile event title - vertical layout with proper spacing */
  .fc-event-title {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 2px;
    width: 100%;
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

/* Click to create - Cursor affordance */

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
}
</style>
