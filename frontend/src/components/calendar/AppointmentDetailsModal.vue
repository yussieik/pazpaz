<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useFocusTrap } from '@vueuse/integrations/useFocusTrap'
import { useScrollLock, onKeyStroke } from '@vueuse/core'
import type {
  AppointmentListItem,
  SessionStatus,
  AppointmentStatus,
} from '@/types/calendar'
import { formatDate } from '@/utils/calendar/dateFormatters'
import { getStatusBadgeClass } from '@/utils/calendar/appointmentHelpers'
import { useAppointmentAutoSave } from '@/composables/useAppointmentAutoSave'
import { useToast } from '@/composables/useToast'
import { useAppointmentsStore } from '@/stores/appointments'
import AppointmentStatusCard from './AppointmentStatusCard.vue'
import DeleteAppointmentModal from '@/components/appointments/DeleteAppointmentModal.vue'
import AppointmentEditIndicator from '@/components/appointments/AppointmentEditIndicator.vue'
import TimePickerDropdown from '@/components/common/TimePickerDropdown.vue'
import IconClose from '@/components/icons/IconClose.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import { formatDistanceToNow, format as formatDateTime } from 'date-fns'

const appointmentsStore = useAppointmentsStore()
const { showSuccess, showSuccessWithUndo, showError } = useToast()

// Delete modal state
const showDeleteModal = ref(false)

interface Props {
  appointment: AppointmentListItem | null
  visible: boolean
  showEditSuccess?: boolean
  sessionStatus?: SessionStatus | null
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'startSessionNotes', appointment: AppointmentListItem): void
  (e: 'cancel', appointment: AppointmentListItem): void
  (e: 'restore', appointment: AppointmentListItem): void
  (e: 'viewClient', clientId: string): void
  (e: 'viewSession', sessionId: string): void
  (e: 'refresh'): void // Emit when appointment is updated
  (e: 'updateStatus', appointmentId: string, status: string): void
  (e: 'edit', appointment: AppointmentListItem): void
}

const props = withDefaults(defineProps<Props>(), {
  showEditSuccess: false,
})
const emit = defineEmits<Emits>()

const modalRef = ref<HTMLElement>()

// H9: Focus trap for accessibility (WCAG 2.1 AA compliance)
// Disable Escape key handling by focus trap - we'll handle it manually
// Disable click outside when delete modal is open to prevent closing parent modal
const { activate, deactivate } = useFocusTrap(modalRef, {
  immediate: false,
  escapeDeactivates: false, // Disable - we'll handle Escape manually
  clickOutsideDeactivates: () => !showDeleteModal.value, // Disable when delete modal is open
  allowOutsideClick: true,
})

// P1-1: Scroll lock to prevent background scrolling
const isLocked = useScrollLock(document.body)

// Local editable state
const editableData = ref({
  scheduled_start: '',
  scheduled_end: '',
  location_type: 'clinic' as 'clinic' | 'home' | 'online',
  location_details: '',
  notes: '',
})

// Separate date field for the date picker (YYYY-MM-DD format)
const appointmentDate = ref<string>('')

// Flag to prevent duration preservation during date changes
const isUpdatingFromDateChange = ref(false)

// Auto-save composable
const autoSave = computed(() => {
  if (!props.appointment) return null
  return useAppointmentAutoSave(props.appointment.id)
})

// Computed properties for auto-save status
const isSaving = computed(() => autoSave.value?.isSaving.value || false)
const lastSaved = computed(() => autoSave.value?.lastSaved.value || null)
const saveError = computed(() => autoSave.value?.saveError.value || null)

// All appointments are editable with audit trail tracking

/**
 * Format the last saved time for display
 */
const lastSavedText = computed(() => {
  if (!lastSaved.value) return ''
  return formatDate(lastSaved.value.toISOString(), 'h:mm a')
})

/**
 * Format datetime-local input value (local timezone)
 * datetime-local inputs expect format: YYYY-MM-DDTHH:mm
 */
function formatDateTimeLocal(isoString: string): string {
  const date = new Date(isoString)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day}T${hours}:${minutes}`
}

/**
 * Helper: Add minutes to a datetime string
 */
function addMinutes(datetimeString: string, minutes: number): string {
  const date = new Date(datetimeString)
  date.setMinutes(date.getMinutes() + minutes)
  return formatDateTimeLocal(date.toISOString())
}

/**
 * Helper: Calculate duration in minutes between two datetime strings
 */
function getDurationMinutes(start: string, end: string): number {
  const startDate = new Date(start)
  const endDate = new Date(end)
  return Math.round((endDate.getTime() - startDate.getTime()) / (1000 * 60))
}

/**
 * Convert datetime-local input to ISO string (preserving local timezone)
 */
function parseDateTimeLocal(dateTimeLocal: string): string {
  // Create date from local datetime string
  const date = new Date(dateTimeLocal)
  return date.toISOString()
}

// Activate/deactivate focus trap and scroll lock based on visibility
watch(
  () => props.visible,
  (isVisible) => {
    isLocked.value = isVisible // Lock scroll when modal opens

    if (isVisible && modalRef.value) {
      nextTick(() => activate())
    } else {
      deactivate()
    }
  }
)

// Sync local editable data with appointment prop
watch(
  () => props.appointment,
  (newAppointment) => {
    if (newAppointment) {
      editableData.value = {
        scheduled_start: formatDateTimeLocal(newAppointment.scheduled_start),
        scheduled_end: formatDateTimeLocal(newAppointment.scheduled_end),
        location_type: newAppointment.location_type,
        location_details: newAppointment.location_details || '',
        notes: newAppointment.notes || '',
      }
    }
  },
  { immediate: true }
)

// Previous start time for duration preservation
const previousStartTime = ref<string>('')

// Watch start time changes to preserve duration
watch(
  () => editableData.value.scheduled_start,
  (newStart, oldStart) => {
    // Skip if updating from date change (end time is already set correctly)
    if (isUpdatingFromDateChange.value) {
      previousStartTime.value = newStart
      return
    }

    // Skip if initial load or no old value
    if (!oldStart || !editableData.value.scheduled_end) {
      previousStartTime.value = newStart
      return
    }

    // Calculate current duration from old start to end
    const currentDuration = getDurationMinutes(
      oldStart,
      editableData.value.scheduled_end
    )

    // Apply same duration to new start time
    editableData.value.scheduled_end = addMinutes(newStart, currentDuration)

    // Store for next change
    previousStartTime.value = newStart
  }
)

/**
 * Close modal immediately
 * Auto-save will complete in the background
 */
function closeModal() {
  // Don't close if delete modal is open
  if (showDeleteModal.value) {
    return
  }

  // Force blur on active element to trigger auto-save
  // Auto-save will complete in background after modal closes
  if (document.activeElement instanceof HTMLElement) {
    document.activeElement.blur()
  }
  emit('update:visible', false)
}

/**
 * Handle field blur - save the field immediately
 */
async function handleFieldBlur(
  field: keyof typeof editableData.value,
  debounce = false
) {
  if (!props.appointment || !autoSave.value) return

  const value = editableData.value[field]

  try {
    await autoSave.value.saveField(field, value, debounce)
    // Emit refresh to update parent component's appointment data
    emit('refresh')
  } catch {
    // Error is already handled by autoSave composable
    // Silently catch to prevent unhandled promise rejection
  }
}

/**
 * Format relative time for edit indicators
 */
function formatRelativeTime(isoString: string): string {
  return formatDistanceToNow(new Date(isoString), { addSuffix: true })
}

/**
 * Format absolute time for tooltips
 */
function formatAbsoluteTime(isoString: string): string {
  return formatDateTime(new Date(isoString), "MMM d, yyyy 'at' h:mm a")
}

/**
 * Check if appointment has been edited
 */
const hasBeenEdited = computed(() => {
  // @ts-expect-error - edited_at will be added by backend specialist
  return !!props.appointment?.edited_at
})

/**
 * Handle date/time change - convert to ISO and save immediately (no debounce)
 * When start time changes, also save end time to preserve duration
 */
async function handleDateTimeChange(field: 'scheduled_start' | 'scheduled_end') {
  if (!props.appointment || !autoSave.value) return

  // Get the local datetime value from editableData
  const localDateTimeValue = editableData.value[field]

  // Convert local datetime format to ISO string for API
  const isoValue = parseDateTimeLocal(localDateTimeValue)

  try {
    // If changing start time, also save end time to preserve duration
    // (the watcher updates end time locally, but we need to save both to API)
    if (field === 'scheduled_start') {
      // Wait for watcher to update end time (preserves duration)
      await nextTick()

      const startISO = isoValue
      const endISO = parseDateTimeLocal(editableData.value.scheduled_end)

      // Save both start and end together
      await appointmentsStore.updateAppointment(props.appointment.id, {
        scheduled_start: startISO,
        scheduled_end: endISO,
      })
    } else {
      // For end time changes, just save the single field
      await autoSave.value.saveField(field, isoValue, false)
    }

    // Emit refresh to update parent component's appointment data
    emit('refresh')
  } catch {
    // Error is already handled by autoSave composable
    // Silently catch to prevent unhandled promise rejection
  }
}

/**
 * Handle location type change - save immediately
 */
function handleLocationTypeChange() {
  handleFieldBlur('location_type', false)
}

/**
 * Handle text field blur - save with debounce for notes
 */
function handleTextFieldBlur(field: 'location_details' | 'notes') {
  const debounce = field === 'notes'
  handleFieldBlur(field, debounce)
}

/**
 * Check if appointment is in the past
 */
const isPastAppointment = computed(() => {
  if (!props.appointment) return false
  return new Date(props.appointment.scheduled_end) < new Date()
})

/**
 * Check if appointment is in the future
 */
const isFutureAppointment = computed(() => {
  if (!props.appointment) return false
  return new Date(props.appointment.scheduled_start) > new Date()
})

/**
 * Get user-friendly message for status change with client name
 */
function getStatusChangeMessage(status: AppointmentStatus, clientName: string): string {
  const messages: Record<AppointmentStatus, string> = {
    scheduled: `${clientName} restored to scheduled`,
    confirmed: `${clientName} confirmed`,
    completed: `${clientName} completed`,
    cancelled: `${clientName} cancelled`,
    no_show: `${clientName} marked as no-show`,
  }
  return messages[status] || 'Status updated'
}

/**
 * Handle status update from AppointmentStatusCard
 * Shows toast notification with undo functionality using closure-based handler
 */
async function handleStatusUpdate(newStatus: string) {
  if (!props.appointment) return

  // Capture data in closure for undo handler
  const appointmentId = props.appointment.id
  const previousStatus = props.appointment.status
  const clientName = props.appointment.client?.first_name || 'Appointment'

  try {
    // Update status via store
    await appointmentsStore.updateAppointmentStatus(
      appointmentId,
      newStatus as AppointmentStatus
    )

    // Create closure-based undo handler
    const handleUndo = async () => {
      try {
        await appointmentsStore.updateAppointmentStatus(
          appointmentId,
          previousStatus as AppointmentStatus
        )
        showSuccess('Status reverted')
        emit('refresh')
      } catch (error) {
        const errorMessage =
          error instanceof Error ? error.message : 'Failed to undo status change'
        showError(errorMessage)
      }
    }

    // Show success toast with undo using closure-based pattern
    showSuccessWithUndo(
      getStatusChangeMessage(newStatus as AppointmentStatus, clientName),
      handleUndo
    )

    // Emit refresh to update parent
    emit('refresh')
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : 'Failed to update appointment status'
    showError(errorMessage)
  }
}

/**
 * Handle complete and document action
 */
function handleCompleteAndDocument() {
  if (!props.appointment) return
  // First update status, then start session notes
  emit('updateStatus', props.appointment.id, 'completed')
  // Emit startSessionNotes to navigate to session creation
  emit('startSessionNotes', props.appointment)
}

/**
 * Handle delete button click - show modal for confirmation
 */
function handleDeleteClick() {
  if (!props.appointment) return
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
  if (!props.appointment) return

  try {
    await appointmentsStore.deleteAppointment(props.appointment.id, payload)
    showDeleteModal.value = false

    // Show appropriate success message
    const message =
      payload.session_note_action === 'delete'
        ? 'Appointment and session note deleted'
        : payload.session_note_action === 'keep'
          ? 'Appointment deleted (session note kept)'
          : 'Appointment deleted'

    showSuccess(message)
    emit('refresh')
    emit('update:visible', false) // Close the details modal
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
}

/**
 * Handle Escape key for AppointmentDetailsModal
 * Only close this modal if delete modal is NOT open
 */
onKeyStroke('Escape', (e) => {
  // Don't handle if modal is not visible
  if (!props.visible) return

  // Don't handle if delete modal is open (let DeleteAppointmentModal handle it)
  if (showDeleteModal.value) {
    return
  }

  e.preventDefault()
  closeModal()
})

/**
 * Computed property for calculated duration
 */
const calculatedDuration = computed(() => {
  if (!editableData.value.scheduled_start || !editableData.value.scheduled_end) return 0
  return getDurationMinutes(
    editableData.value.scheduled_start,
    editableData.value.scheduled_end
  )
})

/**
 * Set duration by adjusting end time relative to start time
 */
function setDuration(minutes: number) {
  if (!editableData.value.scheduled_start) return

  editableData.value.scheduled_end = addMinutes(
    editableData.value.scheduled_start,
    minutes
  )
  // Trigger auto-save for end time
  handleDateTimeChange('scheduled_end')
}

/**
 * Extract date in YYYY-MM-DD format from datetime string
 */
function extractDate(datetimeString: string): string {
  if (!datetimeString) return ''
  const date = new Date(datetimeString)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/**
 * Watch for date changes and update start/end times accordingly
 */
watch(appointmentDate, async (newDate, oldDate) => {
  if (!newDate || !editableData.value.scheduled_start) return

  // Skip if date hasn't actually changed (prevent circular updates)
  if (newDate === oldDate) return

  // Set flag to prevent duration preservation watcher from interfering
  isUpdatingFromDateChange.value = true

  // Extract time from current start/end (these are in datetime-local format: YYYY-MM-DDTHH:mm)
  const startTime = new Date(editableData.value.scheduled_start)
  const endTime = new Date(editableData.value.scheduled_end)

  // Parse new date components (YYYY-MM-DD format)
  const [year, month, day] = newDate.split('-').map(Number)

  // Create new datetime with new date and existing times (using local timezone)
  const newStart = new Date(
    year,
    month - 1,
    day,
    startTime.getHours(),
    startTime.getMinutes(),
    0,
    0
  )
  const newEnd = new Date(
    year,
    month - 1,
    day,
    endTime.getHours(),
    endTime.getMinutes(),
    0,
    0
  )

  // Format as datetime-local (YYYY-MM-DDTHH:mm)
  editableData.value.scheduled_start = formatDateTimeLocal(newStart.toISOString())
  editableData.value.scheduled_end = formatDateTimeLocal(newEnd.toISOString())

  // Wait for reactivity to settle before saving
  await nextTick()

  // Clear flag after updates complete
  isUpdatingFromDateChange.value = false

  // Save both start and end times together to avoid validation errors
  if (props.appointment && autoSave.value) {
    const startISO = parseDateTimeLocal(editableData.value.scheduled_start)
    const endISO = parseDateTimeLocal(editableData.value.scheduled_end)

    try {
      // Update both fields in the store
      await appointmentsStore.updateAppointment(props.appointment.id, {
        scheduled_start: startISO,
        scheduled_end: endISO,
      })
      emit('refresh')
    } catch (error) {
      console.error('Failed to update appointment dates:', error)
    }
  }
})

/**
 * Sync appointmentDate when editableData.scheduled_start changes
 * (but only if date portion actually changed to avoid circular updates)
 */
watch(
  () => editableData.value.scheduled_start,
  (newStart) => {
    if (newStart) {
      const newDateValue = extractDate(newStart)
      // Only update if date actually changed (avoid circular updates)
      if (newDateValue !== appointmentDate.value) {
        appointmentDate.value = newDateValue
      }
    }
  }
)
</script>

<template>
  <Teleport to="body">
    <!-- Modal Backdrop -->
    <Transition
      enter-active-class="transition-opacity duration-150 ease-out"
      leave-active-class="transition-opacity duration-150 ease-in"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="visible && appointment"
        class="fixed inset-0 z-40 bg-slate-900/20 backdrop-blur-sm"
        @click="closeModal"
        aria-hidden="true"
      ></div>
    </Transition>

    <!-- Modal Content -->
    <Transition
      enter-active-class="transition-all duration-150 ease-out"
      leave-active-class="transition-all duration-150 ease-in"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="visible && appointment"
        ref="modalRef"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="`appointment-details-modal-title-${appointment.id}`"
      >
        <div
          class="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white shadow-xl"
          @click.stop
        >
          <!-- Header -->
          <div
            class="sticky top-0 flex items-start justify-between border-b border-slate-200 bg-white px-6 py-4"
          >
            <div>
              <div class="flex items-center gap-3">
                <h2
                  :id="`appointment-details-modal-title-${appointment.id}`"
                  class="text-xl font-semibold text-slate-900"
                >
                  Appointment Details
                </h2>

                <!-- Edit Success Badge -->
                <Transition name="fade">
                  <div
                    v-if="showEditSuccess"
                    class="inline-flex items-center gap-1.5 rounded-md bg-emerald-100 px-2 py-1 text-xs font-medium text-emerald-700"
                  >
                    <svg
                      class="h-3 w-3"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                    Changes saved
                  </div>
                </Transition>
              </div>

              <div class="mt-2 flex items-center gap-2">
                <!-- Primary Status Badge (state truth) -->
                <span
                  :class="getStatusBadgeClass(appointment.status)"
                  class="inline-flex"
                >
                  {{ appointment.status.replace('_', ' ') }}
                </span>

                <!-- WARNING BADGE: Only for past scheduled appointments -->
                <span
                  v-if="appointment.status === 'scheduled' && isPastAppointment"
                  class="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-900 ring-1 ring-amber-600/20 ring-inset"
                >
                  <!-- Clock Icon -->
                  <svg
                    class="h-3 w-3"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                  Needs Completion
                </span>

                <!-- Edit Indicator -->
                <AppointmentEditIndicator
                  v-if="appointment.edited_at && appointment.edit_count"
                  :edit-count="appointment.edit_count"
                  :edited-at="appointment.edited_at"
                />

                <!-- Save Status Indicator -->
                <div
                  v-if="isSaving || lastSaved || saveError"
                  class="flex items-center gap-1.5 text-xs"
                >
                  <!-- Saving -->
                  <template v-if="isSaving">
                    <LoadingSpinner size="sm" color="slate" />
                    <span class="text-slate-600">Saving...</span>
                  </template>

                  <!-- Saved -->
                  <template v-else-if="lastSaved && !saveError">
                    <svg
                      class="h-3 w-3 text-emerald-600"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                    <span class="text-slate-500">Saved at {{ lastSavedText }}</span>
                  </template>

                  <!-- Error -->
                  <template v-else-if="saveError">
                    <IconClose class="h-3 w-3 text-red-600" />
                    <span class="text-red-600">{{ saveError }}</span>
                  </template>
                </div>
              </div>
            </div>
            <button
              @click="closeModal"
              class="rounded-lg p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
              aria-label="Close dialog"
            >
              <IconClose class="h-5 w-5" />
            </button>
          </div>

          <!-- Body with Editable Fields -->
          <div class="space-y-4 px-6 py-6">
            <!-- Time Card (Editable) -->
            <div class="rounded-lg border border-slate-200 bg-white p-4">
              <div class="mb-3 text-sm font-medium text-slate-500">Time</div>

              <!-- Date -->
              <div class="mb-3">
                <label for="edit-date" class="block text-xs text-slate-500">
                  Date
                </label>
                <input
                  id="edit-date"
                  v-model="appointmentDate"
                  type="date"
                  aria-label="Appointment date"
                  class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                />
              </div>

              <!-- Start Time -->
              <div class="mb-3">
                <TimePickerDropdown
                  v-model="editableData.scheduled_start"
                  label="Start"
                  min-time="06:00"
                  max-time="22:00"
                  :interval="15"
                  @update:model-value="handleDateTimeChange('scheduled_start')"
                />
              </div>

              <!-- End Time -->
              <div class="mb-3">
                <TimePickerDropdown
                  v-model="editableData.scheduled_end"
                  label="End"
                  min-time="06:00"
                  max-time="22:00"
                  :interval="15"
                  @update:model-value="handleDateTimeChange('scheduled_end')"
                />
              </div>

              <!-- Duration Display & Quick Duration Pills -->
              <div class="mt-3 space-y-3">
                <!-- Duration Display -->
                <div class="text-sm text-slate-600">
                  Duration: {{ calculatedDuration }} min
                </div>

                <!-- Quick Duration Pills -->
                <div>
                  <label class="mb-2 block text-xs text-slate-500">
                    Quick Duration:
                  </label>
                  <div class="flex flex-wrap gap-2">
                    <button
                      v-for="duration in [30, 45, 60, 90]"
                      :key="duration"
                      type="button"
                      @click="setDuration(duration)"
                      :aria-label="`Set duration to ${duration} minutes`"
                      :aria-pressed="calculatedDuration === duration"
                      :class="[
                        'rounded-full px-3 py-1.5 text-sm transition-all',
                        calculatedDuration === duration
                          ? 'border border-emerald-600 bg-emerald-50 font-medium text-emerald-900'
                          : 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50',
                      ]"
                    >
                      {{ duration }} min
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <!-- Location Card (Editable) -->
            <div class="rounded-lg border border-slate-200 bg-white p-4">
              <div class="mb-2 text-sm font-medium text-slate-500">Location</div>

              <!-- Location Type -->
              <div class="mb-3">
                <label for="edit-location-type" class="block text-xs text-slate-500">
                  Type
                </label>
                <select
                  id="edit-location-type"
                  v-model="editableData.location_type"
                  @change="handleLocationTypeChange"
                  class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 capitalize focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                >
                  <option value="clinic">Clinic</option>
                  <option value="home">Home Visit</option>
                  <option value="online">Online (Video/Phone)</option>
                </select>
              </div>

              <!-- Location Details -->
              <div>
                <label for="edit-location-details" class="block text-xs text-slate-500">
                  Details
                </label>
                <input
                  id="edit-location-details"
                  v-model="editableData.location_details"
                  type="text"
                  placeholder="e.g., Zoom link, room number, address"
                  @blur="handleTextFieldBlur('location_details')"
                  class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                />
              </div>
            </div>

            <!-- P1-3: Client Information (Entire Card is Clickable) -->
            <button
              @click="emit('viewClient', appointment.client_id)"
              class="group w-full rounded-lg border border-slate-200 bg-slate-50 p-4 text-left transition-all hover:border-slate-300 hover:bg-white hover:shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
            >
              <div class="mb-2 text-sm font-medium text-slate-500">Client</div>
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                  <div
                    class="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-100 font-medium text-emerald-700 transition-colors group-hover:bg-emerald-200"
                  >
                    {{ appointment.client?.first_name?.[0] || 'C'
                    }}{{ appointment.client?.last_name?.[0] || '' }}
                  </div>
                  <div>
                    <div class="font-medium text-slate-900">
                      {{ appointment.client?.full_name || 'Unknown Client' }}
                    </div>
                    <div
                      class="flex items-center gap-1.5 text-sm font-medium text-emerald-600 group-hover:text-emerald-700"
                    >
                      View full profile
                      <svg
                        class="h-4 w-4 transition-transform group-hover:translate-x-0.5"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="2"
                          d="M9 5l7 7-7 7"
                        />
                      </svg>
                    </div>
                  </div>
                </div>
              </div>
            </button>

            <!-- Notes (Editable) -->
            <div class="rounded-lg border border-slate-200 bg-white p-4">
              <label
                for="edit-notes"
                class="mb-2 block text-sm font-medium text-slate-500"
              >
                Notes
              </label>
              <textarea
                id="edit-notes"
                v-model="editableData.notes"
                rows="4"
                placeholder="Optional notes about this appointment"
                @blur="handleTextFieldBlur('notes')"
                class="block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 placeholder-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              ></textarea>
              <p class="mt-1 text-xs text-slate-400">Changes are saved automatically</p>
            </div>

            <!-- Appointment Status Management Card -->
            <AppointmentStatusCard
              v-if="appointment"
              :appointment="appointment"
              :session-status="sessionStatus"
              @update-status="handleStatusUpdate"
              @complete-and-document="handleCompleteAndDocument"
            />

            <!-- Session Status Section (P0 Feature) -->
            <div class="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <!-- Has Session Note -->
              <div v-if="sessionStatus?.hasSession" class="flex items-start gap-3">
                <svg
                  class="h-5 w-5 shrink-0 text-emerald-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <div class="flex-1">
                  <p class="text-sm font-medium text-slate-900">
                    Session Note:
                    {{ sessionStatus.isDraft ? 'Draft' : 'Finalized' }}
                  </p>
                  <button
                    @click="emit('viewSession', sessionStatus.sessionId!)"
                    class="mt-1 text-sm font-medium text-emerald-600 transition-colors hover:text-emerald-700 focus:underline focus:outline-none"
                  >
                    {{ sessionStatus.isDraft ? 'Continue Editing →' : 'View Note →' }}
                  </button>
                </div>
              </div>

              <!-- No Session Note - Context-Aware Messaging -->
              <div v-else-if="!sessionStatus?.hasSession">
                <!-- Completed - Encourage documentation -->
                <div
                  v-if="appointment.status === 'completed'"
                  class="flex items-start gap-3"
                >
                  <svg
                    class="h-5 w-5 shrink-0 text-amber-600"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                    />
                  </svg>
                  <div>
                    <p class="text-sm font-medium text-slate-900">
                      No session note yet
                    </p>
                    <p class="mt-0.5 text-xs text-slate-600">
                      Document this appointment with SOAP notes
                    </p>
                    <button
                      @click="emit('startSessionNotes', appointment)"
                      class="mt-2 text-sm font-medium text-emerald-600 transition-colors hover:text-emerald-700 focus:underline focus:outline-none"
                    >
                      Start Session Note →
                    </button>
                  </div>
                </div>

                <!-- Scheduled - Future -->
                <div v-else-if="isFutureAppointment" class="text-sm text-slate-600">
                  <p>Session notes can be created after the appointment</p>
                </div>

                <!-- Scheduled - Past (prompt to complete) -->
                <div
                  v-else-if="isPastAppointment && appointment.status === 'scheduled'"
                  class="flex items-start gap-3"
                >
                  <svg
                    class="h-5 w-5 shrink-0 text-blue-600"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                  <div>
                    <p class="text-sm font-medium text-slate-900">
                      This appointment has ended
                    </p>
                    <p class="mt-0.5 text-xs text-slate-600">
                      Mark it as completed to create session notes
                    </p>
                  </div>
                </div>

                <!-- No-Show / Cancelled -->
                <div
                  v-else-if="['no_show', 'cancelled'].includes(appointment.status)"
                  class="text-sm text-slate-500"
                >
                  <p>
                    No session notes for
                    {{ appointment.status.replace('_', ' ') }} appointments
                  </p>
                </div>
              </div>
            </div>
          </div>

          <!-- Actions Footer -->
          <div class="sticky bottom-0 border-t border-slate-200 bg-slate-50 px-6 py-4">
            <div class="flex items-center justify-between gap-3">
              <div class="flex gap-2">
                <!-- Restore button for cancelled appointments -->
                <button
                  v-if="appointment.status === 'cancelled'"
                  @click="emit('restore', appointment)"
                  class="flex items-center gap-2 rounded-lg border border-emerald-600 bg-white px-4 py-2 text-sm font-medium text-emerald-700 transition-colors hover:bg-emerald-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
                >
                  <svg
                    class="h-4 w-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                    />
                  </svg>
                  <span>Restore Appointment</span>
                </button>

                <!-- Start Session Notes button (if has session, show View/Continue) -->
                <button
                  v-if="sessionStatus?.hasSession"
                  @click="emit('viewSession', sessionStatus.sessionId!)"
                  class="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
                >
                  {{
                    sessionStatus.isDraft
                      ? 'Continue Editing Session'
                      : 'View Session Note'
                  }}
                </button>

                <!-- Start Session Notes button (only if no session and completed) -->
                <button
                  v-else-if="appointment.status === 'completed'"
                  @click="emit('startSessionNotes', appointment)"
                  class="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
                >
                  Start Session Notes
                </button>
              </div>

              <div class="flex items-center gap-2">
                <!-- Delete button - always enabled -->
                <button
                  @click.stop="handleDeleteClick"
                  title="Delete this appointment"
                  class="flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-red-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2"
                >
                  <svg
                    class="h-4 w-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                    />
                  </svg>
                  <span>Delete</span>
                </button>

                <!-- Cancel button (only for scheduled/no_show, not completed or cancelled) -->
                <button
                  v-if="['scheduled', 'no_show'].includes(appointment.status)"
                  @click="emit('cancel', appointment)"
                  class="rounded-lg px-4 py-2 text-sm font-medium text-red-600 transition-colors hover:bg-red-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2"
                >
                  Cancel Appointment
                </button>
              </div>
            </div>

            <!-- Metadata -->
            <div
              class="mt-4 space-y-1 border-t border-slate-200 pt-4 text-xs text-slate-400"
            >
              <div>
                Created
                {{ formatDate(appointment.created_at, "MMM d, yyyy 'at' h:mm a") }}
              </div>
              <div>
                Last updated
                {{ formatDate(appointment.updated_at, "MMM d, yyyy 'at' h:mm a") }}
              </div>
              <!-- Edit Indicator -->
              <div
                v-if="hasBeenEdited"
                class="flex items-center gap-1.5 text-slate-600"
                :title="formatAbsoluteTime((appointment as any).edited_at)"
              >
                <svg
                  class="h-3 w-3"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                  />
                </svg>
                Edited
                {{ formatRelativeTime((appointment as any).edited_at) }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Delete Appointment Modal -->
    <DeleteAppointmentModal
      :appointment="appointment"
      :session-status="sessionStatus"
      :open="showDeleteModal"
      @confirm="handleDeleteConfirm"
      @cancel="handleDeleteCancel"
    />
  </Teleport>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
