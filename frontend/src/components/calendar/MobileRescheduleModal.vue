<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from '@/composables/useI18n'
import type { AppointmentListItem } from '@/types/calendar'
import {
  formatTimeRange,
  getAppointmentDuration,
  calculateEndTime,
} from '@/utils/dragHelpers'
import IconClose from '@/components/icons/IconClose.vue'

const { t } = useI18n()

/**
 * Mobile Reschedule Modal
 *
 * Time picker modal for mobile/touch devices (<768px).
 * Uses native date/time pickers for familiar UX.
 *
 * Features:
 * - Native date and time inputs
 * - Preserves appointment duration
 * - Validates new time against conflicts
 * - Responsive design for small screens
 */

interface Props {
  visible: boolean
  appointment: AppointmentListItem | null
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'reschedule', data: { newStart: Date; newEnd: Date }): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// Form state
const selectedDate = ref('')
const selectedTime = ref('')
const duration = ref(0)

/**
 * Watch for appointment changes to initialize form
 */
watch(
  () => props.appointment,
  (appointment) => {
    if (appointment) {
      const start = new Date(appointment.scheduled_start)
      const end = new Date(appointment.scheduled_end)

      // Set date (YYYY-MM-DD format for input[type="date"])
      selectedDate.value = start.toISOString().split('T')[0] ?? ''

      // Set time (HH:MM format for input[type="time"])
      const hours = start.getHours().toString().padStart(2, '0')
      const minutes = start.getMinutes().toString().padStart(2, '0')
      selectedTime.value = `${hours}:${minutes}`

      // Calculate duration
      duration.value = getAppointmentDuration(start, end)
    }
  },
  { immediate: true }
)

/**
 * Current appointment time display
 */
const currentTimeDisplay = computed(() => {
  if (!props.appointment) return ''
  return formatTimeRange(
    props.appointment.scheduled_start,
    props.appointment.scheduled_end
  )
})

/**
 * New appointment time preview
 */
const newTimePreview = computed(() => {
  if (!selectedDate.value || !selectedTime.value) return ''

  const [hours, minutes] = selectedTime.value.split(':').map(Number)
  const newStart = new Date(selectedDate.value)
  newStart.setHours(hours ?? 0, minutes ?? 0, 0, 0)

  const newEnd = calculateEndTime(newStart, duration.value ?? 60)

  return formatTimeRange(newStart, newEnd)
})

/**
 * Is form valid
 */
const isFormValid = computed(() => {
  return !!selectedDate.value && !!selectedTime.value
})

/**
 * Handle reschedule
 */
function handleReschedule() {
  if (!isFormValid.value || !selectedDate.value || !selectedTime.value) return

  const [hours, minutes] = selectedTime.value.split(':').map(Number)
  const newStart = new Date(selectedDate.value)
  newStart.setHours(hours ?? 0, minutes ?? 0, 0, 0)

  const newEnd = calculateEndTime(newStart, duration.value ?? 60)

  emit('reschedule', { newStart, newEnd })
  handleClose()
}

/**
 * Handle close
 */
function handleClose() {
  emit('update:visible', false)
}

/**
 * Get today's date in YYYY-MM-DD format
 */
function getTodayDate(): string {
  return new Date().toISOString().split('T')[0] ?? ''
}
</script>

<template>
  <Transition name="modal-fade">
    <div
      v-if="visible && appointment"
      class="fixed inset-0 z-50 flex items-end justify-center bg-black/40 sm:items-center sm:p-4"
      @click.self="handleClose"
    >
      <!-- Modal -->
      <div
        class="w-full max-w-lg rounded-t-2xl bg-white shadow-2xl sm:rounded-2xl"
        role="dialog"
        aria-modal="true"
        aria-labelledby="reschedule-title"
      >
        <!-- Header -->
        <div class="border-b border-gray-200 px-6 py-4">
          <div class="flex items-center justify-between">
            <h3 id="reschedule-title" class="text-lg font-semibold text-gray-900">
              {{ t('calendar.mobileRescheduleModal.title') }}
            </h3>
            <button
              type="button"
              class="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:outline-none"
              @click="handleClose"
              :aria-label="t('calendar.mobileRescheduleModal.closeDialog')"
            >
              <IconClose class="h-6 w-6" />
            </button>
          </div>
        </div>

        <!-- Content -->
        <div class="px-6 py-4">
          <!-- Client info -->
          <div class="mb-4 rounded-lg bg-blue-50 p-4">
            <p class="text-sm font-medium text-blue-900">
              {{
                appointment.client?.full_name ||
                t('calendar.mobileRescheduleModal.clientFallback')
              }}
            </p>
            <p class="mt-1 text-sm text-blue-700">
              {{ t('calendar.mobileRescheduleModal.currentTimeLabel') }}
              <span class="font-semibold">{{ currentTimeDisplay }}</span>
            </p>
          </div>

          <!-- Form -->
          <form @submit.prevent="handleReschedule" class="space-y-4">
            <!-- Date picker -->
            <div>
              <label
                for="reschedule-date"
                class="block text-sm font-medium text-gray-700"
              >
                {{ t('calendar.mobileRescheduleModal.newDateLabel') }}
              </label>
              <input
                id="reschedule-date"
                v-model="selectedDate"
                type="date"
                :min="getTodayDate()"
                required
                class="mt-1 block w-full rounded-lg border border-gray-300 px-4 py-3 text-base shadow-sm transition-colors focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-0 focus-visible:outline-none"
              />
            </div>

            <!-- Time picker -->
            <div>
              <label
                for="reschedule-time"
                class="block text-sm font-medium text-gray-700"
              >
                {{ t('calendar.mobileRescheduleModal.newTimeLabel') }}
              </label>
              <input
                id="reschedule-time"
                v-model="selectedTime"
                type="time"
                required
                step="900"
                class="mt-1 block w-full rounded-lg border border-gray-300 px-4 py-3 text-base shadow-sm transition-colors focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-0 focus-visible:outline-none"
              />
              <p class="mt-1.5 text-xs text-gray-500">
                {{ t('calendar.mobileRescheduleModal.timeIncrementHelp') }}
              </p>
            </div>

            <!-- Preview -->
            <div v-if="newTimePreview" class="rounded-lg bg-emerald-50 p-4">
              <p class="text-sm font-medium text-emerald-900">
                {{ t('calendar.mobileRescheduleModal.previewLabel') }}
              </p>
              <p class="mt-1 text-base font-semibold text-emerald-700">
                {{ newTimePreview }}
              </p>
            </div>
          </form>
        </div>

        <!-- Actions -->
        <div class="flex gap-3 border-t border-gray-200 bg-gray-50 px-6 py-4">
          <button
            type="button"
            class="flex-1 rounded-lg border border-gray-300 bg-white px-4 py-3 text-base font-medium text-gray-700 shadow-sm transition-colors hover:bg-gray-50 focus-visible:ring-2 focus-visible:ring-gray-500 focus-visible:ring-offset-2 focus-visible:outline-none"
            @click="handleClose"
          >
            {{ t('calendar.mobileRescheduleModal.cancelButton') }}
          </button>
          <button
            type="button"
            :disabled="!isFormValid"
            class="flex-1 rounded-lg bg-emerald-600 px-4 py-3 text-base font-medium text-white shadow-sm transition-colors hover:bg-emerald-700 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
            @click="handleReschedule"
          >
            {{ t('calendar.mobileRescheduleModal.confirmButton') }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* Modal fade transition */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 200ms ease-in-out;
}

.modal-fade-enter-active > div,
.modal-fade-leave-active > div {
  transition: transform 200ms ease-in-out;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

/* Mobile: slide up from bottom */
@media (max-width: 639px) {
  .modal-fade-enter-from > div,
  .modal-fade-leave-to > div {
    transform: translateY(100%);
  }
}

/* Desktop: scale from center */
@media (min-width: 640px) {
  .modal-fade-enter-from > div,
  .modal-fade-leave-to > div {
    transform: scale(0.95);
  }
}

/* Respect reduced motion preference */
@media (prefers-reduced-motion: reduce) {
  .modal-fade-enter-active,
  .modal-fade-leave-active,
  .modal-fade-enter-active > div,
  .modal-fade-leave-active > div {
    transition: none;
  }
}
</style>
