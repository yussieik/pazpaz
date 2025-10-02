<script setup lang="ts">
import { ref, computed } from 'vue'
import { format, parseISO } from 'date-fns'
import type { ConflictingAppointment } from '@/types/calendar'

interface Props {
  conflicts: ConflictingAppointment[]
}

interface Emits {
  (e: 'view-conflict', appointmentId: string): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const isExpanded = ref(false)

const conflictCount = computed(() => props.conflicts.length)
const conflictCountText = computed(() =>
  conflictCount.value === 1 ? '1 existing appointment' : `${conflictCount.value} existing appointments`
)

function toggleExpanded() {
  isExpanded.value = !isExpanded.value
}

function handleViewConflict(appointmentId: string) {
  emit('view-conflict', appointmentId)
}

function formatTime(isoDatetime: string): string {
  try {
    return format(parseISO(isoDatetime), 'h:mm a')
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
</script>

<template>
  <div
    role="alert"
    aria-live="polite"
    aria-atomic="true"
    class="mt-3 flex gap-3 rounded-lg border-l-4 border-amber-500 bg-amber-50 px-4 py-3"
  >
    <!-- Warning Icon -->
    <svg
      aria-hidden="true"
      class="h-5 w-5 flex-shrink-0 text-amber-600"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
      />
    </svg>

    <!-- Content -->
    <div class="flex-1">
      <p class="text-sm font-semibold text-amber-900">Scheduling Conflict</p>
      <p class="mt-1 text-sm text-amber-800">
        This time overlaps with {{ conflictCountText }}.
        <button
          @click="toggleExpanded"
          :aria-expanded="isExpanded"
          aria-controls="conflict-details"
          class="ml-1 font-medium underline hover:text-amber-900 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-1"
        >
          {{ isExpanded ? 'Hide details' : 'View details' }}
        </button>
      </p>

      <!-- Expanded Conflict List -->
      <div
        v-if="isExpanded"
        id="conflict-details"
        role="region"
        aria-labelledby="conflict-heading"
        class="mt-3 max-h-64 space-y-2 overflow-y-auto border-t border-amber-200 pt-3"
      >
        <h3 id="conflict-heading" class="sr-only">
          Conflicting appointments ({{ conflictCount }})
        </h3>

        <div
          v-for="conflict in conflicts"
          :key="conflict.id"
          class="flex items-start justify-between gap-3 rounded-md border border-amber-300 bg-white px-3 py-2"
        >
          <div class="flex-1 space-y-1">
            <p class="text-sm font-medium text-slate-900">
              {{ formatTimeRange(conflict.scheduled_start, conflict.scheduled_end) }}
            </p>
            <div class="flex items-center gap-3 text-xs text-slate-600">
              <span>Client: {{ conflict.client_initials }}</span>
              <span>&bull;</span>
              <span>{{ getLocationLabel(conflict.location_type) }}</span>
            </div>
          </div>

          <button
            @click="handleViewConflict(conflict.id)"
            class="flex-shrink-0 rounded px-2 py-1 text-xs font-medium text-amber-700 hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
            :aria-label="`View appointment at ${formatTimeRange(conflict.scheduled_start, conflict.scheduled_end)}`"
          >
            View →
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
