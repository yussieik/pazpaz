<script setup lang="ts">
import { computed } from 'vue'
import { onKeyStroke } from '@vueuse/core'
import type {
  AppointmentListItem,
  AppointmentStatus,
  SessionStatus,
} from '@/types/calendar'
import { formatDistanceToNow } from 'date-fns'

interface Props {
  appointment: AppointmentListItem | null
  sessionStatus?: SessionStatus | null
}

interface Emits {
  (e: 'update-status', status: AppointmentStatus): void
  (e: 'complete-and-document'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

/**
 * Check if appointment is in the past
 */
const isPastAppointment = computed(() => {
  if (!props.appointment) return false
  return new Date(props.appointment.scheduled_end) < new Date()
})

/**
 * Check if status can be changed (only scheduled appointments)
 */
const canChangeStatus = computed(() => {
  return props.appointment?.status === 'scheduled'
})

/**
 * Get time since appointment ended for smart prompts
 */
const timeSinceEnd = computed(() => {
  if (!props.appointment || !isPastAppointment.value) return ''
  return formatDistanceToNow(new Date(props.appointment.scheduled_end), {
    addSuffix: true,
  })
})

/**
 * Primary action: Complete appointment and navigate to session creation
 */
function completeAndDocument() {
  emit('update-status', 'completed')
  emit('complete-and-document')
}

/**
 * Secondary action: Mark as completed without creating session
 */
function markAsCompleted() {
  emit('update-status', 'completed')
}

/**
 * Tertiary action: Mark as no-show
 */
function markAsNoShow() {
  emit('update-status', 'no_show')
}

/**
 * Keyboard shortcuts for status management
 */
onKeyStroke(['Meta+Enter', 'Control+Enter'], (e) => {
  if (isPastAppointment.value && canChangeStatus.value) {
    e.preventDefault()
    completeAndDocument()
  }
})

onKeyStroke(['Meta+Shift+c', 'Control+Shift+c'], (e) => {
  if (canChangeStatus.value && isPastAppointment.value) {
    e.preventDefault()
    markAsCompleted()
  }
})

onKeyStroke(['Meta+Shift+n', 'Control+Shift+n'], (e) => {
  if (canChangeStatus.value && isPastAppointment.value) {
    e.preventDefault()
    markAsNoShow()
  }
})
</script>

<template>
  <!-- Only show if appointment can change status (scheduled only) -->
  <div
    v-if="appointment && canChangeStatus"
    class="rounded-lg border border-slate-200 bg-white p-4"
  >
    <!-- Smart prompt for past appointments -->
    <div v-if="isPastAppointment" class="mb-4">
      <div class="flex items-start gap-3">
        <svg
          class="h-5 w-5 shrink-0 text-blue-600"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <div class="flex-1">
          <p class="text-sm font-medium text-slate-900">
            This appointment ended {{ timeSinceEnd }}.
          </p>
          <p class="mt-0.5 text-xs text-slate-600">Ready to document?</p>
        </div>
      </div>
    </div>

    <!-- Future appointment message -->
    <div v-else class="mb-4">
      <p class="text-sm text-slate-600">Update appointment status when completed</p>
    </div>

    <!-- Action Buttons -->
    <div class="space-y-2">
      <!-- Primary: Complete & Add Session Note -->
      <button
        v-if="isPastAppointment"
        @click="completeAndDocument"
        class="flex w-full items-center justify-between rounded-lg bg-emerald-600 px-4 py-3 text-sm font-medium text-white transition-colors hover:bg-emerald-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
      >
        <span>Complete & Add Session Note</span>
        <span class="ml-2 rounded bg-emerald-700/50 px-2 py-0.5 text-xs font-medium">
          ⌘↵
        </span>
      </button>

      <!-- Secondary: Mark as Completed (ONLY for past appointments) -->
      <button
        v-if="isPastAppointment"
        @click="markAsCompleted"
        class="flex w-full items-center justify-between rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2"
      >
        <span>Mark as Completed</span>
        <span
          class="ml-2 rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600"
        >
          ⌘⇧C
        </span>
      </button>

      <!-- Tertiary: Mark as No-Show (ONLY for past appointments) -->
      <button
        v-if="isPastAppointment"
        @click="markAsNoShow"
        class="flex w-full items-center justify-between rounded-lg border border-amber-300 bg-white px-4 py-2.5 text-sm font-medium text-amber-700 transition-colors hover:bg-amber-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2"
      >
        <span>Mark as No-Show</span>
        <span
          class="ml-2 rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700"
        >
          ⌘⇧N
        </span>
      </button>
    </div>
  </div>
</template>
