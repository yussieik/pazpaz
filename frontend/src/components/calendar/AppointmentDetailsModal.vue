<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useFocusTrap } from '@vueuse/integrations/useFocusTrap'
import { useScrollLock } from '@vueuse/core'
import type { AppointmentListItem } from '@/types/calendar'
import { formatDate, calculateDuration } from '@/utils/calendar/dateFormatters'
import { getStatusBadgeClass } from '@/utils/calendar/appointmentHelpers'
import { useAppointmentAutoSave } from '@/composables/useAppointmentAutoSave'

interface Props {
  appointment: AppointmentListItem | null
  visible: boolean
  showEditSuccess?: boolean
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'startSessionNotes', appointment: AppointmentListItem): void
  (e: 'cancel', appointment: AppointmentListItem): void
  (e: 'restore', appointment: AppointmentListItem): void
  (e: 'delete', appointment: AppointmentListItem): void
  (e: 'viewClient', clientId: string): void
  (e: 'refresh'): void // Emit when appointment is updated
}

const props = withDefaults(defineProps<Props>(), {
  showEditSuccess: false,
})
const emit = defineEmits<Emits>()

const modalRef = ref<HTMLElement>()

// H9: Focus trap for accessibility (WCAG 2.1 AA compliance)
const { activate, deactivate } = useFocusTrap(modalRef, {
  immediate: false,
  escapeDeactivates: true,
  clickOutsideDeactivates: true,
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

// Auto-save composable
const autoSave = computed(() => {
  if (!props.appointment) return null
  return useAppointmentAutoSave(props.appointment.id)
})

// Computed properties for auto-save status
const isSaving = computed(() => autoSave.value?.isSaving.value || false)
const lastSaved = computed(() => autoSave.value?.lastSaved.value || null)
const saveError = computed(() => autoSave.value?.saveError.value || null)

// Status-based edit restrictions
const isReadOnly = computed(() => {
  return props.appointment?.status === 'completed'
})

const isRestrictedEdit = computed(() => {
  // Cancelled appointments: allow notes only (for audit trail)
  return props.appointment?.status === 'cancelled'
})

const canEditTimeLocation = computed(() => {
  // Can edit time/location for scheduled/confirmed only
  return !isReadOnly.value && !isRestrictedEdit.value
})

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

/**
 * Close modal immediately
 * Auto-save will complete in the background
 */
function closeModal() {
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
 * Handle date/time change - convert to ISO and save immediately (no debounce)
 */
async function handleDateTimeChange(field: 'scheduled_start' | 'scheduled_end') {
  if (!props.appointment || !autoSave.value) return

  // Get the local datetime value from editableData
  const localDateTimeValue = editableData.value[field]

  // Convert local datetime format to ISO string for API
  const isoValue = parseDateTimeLocal(localDateTimeValue)

  try {
    // Save the ISO value to the API
    await autoSave.value.saveField(field, isoValue, false)
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
                <span
                  :class="getStatusBadgeClass(appointment.status)"
                  class="inline-flex"
                >
                  {{ appointment.status.replace('_', ' ') }}
                </span>

                <!-- Read-only badge -->
                <div
                  v-if="isReadOnly"
                  class="inline-flex items-center rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600"
                >
                  <svg
                    class="mr-1 h-3 w-3"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                    />
                  </svg>
                  Read-only
                </div>

                <!-- Save Status Indicator -->
                <div
                  v-if="isSaving || lastSaved || saveError"
                  class="flex items-center gap-1.5 text-xs"
                >
                  <!-- Saving -->
                  <template v-if="isSaving">
                    <svg
                      class="h-3 w-3 animate-spin text-slate-400"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        class="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        stroke-width="4"
                      ></circle>
                      <path
                        class="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      ></path>
                    </svg>
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
                    <svg
                      class="h-3 w-3 text-red-600"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M6 18L18 6M6 6l12 12"
                      />
                    </svg>
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
              <svg
                class="h-5 w-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>

          <!-- Body with Editable Fields -->
          <div class="space-y-4 px-6 py-6">
            <!-- Cancelled appointment info message -->
            <div
              v-if="isRestrictedEdit"
              class="rounded-md border border-amber-200 bg-amber-50 p-3"
            >
              <div class="flex">
                <svg
                  class="h-5 w-5 text-amber-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <div class="ml-3">
                  <p class="text-sm text-amber-700">
                    This appointment is cancelled. Only notes can be edited to maintain
                    the audit trail.
                  </p>
                </div>
              </div>
            </div>

            <!-- Time Card (Editable) -->
            <div class="rounded-lg border border-slate-200 bg-white p-4">
              <div class="mb-2 text-sm font-medium text-slate-500">Time</div>

              <!-- Start Time -->
              <div class="mb-3">
                <label for="edit-start-time" class="block text-xs text-slate-500">
                  Start
                </label>
                <input
                  id="edit-start-time"
                  v-model="editableData.scheduled_start"
                  type="datetime-local"
                  :disabled="!canEditTimeLocation"
                  @change="handleDateTimeChange('scheduled_start')"
                  class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500"
                />
              </div>

              <!-- End Time -->
              <div>
                <label for="edit-end-time" class="block text-xs text-slate-500">
                  End
                </label>
                <input
                  id="edit-end-time"
                  v-model="editableData.scheduled_end"
                  type="datetime-local"
                  :disabled="!canEditTimeLocation"
                  @change="handleDateTimeChange('scheduled_end')"
                  class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500"
                />
              </div>

              <!-- Duration Display -->
              <div class="mt-2 text-sm text-slate-400">
                Duration:
                {{
                  calculateDuration(
                    editableData.scheduled_start,
                    editableData.scheduled_end
                  )
                }}
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
                  :disabled="!canEditTimeLocation"
                  @change="handleLocationTypeChange"
                  class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 capitalize focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500"
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
                  :disabled="!canEditTimeLocation"
                  placeholder="e.g., Zoom link, room number, address"
                  @blur="handleTextFieldBlur('location_details')"
                  class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500"
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
                :disabled="isReadOnly"
                placeholder="Optional notes about this appointment"
                @blur="handleTextFieldBlur('notes')"
                class="block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 placeholder-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500"
              ></textarea>
              <p class="mt-1 text-xs text-slate-400">
                <template v-if="!isReadOnly">Changes are saved automatically</template>
                <template v-else>Read-only (completed appointment)</template>
              </p>
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

                <!-- Start Session Notes button (only for scheduled) -->
                <button
                  v-if="appointment.status === 'scheduled'"
                  @click="emit('startSessionNotes', appointment)"
                  class="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700"
                >
                  Start Session Notes
                </button>
              </div>

              <div class="flex items-center gap-2">
                <!-- Delete button (only for scheduled/cancelled, not completed) -->
                <button
                  v-if="appointment.status !== 'completed'"
                  @click="emit('delete', appointment)"
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

                <!-- Cancel button (only for non-cancelled) -->
                <button
                  v-if="appointment.status !== 'cancelled'"
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
            </div>
          </div>
        </div>
      </div>
    </Transition>
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
