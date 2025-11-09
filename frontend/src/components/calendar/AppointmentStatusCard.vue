<script setup lang="ts">
import { computed } from 'vue'
import { onKeyStroke } from '@vueuse/core'
import type {
  AppointmentListItem,
  AppointmentStatus,
  SessionStatus,
} from '@/types/calendar'
import { formatDistanceToNow } from 'date-fns'
import { useI18n } from '@/composables/useI18n'
import IconClock from '@/components/icons/IconClock.vue'

const { t } = useI18n()

interface Props {
  appointment: AppointmentListItem | null
  sessionStatus?: SessionStatus | null
  completionDisabled?: boolean
  completionDisabledMessage?: string | null
}

interface Emits {
  (e: 'update-status', status: AppointmentStatus): void
  (e: 'complete-and-document'): void
}

const props = withDefaults(defineProps<Props>(), {
  completionDisabled: false,
  completionDisabledMessage: null,
})
const emit = defineEmits<Emits>()

/**
 * Check if appointment is in the past
 */
const isPastAppointment = computed(() => {
  if (!props.appointment) return false
  return new Date(props.appointment.scheduled_end) < new Date()
})

/**
 * Check if appointment is currently in progress
 * Only scheduled appointments within the time window are considered "in progress"
 */
const isInProgressAppointment = computed(() => {
  if (!props.appointment) return false
  if (props.appointment.status !== 'scheduled') return false
  const now = new Date()
  const start = new Date(props.appointment.scheduled_start)
  const end = new Date(props.appointment.scheduled_end)
  return now >= start && now <= end
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
  emit('update-status', 'attended')
  emit('complete-and-document')
}

/**
 * Secondary action: Mark as attended without creating session
 */
function markAsAttended() {
  emit('update-status', 'attended')
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
    markAsAttended()
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
    <!-- IN PROGRESS: Show document action -->
    <div v-if="isInProgressAppointment" class="mb-4">
      <div class="flex items-start gap-3">
        <svg
          class="h-5 w-5 shrink-0 text-emerald-600"
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
        <div class="flex-1">
          <p class="text-sm font-medium text-slate-900">
            {{ t('calendar.appointmentDetails.statusCard.sessionInProgress') }}
          </p>
          <p class="mt-0.5 text-xs text-slate-600">
            {{ t('calendar.appointmentDetails.statusCard.sessionInProgressHint') }}
          </p>
        </div>
      </div>
    </div>

    <!-- PAST: Keep existing prompt -->
    <div v-else-if="isPastAppointment" class="mb-4">
      <div class="flex items-start gap-3">
        <IconClock size="md" class="shrink-0 text-blue-600" />
        <div class="flex-1">
          <p class="text-sm font-medium text-slate-900">
            {{
              t('calendar.appointmentDetails.statusCard.appointmentEnded', {
                timeAgo: timeSinceEnd,
              })
            }}
          </p>
          <p class="mt-0.5 text-xs text-slate-600">
            {{ t('calendar.appointmentDetails.statusCard.readyToDocument') }}
          </p>
        </div>
      </div>
    </div>

    <!-- FUTURE: Keep existing message -->
    <div v-else class="mb-4">
      <p class="text-sm text-slate-600">
        {{ t('calendar.appointmentDetails.statusCard.updateWhenCompleted') }}
      </p>
    </div>

    <!-- Action Buttons -->
    <div class="space-y-2">
      <!-- Warning message if completion is disabled -->
      <div
        v-if="completionDisabled && completionDisabledMessage"
        class="flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900"
      >
        <svg
          class="h-4 w-4 shrink-0 text-amber-600"
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
        <span>{{ completionDisabledMessage }}</span>
      </div>

      <!-- Primary: Document Session (In Progress OR Past) -->
      <button
        v-if="isInProgressAppointment || isPastAppointment"
        @click="completeAndDocument"
        :disabled="completionDisabled"
        :class="[
          'flex w-full items-center justify-between rounded-lg px-4 py-3 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2',
          completionDisabled
            ? 'cursor-not-allowed bg-slate-300 text-slate-500'
            : 'bg-emerald-600 text-white hover:bg-emerald-700',
        ]"
      >
        <span>
          {{
            isInProgressAppointment
              ? t('calendar.appointmentDetails.statusCard.documentSession')
              : t('calendar.appointmentDetails.statusCard.completeAndAddNote')
          }}
        </span>
        <span
          :class="[
            'ml-2 rounded px-2 py-0.5 text-xs font-medium',
            completionDisabled ? 'bg-slate-400/50' : 'bg-emerald-700/50',
          ]"
        >
          ⌘↵
        </span>
      </button>

      <!-- Secondary: Mark as Attended (ONLY past, not in progress) -->
      <button
        v-if="isPastAppointment && !isInProgressAppointment"
        @click="markAsAttended"
        :disabled="completionDisabled"
        :class="[
          'flex w-full items-center justify-between rounded-lg border px-4 py-2.5 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2',
          completionDisabled
            ? 'cursor-not-allowed border-slate-200 bg-slate-50 text-slate-400'
            : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50',
        ]"
      >
        <span>{{ t('calendar.appointmentDetails.statusCard.markAsAttended') }}</span>
        <span
          :class="[
            'ml-2 rounded px-2 py-0.5 text-xs font-medium',
            completionDisabled
              ? 'bg-slate-200 text-slate-500'
              : 'bg-slate-100 text-slate-600',
          ]"
        >
          ⌘⇧C
        </span>
      </button>

      <!-- Tertiary: Mark as No-Show (ONLY past, not in progress) -->
      <button
        v-if="isPastAppointment && !isInProgressAppointment"
        @click="markAsNoShow"
        class="flex w-full items-center justify-between rounded-lg border border-amber-300 bg-white px-4 py-2.5 text-sm font-medium text-amber-700 transition-colors hover:bg-amber-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 focus-visible:ring-offset-2"
      >
        <span>{{ t('calendar.appointmentDetails.statusCard.markAsNoShow') }}</span>
        <span
          class="ml-2 rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700"
        >
          ⌘⇧N
        </span>
      </button>
    </div>
  </div>
</template>
