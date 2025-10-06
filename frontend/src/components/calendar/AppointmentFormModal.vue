<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import type {
  AppointmentListItem,
  AppointmentFormData,
  ConflictingAppointment,
} from '@/types/calendar'
import { checkAppointmentConflicts } from '@/api/client'
import ClientCombobox from '@/components/clients/ClientCombobox.vue'

interface Props {
  visible: boolean
  appointment?: AppointmentListItem | null
  mode: 'create' | 'edit'
  prefillDateTime?: { start: Date; end: Date } | null
  prefillClientId?: string | null
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'submit', data: AppointmentFormData): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// Form state
const formData = ref<AppointmentFormData>({
  client_id: '',
  scheduled_start: '',
  scheduled_end: '',
  location_type: 'clinic',
  location_details: '',
  notes: '',
})

// Template refs for auto-focus
const clientComboboxRef = ref<InstanceType<typeof ClientCombobox>>()
const startTimeInputRef = ref<HTMLInputElement>()
const locationSelectRef = ref<HTMLSelectElement>()

// Validation
const errors = ref<Record<string, string>>({})

// Conflict detection state
const conflicts = ref<ConflictingAppointment[]>([])
const isCheckingConflicts = ref(false)
const isInitialLoad = ref(true)
const showAvailableIndicator = ref(false)

// Platform detection for keyboard shortcuts
const isMac = computed(() => navigator.platform.toUpperCase().indexOf('MAC') >= 0)
const modifierKey = computed(() => (isMac.value ? '⌘' : 'Ctrl'))

// Watch for appointment changes (edit mode)
watch(
  () => props.appointment,
  (newAppointment) => {
    if (newAppointment && props.mode === 'edit') {
      formData.value = {
        client_id: newAppointment.client_id,
        scheduled_start: newAppointment.scheduled_start,
        scheduled_end: newAppointment.scheduled_end,
        location_type: newAppointment.location_type,
        location_details: newAppointment.location_details || '',
        notes: newAppointment.notes || '',
      }
    }
  },
  { immediate: true }
)

/**
 * Helper: Format Date to datetime-local input format
 */
function formatDateTimeForInput(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  return `${year}-${month}-${day}T${hours}:${minutes}`
}

// Reset form when modal closes or set defaults when opening
watch(
  () => props.visible,
  (isVisible) => {
    if (!isVisible) {
      resetForm()
    } else if (props.mode === 'create') {
      // Mark as initial load to prevent showing conflict check on first open
      isInitialLoad.value = true

      // Reset form to ensure clean state
      // Only preserve client_id if explicitly provided via prefillClientId
      formData.value.client_id = props.prefillClientId || ''
      formData.value.location_details = ''
      formData.value.notes = ''

      if (props.prefillDateTime) {
        // Use pre-filled date/time from calendar double-click
        formData.value.scheduled_start = formatDateTimeForInput(
          props.prefillDateTime.start
        )
        formData.value.scheduled_end = formatDateTimeForInput(props.prefillDateTime.end)
      } else {
        // Default to now + 1 hour (existing behavior for "+ New Appointment" button)
        const now = new Date()
        const oneHourLater = new Date(now.getTime() + 60 * 60 * 1000)
        formData.value.scheduled_start = formatDateTimeForInput(now)
        formData.value.scheduled_end = formatDateTimeForInput(oneHourLater)
      }

      // Set other defaults
      formData.value.location_type = 'clinic'

      // After initial form data is set, mark as no longer initial load
      // Use nextTick to ensure form data watchers have run first
      setTimeout(() => {
        isInitialLoad.value = false
      }, 100)

      // Auto-focus: Focus the first appropriate field based on context
      nextTick(() => {
        // Context-aware focus logic:
        // 1. If client is NOT pre-filled → Focus Client combobox
        // 2. If client IS pre-filled but Start Time is empty → Focus Start Time picker
        // 3. If both client and Start Time are pre-filled → Focus Location dropdown
        if (!formData.value.client_id) {
          clientComboboxRef.value?.inputRef?.focus()
        } else if (!formData.value.scheduled_start) {
          startTimeInputRef.value?.focus()
        } else {
          locationSelectRef.value?.focus()
        }
      })
    } else if (props.mode === 'edit') {
      // For edit mode, focus the first editable field (client combobox)
      nextTick(() => {
        clientComboboxRef.value?.inputRef?.focus()
      })
    }
  }
)

function resetForm() {
  formData.value = {
    client_id: '',
    scheduled_start: '',
    scheduled_end: '',
    location_type: 'clinic',
    location_details: '',
    notes: '',
  }
  errors.value = {}
  conflicts.value = []
  isCheckingConflicts.value = false
  isInitialLoad.value = true
  showAvailableIndicator.value = false
}

function validate(): boolean {
  errors.value = {}

  if (!formData.value.client_id) {
    errors.value.client_id = 'Client is required'
  }
  if (!formData.value.scheduled_start) {
    errors.value.scheduled_start = 'Start time is required'
  }
  if (!formData.value.scheduled_end) {
    errors.value.scheduled_end = 'End time is required'
  }

  // Validate start < end
  if (formData.value.scheduled_start && formData.value.scheduled_end) {
    if (
      new Date(formData.value.scheduled_start) >= new Date(formData.value.scheduled_end)
    ) {
      errors.value.scheduled_end = 'End time must be after start time'
    }
  }

  return Object.keys(errors.value).length === 0
}

function handleSubmit() {
  if (!validate()) return

  emit('submit', formData.value)
  // Note: Parent component (CalendarView) handles closing the modal
  // This prevents race conditions and allows parent to show errors if needed
}

function closeModal() {
  emit('update:visible', false)
}

function handleKeydown(e: KeyboardEvent) {
  // Check for ⌘Enter (macOS) or Ctrl+Enter (Windows/Linux) to submit form
  const isSubmitShortcut = (e.metaKey || e.ctrlKey) && e.key === 'Enter'

  if (isSubmitShortcut && props.visible) {
    e.preventDefault()
    handleSubmit()
    return
  }

  // Escape to close modal
  if (e.key === 'Escape' && props.visible) {
    e.preventDefault()
    closeModal()
  }
}

// Mount global escape handler for modal
onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

// Debounced conflict check (500ms)
const checkConflicts = useDebounceFn(async () => {
  // Only check if both start and end times are set
  if (!formData.value.scheduled_start || !formData.value.scheduled_end) {
    conflicts.value = []
    return
  }

  // Convert datetime-local format to ISO 8601
  const startISO = new Date(formData.value.scheduled_start).toISOString()
  const endISO = new Date(formData.value.scheduled_end).toISOString()
  const wasInitialLoad = isInitialLoad.value

  // Threshold-based loading indicator: "Silent-Fast, Feedback-Slow"
  // Fast checks (<400ms): Silent, no loading indicator
  // Slow checks (>400ms): Show loading indicator for minimum 600ms
  const FEEDBACK_DELAY = 400 // Only show loading if check takes longer than this
  const MIN_DISPLAY_TIME = 600 // Once shown, keep visible for smooth transition

  let showLoadingTimer: number | null = null
  let loadingShownAt: number | null = null

  // Schedule loading indicator to appear after FEEDBACK_DELAY
  // (unless check completes first - typical case)
  if (!wasInitialLoad) {
    showLoadingTimer = window.setTimeout(() => {
      isCheckingConflicts.value = true
      loadingShownAt = Date.now()
    }, FEEDBACK_DELAY)
  }

  try {
    const response = await checkAppointmentConflicts({
      scheduled_start: startISO,
      scheduled_end: endISO,
      exclude_appointment_id: props.mode === 'edit' ? props.appointment?.id : undefined,
    })

    conflicts.value = response.has_conflict ? response.conflicting_appointments : []

    // Show brief "available" indicator only after initial check if no conflicts
    if (wasInitialLoad && !response.has_conflict && props.mode === 'create') {
      showAvailableIndicator.value = true
      // Auto-hide after 2 seconds
      setTimeout(() => {
        showAvailableIndicator.value = false
      }, 2000)
    }
  } catch (error) {
    console.error('Conflict check failed:', error)
    // Don't block user on error, just clear conflicts
    conflicts.value = []
  } finally {
    // If loading was shown, ensure it displays for minimum time (smooth transition)
    if (loadingShownAt) {
      const displayDuration = Date.now() - loadingShownAt
      const remainingTime = Math.max(0, MIN_DISPLAY_TIME - displayDuration)

      await new Promise((resolve) => setTimeout(resolve, remainingTime))
    }

    // Cancel scheduled loading indicator if check completed fast
    if (showLoadingTimer !== null) {
      clearTimeout(showLoadingTimer)
    }

    isCheckingConflicts.value = false

    // Mark initial load complete after first check
    if (wasInitialLoad) {
      isInitialLoad.value = false
    }
  }
}, 500)

// Watch time fields for changes
watch(
  () => [formData.value.scheduled_start, formData.value.scheduled_end],
  () => {
    checkConflicts()
  }
)

// Computed properties
const hasConflicts = computed(() => conflicts.value.length > 0)

const firstConflict = computed(() => conflicts.value[0] || null)

const modalTitle = computed(() =>
  props.mode === 'create' ? 'New Appointment' : 'Edit Appointment'
)

const submitButtonText = computed(() =>
  props.mode === 'create' ? 'Create' : 'Save Changes'
)

const isPastAppointment = computed(() => {
  if (!formData.value.scheduled_start) return false
  return new Date(formData.value.scheduled_start) < new Date()
})

// Helper functions for formatting conflict details in status area
function formatTime(isoDatetime: string): string {
  try {
    const date = new Date(isoDatetime)
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    })
  } catch (error) {
    console.error('Error formatting time:', error)
    return isoDatetime
  }
}

function formatTimeRange(start: string, end: string): string {
  return `${formatTime(start)} - ${formatTime(end)}`
}

function getLocationLabel(locationType: string): string {
  const labels: Record<string, string> = {
    clinic: 'Clinic',
    home: 'Home Visit',
    online: 'Online',
  }
  return labels[locationType] || locationType
}

// Computed property for client lock state
const isClientLocked = computed(() => {
  return props.mode === 'create' && !!props.prefillClientId
})
</script>

<template>
  <Teleport to="body">
    <!-- Backdrop -->
    <Transition
      enter-active-class="transition-opacity duration-150 ease-out"
      leave-active-class="transition-opacity duration-150 ease-in"
      enter-from-class="opacity-0"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="visible"
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
        v-if="visible"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="`appointment-form-modal-title`"
      >
        <div
          class="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white shadow-xl"
          @click.stop
        >
          <!-- Header -->
          <div
            class="sticky top-0 flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4"
          >
            <h2
              id="appointment-form-modal-title"
              class="text-xl font-semibold text-slate-900"
            >
              {{ modalTitle }}
            </h2>
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

          <!-- Persistent Status Area - always reserves space to prevent layout shift -->
          <div class="min-h-10 px-6 pt-4 transition-all duration-200">
            <!-- Loading State (only when user edits times, NOT initial load) -->
            <div
              v-if="isCheckingConflicts && !isInitialLoad"
              class="flex items-center gap-2 text-sm text-slate-600"
              role="status"
              aria-live="polite"
            >
              <svg
                class="h-4 w-4 animate-spin text-slate-400"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                aria-hidden="true"
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
              <span>Checking availability...</span>
            </div>

            <!-- Conflict Warning (amber styling, non-blocking) -->
            <div
              v-else-if="hasConflicts"
              role="alert"
              aria-live="polite"
              class="rounded-lg border border-amber-200 bg-amber-50 p-3"
            >
              <div class="flex gap-3">
                <svg
                  class="h-5 w-5 flex-shrink-0 text-amber-600"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
                <div class="flex-1">
                  <p class="text-sm font-semibold text-amber-900">
                    Time slot overlap detected
                  </p>
                  <p class="mt-1 text-sm text-amber-700">
                    {{
                      conflicts.length === 1
                        ? '1 existing appointment'
                        : `${conflicts.length} existing appointments`
                    }}
                    conflict with this time slot.
                  </p>
                  <!-- Show first conflict details inline for quick reference -->
                  <div v-if="firstConflict" class="mt-2 text-xs text-amber-700">
                    <span class="font-medium">{{
                      formatTimeRange(
                        firstConflict.scheduled_start,
                        firstConflict.scheduled_end
                      )
                    }}</span>
                    <span class="mx-1">&bull;</span>
                    <span>Client: {{ firstConflict.client_initials }}</span>
                    <span class="mx-1">&bull;</span>
                    <span>{{ getLocationLabel(firstConflict.location_type) }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Available Indicator (optional, brief success state) -->
            <Transition
              enter-active-class="transition-all duration-200 ease-out"
              leave-active-class="transition-all duration-200 ease-in"
              enter-from-class="opacity-0 scale-95"
              enter-to-class="opacity-100 scale-100"
              leave-from-class="opacity-100 scale-100"
              leave-to-class="opacity-0 scale-95"
            >
              <div
                v-if="showAvailableIndicator"
                class="flex items-center gap-2 text-sm text-emerald-700"
                role="status"
                aria-live="polite"
              >
                <svg
                  class="h-4 w-4 text-emerald-600"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <span>Time slot available</span>
              </div>
            </Transition>
          </div>

          <!-- Form -->
          <form @submit.prevent="handleSubmit" class="space-y-6 px-6 pb-6">
            <!-- Past Appointment Warning -->
            <Transition
              enter-active-class="transition-all duration-150 ease-out"
              leave-active-class="transition-all duration-150 ease-in"
              enter-from-class="opacity-0 max-h-0"
              enter-to-class="opacity-100 max-h-20"
              leave-from-class="opacity-100 max-h-20"
              leave-to-class="opacity-0 max-h-0"
            >
              <div
                v-if="isPastAppointment && mode === 'create'"
                class="overflow-hidden rounded-md border border-amber-200 bg-amber-50 p-3"
              >
                <div class="flex gap-2">
                  <svg
                    class="h-5 w-5 flex-shrink-0 text-amber-600"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                    />
                  </svg>
                  <p class="text-sm text-amber-800">
                    This appointment is in the past. You can still create it if you're
                    logging a past session.
                  </p>
                </div>
              </div>
            </Transition>

            <!-- Client Field - Searchable Combobox -->
            <ClientCombobox
              ref="clientComboboxRef"
              v-model="formData.client_id"
              :disabled="isClientLocked"
              :error="errors.client_id"
              :help-text="isClientLocked ? 'Client is pre-selected' : undefined"
            />

            <!-- Date and Time -->
            <div class="grid grid-cols-1 gap-6 sm:grid-cols-2">
              <!-- Start Time -->
              <div>
                <label
                  for="start-time"
                  class="block text-sm font-medium text-slate-700"
                >
                  Start Time <span class="text-red-500">*</span>
                </label>
                <input
                  id="start-time"
                  ref="startTimeInputRef"
                  v-model="formData.scheduled_start"
                  type="datetime-local"
                  class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                  :class="{ 'border-red-500': errors.scheduled_start }"
                />
                <p v-if="errors.scheduled_start" class="mt-1 text-sm text-red-600">
                  {{ errors.scheduled_start }}
                </p>
              </div>

              <!-- End Time -->
              <div>
                <label for="end-time" class="block text-sm font-medium text-slate-700">
                  End Time <span class="text-red-500">*</span>
                </label>
                <input
                  id="end-time"
                  v-model="formData.scheduled_end"
                  type="datetime-local"
                  class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                  :class="{ 'border-red-500': errors.scheduled_end }"
                />
                <p v-if="errors.scheduled_end" class="mt-1 text-sm text-red-600">
                  {{ errors.scheduled_end }}
                </p>
              </div>
            </div>

            <!-- Location Type -->
            <div>
              <label
                for="location-type"
                class="block text-sm font-medium text-slate-700"
              >
                Location Type <span class="text-red-500">*</span>
              </label>
              <select
                id="location-type"
                ref="locationSelectRef"
                v-model="formData.location_type"
                class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              >
                <option value="clinic">Clinic</option>
                <option value="home">Home Visit</option>
                <option value="online">Online (Video/Phone)</option>
              </select>
            </div>

            <!-- Location Details -->
            <div>
              <label
                for="location-details"
                class="block text-sm font-medium text-slate-700"
              >
                Location Details
              </label>
              <input
                id="location-details"
                v-model="formData.location_details"
                type="text"
                placeholder="e.g., Zoom link, room number, address"
                class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
            </div>

            <!-- Notes -->
            <div>
              <label for="notes" class="block text-sm font-medium text-slate-700">
                Notes
              </label>
              <textarea
                id="notes"
                v-model="formData.notes"
                rows="3"
                placeholder="Optional notes about this appointment"
                class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              ></textarea>
            </div>
          </form>

          <!-- Footer -->
          <div
            class="sticky bottom-0 flex items-center justify-end gap-3 border-t border-slate-200 bg-slate-50 px-6 py-4"
          >
            <button
              @click="closeModal"
              type="button"
              class="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
            >
              Cancel
            </button>
            <div class="flex flex-col items-center gap-2">
              <button
                @click="handleSubmit"
                type="submit"
                :class="[
                  'rounded-lg px-4 py-2 text-sm font-medium text-white transition-colors',
                  hasConflicts
                    ? 'bg-amber-600 hover:bg-amber-700'
                    : 'bg-emerald-600 hover:bg-emerald-700',
                ]"
              >
                <span v-if="hasConflicts">⚠️ {{ submitButtonText }} Anyway</span>
                <span v-else>{{ submitButtonText }}</span>
              </button>
              <p class="text-xs text-slate-500">
                or press
                <kbd
                  class="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700"
                  >{{ modifierKey }}Enter</kbd
                >
              </p>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
