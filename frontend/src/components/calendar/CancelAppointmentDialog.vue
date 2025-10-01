<script setup lang="ts">
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

defineProps<Props>()
const emit = defineEmits<Emits>()

function closeDialog() {
  emit('update:visible', false)
}

function handleConfirm() {
  emit('confirm')
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
        <div class="w-full max-w-md rounded-xl bg-white shadow-xl" @click.stop>
          <!-- Header -->
          <div class="px-6 pt-6">
            <div class="flex items-center gap-3">
              <div
                class="flex h-10 w-10 items-center justify-center rounded-full bg-red-100"
              >
                <svg
                  class="h-5 w-5 text-red-600"
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
              </div>
              <div>
                <h2
                  id="cancel-dialog-title"
                  class="text-lg font-semibold text-slate-900"
                >
                  Cancel Appointment?
                </h2>
              </div>
            </div>
          </div>

          <!-- Body -->
          <div class="px-6 py-4">
            <p class="text-sm text-slate-600">
              Are you sure you want to cancel the appointment with
              <strong>{{ appointment.client?.full_name || 'this client' }}</strong>
              on
              <strong>{{
                formatDate(
                  appointment.scheduled_start,
                  "EEEE, MMMM d, yyyy 'at' h:mm a"
                )
              }}</strong
              >?
            </p>
            <p class="mt-2 text-sm text-slate-600">This action cannot be undone.</p>
          </div>

          <!-- Footer -->
          <div
            class="flex items-center justify-end gap-3 border-t border-slate-200 bg-slate-50 px-6 py-4"
          >
            <button
              @click="closeDialog"
              type="button"
              class="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
            >
              Keep Appointment
            </button>
            <button
              @click="handleConfirm"
              type="button"
              class="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700"
            >
              Yes, Cancel Appointment
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
