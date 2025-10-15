<script setup lang="ts">
import { ref } from 'vue'
import type { AppointmentListItem } from '@/types/calendar'
import { formatDate } from '@/utils/calendar/dateFormatters'
import IconWarning from '@/components/icons/IconWarning.vue'
import IconClock from '@/components/icons/IconClock.vue'

interface Props {
  visible: boolean
  appointment: AppointmentListItem | null
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'confirm', reason: string): void
}

defineProps<Props>()
const emit = defineEmits<Emits>()

const cancelReason = ref('')

function closeDialog() {
  emit('update:visible', false)
  // Reset reason when closing
  cancelReason.value = ''
}

function handleConfirm() {
  emit('confirm', cancelReason.value)
  closeDialog()
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
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
        aria-labelledby="cancel-dialog-title"
        @keydown="handleKeydown"
      >
        <div class="w-full max-w-md rounded-xl bg-white p-6 shadow-xl" @click.stop>
          <!-- Header with Amber Warning Icon -->
          <div class="flex items-start gap-4">
            <div
              class="flex h-12 w-12 items-center justify-center rounded-full bg-amber-100"
            >
              <IconWarning size="lg" class="text-amber-600" />
            </div>

            <div class="flex-1">
              <h2 id="cancel-dialog-title" class="text-lg font-semibold text-slate-900">
                Cancel Appointment?
              </h2>
              <p class="mt-1 text-sm text-slate-600">
                This will mark the appointment as cancelled but keep it in your records.
              </p>
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
                <IconClock size="sm" class="text-slate-400" />
                <span class="text-slate-600">
                  {{ formatDate(appointment.scheduled_start, 'h:mm a') }} -
                  {{ formatDate(appointment.scheduled_end, 'h:mm a') }}
                </span>
              </div>
            </div>
          </div>

          <!-- Optional Reason Field -->
          <div class="mt-4">
            <label
              for="cancel-reason"
              class="mb-1.5 block text-sm font-medium text-slate-900"
            >
              Reason (optional)
            </label>
            <textarea
              id="cancel-reason"
              v-model="cancelReason"
              rows="3"
              placeholder="e.g., Client requested cancellation, therapist illness..."
              class="sm:rows-2 mt-1 min-h-[80px] w-full rounded-lg border border-slate-300 px-3 py-2 text-base placeholder:text-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 focus:outline-none sm:text-sm"
            />
            <p class="mt-1 text-xs text-slate-500">
              This note will be added to the appointment record.
            </p>
          </div>

          <!-- Actions -->
          <div
            class="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-end"
          >
            <button
              @click="closeDialog"
              type="button"
              class="order-2 inline-flex min-h-[44px] w-full items-center justify-center rounded-lg px-4 py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 sm:order-1 sm:w-auto"
            >
              Keep Appointment
            </button>
            <button
              @click="handleConfirm"
              type="button"
              class="order-1 inline-flex min-h-[44px] w-full items-center justify-center rounded-lg bg-red-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-red-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2 sm:order-2 sm:w-auto"
            >
              Cancel Appointment
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
