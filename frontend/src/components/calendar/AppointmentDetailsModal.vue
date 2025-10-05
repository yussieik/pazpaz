<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useFocusTrap } from '@vueuse/integrations/useFocusTrap'
import { useScrollLock } from '@vueuse/core'
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
  (e: 'restore', appointment: AppointmentListItem): void
  (e: 'viewClient', clientId: string): void
}

const props = defineProps<Props>()
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
              <h2
                :id="`appointment-details-modal-title-${appointment.id}`"
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

                <!-- Edit button (only for non-cancelled) -->
                <button
                  v-else
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

              <!-- Cancel button (only for non-cancelled) -->
              <button
                v-if="appointment.status !== 'cancelled'"
                @click="emit('cancel', appointment)"
                class="rounded-lg px-4 py-2 text-sm font-medium text-red-600 transition-colors hover:bg-red-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2"
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
