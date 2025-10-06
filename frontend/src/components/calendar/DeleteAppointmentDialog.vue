<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { AppointmentListItem } from '@/types/calendar'
import { formatDate } from '@/utils/calendar/dateFormatters'

interface Props {
  visible: boolean
  appointment: AppointmentListItem | null
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'confirm'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const isDeleting = ref(false)

// Reset loading state when dialog closes or appointment changes
watch(
  () => props.visible,
  (newVisible) => {
    if (!newVisible) {
      isDeleting.value = false
    }
  }
)

watch(
  () => props.appointment?.id,
  () => {
    isDeleting.value = false
  }
)

/**
 * Check if appointment can be deleted based on UX rules:
 * - Allow: scheduled or cancelled status
 * - Block: completed status (medical records)
 * - Block: Appointments with SOAP notes (future-proof)
 */
const canDelete = computed(() => {
  if (!props.appointment) return false

  // Block deletion of completed appointments (medical records)
  if (props.appointment.status === 'completed') {
    return false
  }

  // Allow deletion of scheduled or cancelled appointments
  return (
    props.appointment.status === 'scheduled' || props.appointment.status === 'cancelled'
  )
})

const blockReason = computed(() => {
  if (!props.appointment) return ''

  if (props.appointment.status === 'completed') {
    return 'Completed appointments cannot be deleted as they are medical records. Consider canceling instead.'
  }

  return ''
})

function closeDialog() {
  if (isDeleting.value) return // Prevent closing while deleting
  emit('update:visible', false)
}

function handleConfirm() {
  if (!canDelete.value || isDeleting.value) return

  isDeleting.value = true
  emit('confirm')
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && !isDeleting.value) {
    closeDialog()
  }
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
        @click="closeDialog"
        aria-hidden="true"
      ></div>
    </Transition>

    <!-- Dialog Content -->
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
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-dialog-title"
        @keydown="handleKeydown"
      >
        <div class="w-full max-w-md rounded-xl bg-white p-6 shadow-xl" @click.stop>
          <!-- Header with Red Warning Icon -->
          <div class="flex items-start gap-4">
            <div
              class="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-red-100"
            >
              <svg
                class="h-6 w-6 text-red-600"
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
            </div>

            <div class="flex-1">
              <h2 id="delete-dialog-title" class="text-lg font-semibold text-slate-900">
                Delete Appointment?
              </h2>
              <p class="mt-1 text-sm text-slate-600">
                This action cannot be undone. The appointment will be permanently
                removed from your records.
              </p>
            </div>
          </div>

          <!-- Warning Message or Block Reason -->
          <div
            v-if="!canDelete"
            class="mt-4 rounded-lg border border-red-200 bg-red-50 p-4"
          >
            <div class="flex">
              <svg
                class="h-5 w-5 flex-shrink-0 text-red-400"
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
              <div class="ml-3">
                <h3 class="text-sm font-medium text-red-800">Deletion Not Allowed</h3>
                <p class="mt-1 text-sm text-red-700">
                  {{ blockReason }}
                </p>
              </div>
            </div>
          </div>

          <div v-else>
            <!-- Alternative Suggestion -->
            <div class="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-4">
              <div class="flex">
                <svg
                  class="h-5 w-5 flex-shrink-0 text-amber-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
                  />
                </svg>
                <div class="ml-3">
                  <h3 class="text-sm font-medium text-amber-800">
                    Consider Canceling Instead
                  </h3>
                  <p class="mt-1 text-sm text-amber-700">
                    Canceling preserves the appointment in your history for
                    record-keeping and audit purposes.
                  </p>
                </div>
              </div>
            </div>

            <!-- Appointment Details Card -->
            <div class="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
              <div class="space-y-2 text-sm">
                <!-- Client -->
                <div class="flex items-center gap-2">
                  <svg
                    class="h-4 w-4 text-slate-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"
                    />
                  </svg>
                  <span class="font-medium text-slate-900">{{
                    appointment.client?.full_name || 'Unknown Client'
                  }}</span>
                </div>

                <!-- Date -->
                <div class="flex items-center gap-2">
                  <svg
                    class="h-4 w-4 text-slate-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                    />
                  </svg>
                  <span class="text-slate-600">
                    {{ formatDate(appointment.scheduled_start, 'EEEE, MMMM d, yyyy') }}
                  </span>
                </div>

                <!-- Time -->
                <div class="flex items-center gap-2">
                  <svg
                    class="h-4 w-4 text-slate-400"
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
                  <span class="text-slate-600">
                    {{ formatDate(appointment.scheduled_start, 'h:mm a') }} -
                    {{ formatDate(appointment.scheduled_end, 'h:mm a') }}
                  </span>
                </div>

                <!-- Status -->
                <div class="flex items-center gap-2">
                  <svg
                    class="h-4 w-4 text-slate-400"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                  <span class="text-slate-600 capitalize">
                    {{ appointment.status.replace('_', ' ') }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <!-- Actions -->
          <div class="mt-6 flex items-center justify-end gap-3">
            <button
              @click="closeDialog"
              type="button"
              :disabled="isDeleting"
              class="rounded-lg px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {{ canDelete ? 'Keep Appointment' : 'Close' }}
            </button>
            <button
              v-if="canDelete"
              @click="handleConfirm"
              type="button"
              :disabled="isDeleting"
              class="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <svg
                v-if="isDeleting"
                class="h-4 w-4 animate-spin"
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
              <span>{{ isDeleting ? 'Deleting...' : 'Delete Permanently' }}</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
