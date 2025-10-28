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
import TimePickerDropdown from '@/components/common/TimePickerDropdown.vue'
import IconClose from '@/components/icons/IconClose.vue'
import IconWarning from '@/components/icons/IconWarning.vue'
import {
  formatDateTimeForInput,
  addMinutes,
  getDurationMinutes,
  extractDate,
} from '@/utils/calendar/dateFormatters'
import { useClientsStore } from '@/stores/clients'
import { useDeviceType } from '@/composables/useDeviceType'

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

// Clients store for auto-filling address
const clientsStore = useClientsStore()

// Device type detection for mobile keyboard behavior
const { shouldDeferKeyboard } = useDeviceType()

// Form state
const formData = ref<AppointmentFormData>({
  client_id: '',
  scheduled_start: '',
  scheduled_end: '',
  location_type: 'clinic',
  location_details: '',
  notes: '',
})

// Separate date field for the date picker (YYYY-MM-DD format)
const appointmentDate = ref<string>('')

// Template refs for auto-focus
const clientComboboxRef = ref<InstanceType<typeof ClientCombobox>>()
const dateInputRef = ref<HTMLInputElement>()
const locationSelectRef = ref<HTMLSelectElement>()

// Validation
const errors = ref<Record<string, string>>({})

// Conflict detection state
const conflicts = ref<ConflictingAppointment[]>([])
const isCheckingConflicts = ref(false)
const isInitialLoad = ref(true)
const showAvailableIndicator = ref(false)

// Address auto-fill state
const showAddressHint = ref(false)

// Duration management
const previousStartTime = ref<string>('')
const DEFAULT_DURATION_MINUTES = 60

// Platform detection for keyboard shortcuts (using userAgent since platform is deprecated)
const isMac = computed(() => navigator.userAgent.toUpperCase().indexOf('MAC') >= 0)
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

// Date/time utility functions imported from @/utils/calendar/dateFormatters

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
        // Use pre-filled date/time from calendar click
        formData.value.scheduled_start = formatDateTimeForInput(
          props.prefillDateTime.start
        )
        formData.value.scheduled_end = formatDateTimeForInput(props.prefillDateTime.end)
      } else {
        // Default to now with 60-minute duration
        const now = new Date()
        formData.value.scheduled_start = formatDateTimeForInput(now)
        formData.value.scheduled_end = addMinutes(
          formData.value.scheduled_start,
          DEFAULT_DURATION_MINUTES
        )
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
        // 2. If client IS pre-filled but Date is empty → Focus Date picker
        // 3. If both client and Date are pre-filled → Focus Location dropdown
        if (!formData.value.client_id) {
          const inputElement = clientComboboxRef.value?.inputRef
          if (inputElement) {
            inputElement.focus()

            // On mobile: prevent keyboard until tap (readonly trick)
            if (shouldDeferKeyboard.value) {
              inputElement.setAttribute('readonly', 'readonly')

              // Remove readonly on first user interaction
              inputElement.addEventListener(
                'click',
                () => {
                  inputElement.removeAttribute('readonly')
                },
                { once: true }
              )
            }
          }
        } else if (!appointmentDate.value) {
          dateInputRef.value?.focus()
        } else {
          locationSelectRef.value?.focus()
        }
      })
    } else if (props.mode === 'edit') {
      // For edit mode, focus the first editable field (client combobox)
      nextTick(() => {
        const inputElement = clientComboboxRef.value?.inputRef
        if (inputElement) {
          inputElement.focus()

          // On mobile: prevent keyboard until tap (readonly trick)
          if (shouldDeferKeyboard.value) {
            inputElement.setAttribute('readonly', 'readonly')

            // Remove readonly on first user interaction
            inputElement.addEventListener(
              'click',
              () => {
                inputElement.removeAttribute('readonly')
              },
              { once: true }
            )
          }
        }
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

// Watch start time changes to preserve duration
watch(
  () => formData.value.scheduled_start,
  (newStart, oldStart) => {
    // Skip if:
    // 1. Initial load or form reset (oldStart is empty)
    // 2. No end time set yet
    if (!oldStart || !formData.value.scheduled_end || isInitialLoad.value) {
      previousStartTime.value = newStart
      return
    }

    // Calculate current duration from old start to end
    const currentDuration = getDurationMinutes(oldStart, formData.value.scheduled_end)

    // Apply same duration to new start time
    formData.value.scheduled_end = addMinutes(newStart, currentDuration)

    // Store for next change
    previousStartTime.value = newStart
  }
)

// Watch time fields for conflict detection
watch(
  () => [formData.value.scheduled_start, formData.value.scheduled_end],
  () => {
    checkConflicts()
  }
)

// Watch for client + location type changes to auto-fill address
watch(
  () => [formData.value.client_id, formData.value.location_type],
  ([clientId, locationType]) => {
    // Only auto-fill for home visits
    if ((locationType === 'home' || locationType === 'home_visit') && clientId) {
      // Find selected client in the store
      const selectedClient = clientsStore.clients.find((c) => c.id === clientId)

      if (selectedClient?.address) {
        // Only auto-fill if location_details is empty (don't overwrite manual edits or existing data)
        if (!formData.value.location_details) {
          formData.value.location_details = selectedClient.address

          // Show subtle hint
          showAddressHint.value = true
          setTimeout(() => {
            showAddressHint.value = false
          }, 3000) // Fade after 3 seconds
        }
      } else if (!formData.value.location_details) {
        // Client has no address saved, keep field empty
        // (Don't clear if user manually entered something)
      }
    }
    // For non-home visits, preserve existing location_details
    // (Don't clear manually entered clinic names, zoom links, etc.)
  },
  { deep: true }
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

const calculatedDuration = computed(() => {
  if (!formData.value.scheduled_start || !formData.value.scheduled_end) return 0
  return getDurationMinutes(
    formData.value.scheduled_start,
    formData.value.scheduled_end
  )
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

/**
 * Set duration by adjusting end time relative to start time
 */
function setDuration(minutes: number) {
  if (!formData.value.scheduled_start) return

  formData.value.scheduled_end = addMinutes(formData.value.scheduled_start, minutes)
}

// extractDate utility function imported from @/utils/calendar/dateFormatters

/**
 * Watch for date changes and update start/end times accordingly
 */
watch(appointmentDate, (newDate) => {
  if (!newDate || !formData.value.scheduled_start) return

  // Extract time from current start/end
  const startTime = new Date(formData.value.scheduled_start)
  const endTime = new Date(formData.value.scheduled_end)

  // Create new datetime with new date and existing times
  const newStart = new Date(newDate)
  newStart.setHours(startTime.getHours(), startTime.getMinutes(), 0, 0)

  const newEnd = new Date(newDate)
  newEnd.setHours(endTime.getHours(), endTime.getMinutes(), 0, 0)

  formData.value.scheduled_start = formatDateTimeForInput(newStart)
  formData.value.scheduled_end = formatDateTimeForInput(newEnd)
})

/**
 * Sync appointmentDate when formData.scheduled_start changes
 */
watch(
  () => formData.value.scheduled_start,
  (newStart) => {
    if (newStart) {
      appointmentDate.value = extractDate(newStart)
    }
  }
)
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
            class="sticky top-0 flex items-center justify-between border-b border-slate-200 bg-white px-5 py-4 sm:px-6"
          >
            <h2
              id="appointment-form-modal-title"
              class="text-lg font-semibold text-slate-900 sm:text-xl"
            >
              {{ modalTitle }}
            </h2>
            <button
              @click="closeModal"
              class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 sm:min-h-0 sm:min-w-0 sm:p-2"
              aria-label="Close dialog"
            >
              <IconClose class="h-6 w-6 sm:h-5 sm:w-5" />
            </button>
          </div>

          <!-- Persistent Status Area - always reserves space to prevent layout shift -->
          <div class="min-h-10 px-5 pt-4 transition-all duration-200 sm:px-6">
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
                <IconWarning size="md" class="flex-shrink-0 text-amber-600" />
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
          <form
            @submit.prevent="handleSubmit"
            class="space-y-6 px-5 pb-6 sm:space-y-6 sm:px-6"
          >
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
                  <IconWarning size="md" class="flex-shrink-0 text-amber-600" />
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

            <!-- Date -->
            <div>
              <label
                for="appointment-date"
                class="mb-1.5 block text-sm font-medium text-slate-900"
              >
                Date <span class="ml-0.5 text-red-500">*</span>
              </label>
              <input
                id="appointment-date"
                ref="dateInputRef"
                v-model="appointmentDate"
                type="date"
                aria-label="Appointment date"
                class="mt-1 block min-h-[44px] w-full rounded-lg border border-slate-300 px-3 py-2 text-base text-slate-900 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none sm:text-sm"
              />
            </div>

            <!-- Time Pickers -->
            <div class="grid grid-cols-1 gap-6 sm:grid-cols-2">
              <!-- Start Time -->
              <TimePickerDropdown
                v-model="formData.scheduled_start"
                label="Start Time *"
                :error="errors.scheduled_start"
                min-time="06:00"
                max-time="22:00"
                :interval="15"
              />

              <!-- End Time -->
              <TimePickerDropdown
                v-model="formData.scheduled_end"
                label="End Time *"
                :error="errors.scheduled_end"
                min-time="06:00"
                max-time="22:00"
                :interval="15"
              />
            </div>

            <!-- Duration Display & Quick Duration Pills -->
            <div v-if="formData.scheduled_start" class="space-y-3">
              <!-- Duration Display -->
              <div class="text-sm text-slate-600">
                Duration: {{ calculatedDuration }} min
              </div>

              <!-- Quick Duration Pills -->
              <div>
                <label class="mb-2 block text-sm font-medium text-slate-700">
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

            <!-- Location Type -->
            <div>
              <label
                for="location-type"
                class="mb-1.5 block text-sm font-medium text-slate-900"
              >
                Location Type <span class="ml-0.5 text-red-500">*</span>
              </label>
              <select
                id="location-type"
                ref="locationSelectRef"
                v-model="formData.location_type"
                class="mt-1 block min-h-[44px] w-full rounded-lg border border-slate-300 px-3 py-2 text-base text-slate-900 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none sm:text-sm"
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
                class="mb-1.5 block text-sm font-medium text-slate-900"
              >
                Location Details
              </label>
              <input
                id="location-details"
                v-model="formData.location_details"
                v-rtl
                type="text"
                placeholder="e.g., Zoom link, room number, address"
                class="mt-1 block min-h-[44px] w-full rounded-lg border border-slate-300 px-3 py-2 text-base text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none sm:text-sm"
              />

              <!-- Address Auto-Fill Hint -->
              <Transition
                enter-active-class="transition-opacity duration-200"
                leave-active-class="transition-opacity duration-200"
                enter-from-class="opacity-0"
                leave-to-class="opacity-0"
              >
                <div
                  v-if="showAddressHint"
                  class="mt-1.5 flex items-center gap-2 rounded-md bg-emerald-50 px-3 py-2 text-xs text-emerald-700"
                  role="status"
                  aria-live="polite"
                >
                  <svg
                    class="h-4 w-4 flex-shrink-0"
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
                  <span>Using address from client profile</span>
                </div>
              </Transition>
            </div>

            <!-- Notes -->
            <div>
              <label
                for="notes"
                class="mb-1.5 block text-sm font-medium text-slate-900"
              >
                Notes
              </label>
              <textarea
                id="notes"
                v-model="formData.notes"
                v-rtl
                rows="6"
                placeholder="Optional notes about this appointment"
                class="sm:rows-3 mt-1 block min-h-[120px] w-full rounded-lg border border-slate-300 px-3 py-2 text-base text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none sm:text-sm"
              ></textarea>
            </div>
          </form>

          <!-- Footer -->
          <div
            class="sticky bottom-0 border-t border-slate-200 bg-slate-50 px-5 py-4 sm:px-6"
          >
            <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-end">
              <button
                @click="closeModal"
                type="button"
                class="order-2 inline-flex min-h-[44px] w-full items-center justify-center rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 sm:order-1 sm:w-auto"
              >
                Cancel
              </button>
              <button
                @click="handleSubmit"
                type="submit"
                :class="[
                  'order-1 inline-flex min-h-[44px] w-full items-center justify-center rounded-lg px-4 py-2.5 text-sm font-medium text-white transition-colors sm:order-2 sm:w-auto',
                  hasConflicts
                    ? 'bg-amber-600 hover:bg-amber-700'
                    : 'bg-emerald-600 hover:bg-emerald-700',
                ]"
              >
                <span v-if="hasConflicts">⚠️ {{ submitButtonText }} Anyway</span>
                <span v-else>{{ submitButtonText }}</span>
              </button>
            </div>
            <p class="mt-3 hidden text-center text-xs text-slate-500 sm:block">
              or press
              <kbd
                class="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-700"
                >{{ modifierKey }}Enter</kbd
              >
            </p>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
