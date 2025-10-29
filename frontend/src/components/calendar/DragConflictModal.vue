<script setup lang="ts">
import { computed } from 'vue'
import type { ConflictingAppointment } from '@/api/client'
import { formatTimeRange } from '@/utils/dragHelpers'
import IconClose from '@/components/icons/IconClose.vue'
import IconWarning from '@/components/icons/IconWarning.vue'
import IconClock from '@/components/icons/IconClock.vue'

/**
 * Drag Conflict Modal
 *
 * Inline modal shown when appointment is dropped on conflicting time slot.
 * Positioned near drop location for contextual awareness.
 *
 * Features:
 * - Shows conflicting appointment details
 * - Actions: "Keep Both Appointments" | "Cancel Move"
 * - Keyboard navigable (Enter/Escape)
 * - Non-blocking UI (can click outside to cancel)
 */

interface Props {
  visible: boolean
  conflicts: ConflictingAppointment[]
  newTimeRange: { start: Date; end: Date } | null
  position?: { x: number; y: number } | null
}

interface Emits {
  (e: 'confirm'): void
  (e: 'cancel'): void
  (e: 'update:visible', value: boolean): void
}

const props = withDefaults(defineProps<Props>(), {
  position: null,
})

const emit = defineEmits<Emits>()

/**
 * Formatted new time range
 */
const formattedNewTime = computed(() => {
  if (!props.newTimeRange) return ''
  return formatTimeRange(props.newTimeRange.start, props.newTimeRange.end)
})

/**
 * Format conflict time range
 */
function formatConflictTime(conflict: ConflictingAppointment): string {
  return formatTimeRange(conflict.scheduled_start, conflict.scheduled_end)
}

/**
 * Get status badge color
 */
function getStatusColor(status: string): string {
  switch (status.toLowerCase()) {
    case 'scheduled':
      return 'bg-blue-100 text-blue-800'
    case 'attended':
      return 'bg-green-100 text-green-800'
    default:
      return 'bg-gray-100 text-gray-800'
  }
}

/**
 * Calculate modal position style
 */
const modalPositionStyle = computed(() => {
  if (!props.position) return {}

  return {
    position: 'fixed' as const,
    left: `${Math.min(props.position.x + 10, window.innerWidth - 400)}px`,
    top: `${Math.min(props.position.y + 10, window.innerHeight - 300)}px`,
  }
})

/**
 * Handle confirm
 */
function handleConfirm() {
  emit('confirm')
  emit('update:visible', false)
}

/**
 * Handle cancel
 */
function handleCancel() {
  emit('cancel')
  emit('update:visible', false)
}

/**
 * Handle keyboard shortcuts
 */
function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter') {
    event.preventDefault()
    handleConfirm()
  } else if (event.key === 'Escape') {
    event.preventDefault()
    handleCancel()
  }
}
</script>

<template>
  <Transition name="modal-fade">
    <div
      v-if="visible"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4 backdrop-blur-sm"
      @click.self="handleCancel"
      @keydown="handleKeydown"
    >
      <!-- Modal positioned near drop location if position provided -->
      <div
        :style="modalPositionStyle"
        class="relative w-full max-w-md rounded-lg bg-white shadow-2xl ring-1 ring-black/5"
        role="dialog"
        aria-modal="true"
        aria-labelledby="conflict-title"
        aria-describedby="conflict-description"
      >
        <!-- Header -->
        <div class="border-b border-amber-200 bg-amber-50 px-6 py-4">
          <div class="flex items-start gap-3">
            <!-- Warning icon -->
            <div
              class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-amber-100"
            >
              <IconWarning size="lg" class="text-amber-600" />
            </div>

            <div class="flex-1">
              <h3 id="conflict-title" class="text-lg font-semibold text-gray-900">
                Scheduling Conflict Detected
              </h3>
              <p id="conflict-description" class="mt-1 text-sm text-gray-600">
                This appointment overlaps with {{ conflicts.length }} existing
                {{ conflicts.length === 1 ? 'appointment' : 'appointments' }}.
              </p>
            </div>

            <!-- Close button -->
            <button
              type="button"
              class="rounded-lg p-1 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:outline-none"
              @click="handleCancel"
              aria-label="Close dialog"
            >
              <IconClose class="h-5 w-5" />
            </button>
          </div>
        </div>

        <!-- Content -->
        <div class="px-6 py-4">
          <!-- New time info -->
          <div class="mb-4 rounded-lg bg-blue-50 p-3">
            <p class="text-sm font-medium text-blue-900">New appointment time:</p>
            <p class="mt-1 text-base font-semibold text-blue-700">
              {{ formattedNewTime }}
            </p>
          </div>

          <!-- Conflicting appointments list -->
          <div class="space-y-3">
            <p class="text-sm font-medium text-gray-700">Conflicts with:</p>

            <div
              v-for="conflict in conflicts"
              :key="conflict.id"
              class="rounded-lg border border-amber-200 bg-amber-50/50 p-3"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0 flex-1">
                  <!-- Client initials -->
                  <div class="flex items-center gap-2">
                    <div
                      class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-amber-200 text-sm font-semibold text-amber-900"
                    >
                      {{ conflict.client_initials }}
                    </div>
                    <div class="min-w-0 flex-1">
                      <p class="truncate text-sm font-medium text-gray-900">
                        Client: {{ conflict.client_initials }}
                      </p>
                    </div>
                  </div>

                  <!-- Time and location -->
                  <div
                    class="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-600"
                  >
                    <span class="flex items-center gap-1">
                      <IconClock size="sm" />
                      {{ formatConflictTime(conflict) }}
                    </span>
                    <span class="flex items-center gap-1 capitalize">
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
                          d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
                        />
                        <path
                          stroke-linecap="round"
                          stroke-linejoin="round"
                          stroke-width="2"
                          d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
                        />
                      </svg>
                      {{ conflict.location_type }}
                    </span>
                  </div>
                </div>

                <!-- Status badge -->
                <span
                  :class="getStatusColor(conflict.status)"
                  class="shrink-0 rounded-full px-2 py-1 text-xs font-medium capitalize"
                >
                  {{ conflict.status }}
                </span>
              </div>
            </div>
          </div>

          <!-- Warning message -->
          <div class="mt-4 rounded-lg bg-yellow-50 p-3">
            <p class="text-sm text-yellow-800">
              <strong>Note:</strong> Keeping both appointments will result in
              overlapping schedules. You may want to reschedule one of them.
            </p>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex gap-3 border-t border-gray-200 bg-gray-50 px-6 py-4">
          <button
            type="button"
            class="flex-1 rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-sm font-medium text-gray-700 shadow-sm transition-colors hover:bg-gray-50 focus-visible:ring-2 focus-visible:ring-gray-500 focus-visible:ring-offset-2 focus-visible:outline-none"
            @click="handleCancel"
          >
            Cancel Move
          </button>
          <button
            type="button"
            class="flex-1 rounded-lg bg-amber-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-amber-700 focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2 focus-visible:outline-none"
            @click="handleConfirm"
            autofocus
          >
            Keep Both Appointments
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

.modal-fade-enter-from > div,
.modal-fade-leave-to > div {
  transform: scale(0.95);
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

/* Screen reader only class */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}
</style>
