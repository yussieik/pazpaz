<script setup lang="ts">
import type { AppointmentListItem } from '@/types/calendar'
import { formatDate, calculateDuration } from '@/utils/calendar/dateFormatters'
import { getStatusBadgeClass } from '@/utils/calendar/appointmentHelpers'

interface Props {
  appointment: AppointmentListItem | null
  visible: boolean
}

interface Emits {
  (e: 'update:visible', value: boolean): void
  (e: 'edit', appointment: AppointmentListItem): void
  (e: 'startSessionNotes', appointment: AppointmentListItem): void
  (e: 'cancel', appointment: AppointmentListItem): void
  (e: 'viewClient', clientId: string): void
}

defineProps<Props>()
const emit = defineEmits<Emits>()

function closeModal() {
  emit('update:visible', false)
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
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        role="dialog"
        aria-modal="true"
        aria-labelledby="appointment-modal-title"
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
              <h2
                id="appointment-modal-title"
                class="text-xl font-semibold text-slate-900"
              >
                Appointment Details
              </h2>
              <span
                :class="getStatusBadgeClass(appointment.status)"
                class="mt-2 inline-flex"
              >
                {{ appointment.status.replace('_', ' ') }}
              </span>
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

          <!-- Body -->
          <div class="space-y-4 px-6 py-6">
            <!-- Time Card -->
            <div class="rounded-lg border border-slate-200 bg-white p-4">
              <div class="flex items-start gap-3">
                <div class="mt-0.5 text-slate-400">
                  <!-- Clock Icon -->
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
                      d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                    />
                  </svg>
                </div>
                <div class="flex-1">
                  <div class="mb-1 text-sm font-medium text-slate-500">Time</div>
                  <div class="text-slate-900">
                    {{ formatDate(appointment.scheduled_start, 'EEEE, MMMM d, yyyy') }}
                  </div>
                  <div class="text-sm text-slate-600">
                    {{ formatDate(appointment.scheduled_start, 'h:mm a') }} -
                    {{ formatDate(appointment.scheduled_end, 'h:mm a') }}
                    <span class="ml-1 text-slate-400">
                      ({{
                        calculateDuration(
                          appointment.scheduled_start,
                          appointment.scheduled_end
                        )
                      }})
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Location Card -->
            <div class="rounded-lg border border-slate-200 bg-white p-4">
              <div class="flex items-start gap-3">
                <div class="mt-0.5 text-slate-400">
                  <!-- MapPin Icon -->
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
                      d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
                    />
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
                    />
                  </svg>
                </div>
                <div class="flex-1">
                  <div class="mb-1 text-sm font-medium text-slate-500">Location</div>
                  <div class="text-slate-900 capitalize">
                    {{ appointment.location_type.replace('_', ' ') }}
                  </div>
                  <div
                    v-if="appointment.location_details"
                    class="text-sm text-slate-600"
                  >
                    {{ appointment.location_details }}
                  </div>
                </div>
              </div>
            </div>

            <!-- Client Information -->
            <div class="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <div class="mb-2 text-sm font-medium text-slate-500">Client</div>
              <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                  <div
                    class="flex h-10 w-10 items-center justify-center rounded-full bg-slate-200 font-medium text-slate-600"
                  >
                    C
                  </div>
                  <div>
                    <div class="font-medium text-slate-900">
                      Client ID: {{ appointment.client_id.slice(0, 8) }}...
                    </div>
                    <div class="text-sm text-slate-500">View client details →</div>
                  </div>
                </div>
                <button
                  class="text-sm font-medium text-emerald-600 hover:text-emerald-700"
                  @click="emit('viewClient', appointment.client_id)"
                >
                  View Profile
                </button>
              </div>
            </div>

            <!-- Notes (if exist) -->
            <div
              v-if="appointment.notes"
              class="rounded-lg border border-slate-200 bg-white p-4"
            >
              <div class="mb-2 text-sm font-medium text-slate-500">Notes</div>
              <div class="text-sm whitespace-pre-wrap text-slate-700">
                {{ appointment.notes }}
              </div>
            </div>
          </div>

          <!-- Actions Footer -->
          <div class="sticky bottom-0 border-t border-slate-200 bg-slate-50 px-6 py-4">
            <div class="flex items-center justify-between gap-3">
              <div class="flex gap-2">
                <button
                  @click="emit('edit', appointment)"
                  class="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
                >
                  Edit
                </button>
                <button
                  v-if="appointment.status === 'scheduled'"
                  @click="emit('startSessionNotes', appointment)"
                  class="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-700"
                >
                  Start Session Notes
                </button>
              </div>
              <button
                @click="emit('cancel', appointment)"
                class="rounded-lg px-4 py-2 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
              >
                Cancel Appointment
              </button>
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
