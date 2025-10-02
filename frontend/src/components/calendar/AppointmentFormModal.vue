<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import type {
  AppointmentListItem,
  AppointmentFormData,
  ConflictingAppointment,
} from '@/types/calendar'
import { checkAppointmentConflicts } from '@/api/client'
import ConflictAlert from './ConflictAlert.vue'

interface Props {
  visible: boolean
  appointment?: AppointmentListItem | null
  mode: 'create' | 'edit'
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

// Validation
const errors = ref<Record<string, string>>({})

// Conflict detection state
const conflicts = ref<ConflictingAppointment[]>([])
const isCheckingConflicts = ref(false)

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

// Reset form when modal closes
watch(
  () => props.visible,
  (isVisible) => {
    if (!isVisible) {
      resetForm()
    } else if (props.mode === 'create') {
      // Set default start time to now, end time to +1 hour
      const now = new Date()
      const oneHourLater = new Date(now.getTime() + 60 * 60 * 1000)
      formData.value.scheduled_start = now.toISOString().slice(0, 16)
      formData.value.scheduled_end = oneHourLater.toISOString().slice(0, 16)
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

  isCheckingConflicts.value = true
  try {
    const response = await checkAppointmentConflicts({
      scheduled_start: startISO,
      scheduled_end: endISO,
      exclude_appointment_id: props.mode === 'edit' ? props.appointment?.id : undefined,
    })

    conflicts.value = response.has_conflict ? response.conflicting_appointments : []
  } catch (error) {
    console.error('Conflict check failed:', error)
    // Don't block user on error, just clear conflicts
    conflicts.value = []
  } finally {
    isCheckingConflicts.value = false
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

const modalTitle = computed(() =>
  props.mode === 'create' ? 'New Appointment' : 'Edit Appointment'
)

const submitButtonText = computed(() =>
  props.mode === 'create' ? 'Create' : 'Save Changes'
)

function handleViewConflict(appointmentId: string) {
  console.log('View conflict:', appointmentId)
  // TODO: Navigate to conflicting appointment or open in modal
}
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

          <!-- Form -->
          <form @submit.prevent="handleSubmit" class="space-y-6 px-6 py-6">
            <!-- Client Field -->
            <div>
              <label for="client" class="block text-sm font-medium text-slate-700">
                Client <span class="text-red-500">*</span>
              </label>
              <input
                id="client"
                v-model="formData.client_id"
                type="text"
                placeholder="Enter client ID (TODO: Replace with dropdown)"
                class="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                :class="{ 'border-red-500': errors.client_id }"
              />
              <p v-if="errors.client_id" class="mt-1 text-sm text-red-600">
                {{ errors.client_id }}
              </p>
              <p class="mt-1 text-xs text-slate-500">
                TODO (M3): Replace with searchable client dropdown
              </p>
            </div>

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

            <!-- Conflict Alert (appears below time fields when conflicts exist) -->
            <ConflictAlert
              v-if="hasConflicts"
              :conflicts="conflicts"
              @view-conflict="handleViewConflict"
            />

            <!-- Loading Indicator (during conflict check) -->
            <div
              v-else-if="isCheckingConflicts"
              class="mt-3 flex items-center gap-2 text-sm text-slate-600"
            >
              <svg
                class="h-4 w-4 animate-spin text-slate-400"
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
              <span>Checking for conflicts...</span>
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
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
