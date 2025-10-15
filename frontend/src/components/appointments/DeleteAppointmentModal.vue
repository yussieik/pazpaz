<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { onKeyStroke } from '@vueuse/core'
import type { AppointmentListItem, SessionStatus } from '@/types/calendar'
import type { SessionNoteAction } from '@/types/sessions'
import { formatDate } from '@/utils/calendar/dateFormatters'
import { hasSubstantialContent } from '@/types/sessions'
import { useSessionQuery } from '@/composables/useSessionQuery'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import IconWarning from '@/components/icons/IconWarning.vue'

interface Props {
  appointment: AppointmentListItem | null
  sessionStatus?: SessionStatus | null
  open: boolean
}

interface Emits {
  (
    e: 'confirm',
    payload: {
      reason?: string
      session_note_action?: SessionNoteAction
      deletion_reason?: string
    }
  ): void
  (e: 'cancel'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// Deletion state
const reason = ref('')
const sessionDeletionReason = ref('')
const showFinalConfirmation = ref(false)
const isDeleting = ref(false)

// Session query composable
const {
  loading: loadingSession,
  session: sessionNote,
  fetchByAppointmentId,
} = useSessionQuery()
const sessionNoteAction = ref<SessionNoteAction>('keep')

// Quick-pick reason suggestions
const reasonSuggestions = [
  'Duplicate entry',
  'Entered in error',
  'Client cancelled before appointment',
]

const sessionDeletionReasons = [
  'Entered in error',
  'Duplicate note',
  'No clinical value',
]

// Real session note metadata from API
const sessionNoteWordCount = computed(() => {
  if (!sessionNote.value) return 0
  const allText = [
    sessionNote.value.subjective,
    sessionNote.value.objective,
    sessionNote.value.assessment,
    sessionNote.value.plan,
  ]
    .filter(Boolean)
    .join(' ')
  return allText.split(/\s+/).filter((w) => w.length > 0).length
})

const sessionNoteAttachments = computed(() => {
  return sessionNote.value?.attachments?.length || 0
})

/**
 * Check if we need to show the final confirmation stage
 * Only show if appointment has a session note
 */
const needsFinalConfirmation = computed(() => {
  return sessionNote.value !== null
})

/**
 * Query for session note when dialog opens
 */
async function checkForSessionNote() {
  if (!props.appointment?.id) return

  const fetchedSession = await fetchByAppointmentId(props.appointment.id)

  if (fetchedSession) {
    // Smart default: keep substantial notes, delete empty ones
    sessionNoteAction.value = hasSubstantialContent(fetchedSession) ? 'keep' : 'delete'
  }
}

/**
 * Handle delete click from Stage 1
 */
function handleDeleteClick() {
  if (needsFinalConfirmation.value) {
    // Go to Stage 2 for final confirmation
    showFinalConfirmation.value = true
  } else {
    // Directly confirm deletion
    handleFinalConfirm()
  }
}

/**
 * Handle final confirmation (Stage 2 or direct from Stage 1)
 */
function handleFinalConfirm() {
  if (isDeleting.value) return

  isDeleting.value = true

  const payload: {
    reason?: string
    session_note_action?: SessionNoteAction
    deletion_reason?: string
  } = {}

  if (reason.value.trim()) {
    payload.reason = reason.value.trim()
  }

  if (sessionNote.value) {
    payload.session_note_action = sessionNoteAction.value
    if (sessionNoteAction.value === 'delete' && sessionDeletionReason.value.trim()) {
      payload.deletion_reason = sessionDeletionReason.value.trim()
    }
  }

  emit('confirm', payload)
}

/**
 * Go back from Stage 2 to Stage 1
 */
function goBack() {
  showFinalConfirmation.value = false
}

/**
 * Close modal and reset state
 */
function handleCancel() {
  if (isDeleting.value) return
  emit('cancel')
}

/**
 * Handle Escape key - global listener
 */
onKeyStroke('Escape', (e) => {
  // Only handle if modal is open and not currently deleting
  if (!props.open || isDeleting.value) return

  // Prevent event from propagating to parent modals (like AppointmentDetailsModal)
  e.preventDefault()
  e.stopPropagation()

  if (showFinalConfirmation.value) {
    goBack()
  } else {
    handleCancel()
  }
})

/**
 * Reset state when dialog opens/closes
 */
watch(
  () => props.open,
  async (isOpen) => {
    if (isOpen) {
      // Query for session note when dialog opens
      await checkForSessionNote()
    } else {
      // Reset state when closing
      reason.value = ''
      sessionDeletionReason.value = ''
      showFinalConfirmation.value = false
      isDeleting.value = false
      sessionNoteAction.value = 'keep'
      // Note: sessionNote is managed by useSessionQuery composable
    }
  }
)

/**
 * Apply quick-pick suggestion
 */
function applySuggestion(suggestion: string) {
  reason.value = suggestion
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
        v-if="open"
        class="fixed inset-0 z-40 bg-slate-900/20 backdrop-blur-sm"
        @click="handleCancel"
        aria-hidden="true"
      ></div>
    </Transition>

    <!-- Stage 1: Initial Confirmation -->
    <Transition
      enter-active-class="transition-all duration-150 ease-out"
      leave-active-class="transition-all duration-150 ease-in"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="open && appointment && !showFinalConfirmation"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-appointment-stage-1-title"
      >
        <div class="w-full max-w-md rounded-xl bg-white p-6 shadow-xl" @click.stop>
          <!-- Header -->
          <h3
            id="delete-appointment-stage-1-title"
            class="text-lg font-semibold text-slate-900"
          >
            Delete Appointment?
          </h3>

          <!-- Appointment Details -->
          <div class="mt-4 rounded-lg bg-slate-50 p-4">
            <p class="text-sm font-medium text-slate-900">
              {{ formatDate(appointment.scheduled_start, "EEEE, MMMM d 'at' h:mm a") }}
            </p>
            <p class="mt-1 text-sm text-slate-600">
              {{ appointment.client?.full_name || 'Unknown Client' }} -
              {{ appointment.service?.name || 'Appointment' }}
            </p>
          </div>

          <!-- Loading state -->
          <div v-if="loadingSession" class="mt-4 py-4 text-center">
            <LoadingSpinner size="md" color="slate" />
            <p class="mt-2 text-sm text-slate-600">Checking for session notes...</p>
          </div>

          <!-- Session Note Action Selection (if session exists) -->
          <div v-else-if="sessionNote" class="mt-4 space-y-3">
            <p class="text-sm font-medium text-slate-700">
              This appointment has a session note. What would you like to do with it?
            </p>

            <!-- Keep Option -->
            <label
              class="flex cursor-pointer items-start gap-3 rounded-lg border-2 p-4 transition-colors"
              :class="
                sessionNoteAction === 'keep'
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-slate-200 hover:border-slate-300'
              "
            >
              <input
                type="radio"
                value="keep"
                v-model="sessionNoteAction"
                class="mt-0.5 h-4 w-4 text-blue-600 focus:ring-2 focus:ring-blue-500"
              />
              <div class="flex-1">
                <div class="flex items-center gap-2">
                  <span class="font-medium text-slate-900">Keep session note</span>
                  <span
                    v-if="hasSubstantialContent(sessionNote)"
                    class="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-700"
                  >
                    Recommended
                  </span>
                </div>
                <p class="mt-1 text-sm text-slate-600">
                  Preserve the clinical documentation ({{ sessionNoteWordCount }} words)
                </p>
              </div>
            </label>

            <!-- Delete Option -->
            <label
              class="flex cursor-pointer items-start gap-3 rounded-lg border-2 p-4 transition-colors"
              :class="
                sessionNoteAction === 'delete'
                  ? 'border-red-500 bg-red-50'
                  : 'border-slate-200 hover:border-slate-300'
              "
            >
              <input
                type="radio"
                value="delete"
                v-model="sessionNoteAction"
                class="mt-0.5 h-4 w-4 text-red-600 focus:ring-2 focus:ring-red-500"
              />
              <div class="flex-1">
                <div class="flex items-center gap-2">
                  <span class="font-medium text-slate-900">Delete session note</span>
                </div>
                <p class="mt-1 text-sm text-slate-600">
                  30-day recovery period before permanent deletion
                </p>
              </div>
            </label>

            <!-- Session Deletion Reason (if delete selected) -->
            <div v-if="sessionNoteAction === 'delete'" class="mt-2 ml-10 space-y-2">
              <label class="text-xs font-medium text-slate-700">
                Reason for deleting note (optional)
              </label>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="delReason in sessionDeletionReasons"
                  :key="delReason"
                  @click="
                    sessionDeletionReason =
                      sessionDeletionReason === delReason ? '' : delReason
                  "
                  type="button"
                  class="rounded-full px-3 py-1 text-xs font-medium transition-colors"
                  :class="
                    sessionDeletionReason === delReason
                      ? 'bg-slate-900 text-white'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                  "
                >
                  {{ delReason }}
                </button>
              </div>
            </div>
          </div>

          <!-- Warning if completed -->
          <div
            v-if="appointment.status === 'completed' && !loadingSession"
            class="mt-4 flex gap-3 rounded-lg border-l-4 border-amber-400 bg-amber-50 p-4"
          >
            <IconWarning size="md" class="flex-shrink-0 text-amber-600" />
            <div>
              <p class="text-sm font-medium text-amber-800">
                This appointment is marked as completed.
              </p>
              <p class="mt-1 text-sm text-amber-700">
                This action is logged in your audit history for your protection.
              </p>
            </div>
          </div>

          <!-- Optional Reason -->
          <div class="mt-4">
            <label
              for="deletion-reason"
              class="mb-1.5 block text-sm font-medium text-slate-700"
            >
              Why are you deleting this? (optional)
            </label>
            <textarea
              id="deletion-reason"
              v-model="reason"
              class="mt-2 min-h-[80px] w-full rounded-lg border border-slate-300 px-3 py-2 text-base text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none sm:text-sm"
              rows="3"
              placeholder="e.g., Duplicate entry"
            ></textarea>

            <!-- Quick-pick Suggestions -->
            <div class="mt-2 flex flex-wrap gap-2">
              <button
                v-for="suggestion in reasonSuggestions"
                :key="suggestion"
                @click="applySuggestion(suggestion)"
                type="button"
                class="rounded bg-slate-100 px-2 py-1 text-xs text-slate-600 transition-colors hover:bg-slate-200 hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400"
              >
                {{ suggestion }}
              </button>
            </div>
          </div>

          <!-- Actions -->
          <div class="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-end">
            <button
              @click="handleCancel"
              type="button"
              :disabled="isDeleting"
              class="order-2 inline-flex min-h-[44px] w-full items-center justify-center rounded-lg px-4 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 sm:order-1 sm:w-auto"
            >
              Cancel
            </button>
            <button
              @click="handleDeleteClick"
              type="button"
              :disabled="isDeleting || loadingSession"
              class="order-1 inline-flex min-h-[44px] w-full items-center justify-center gap-2 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-red-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 sm:order-2 sm:w-auto"
            >
              <LoadingSpinner v-if="isDeleting" size="sm" color="blue" />
              <span>{{
                isDeleting
                  ? 'Deleting...'
                  : loadingSession
                    ? 'Loading...'
                    : 'Delete Appointment'
              }}</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Stage 2: Final Confirmation (only if session note exists) -->
    <Transition
      enter-active-class="transition-all duration-150 ease-out"
      leave-active-class="transition-all duration-150 ease-in"
      enter-from-class="opacity-0 scale-95"
      enter-to-class="opacity-100 scale-100"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <div
        v-if="open && appointment && showFinalConfirmation"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-appointment-stage-2-title"
      >
        <div class="w-full max-w-md rounded-xl bg-white p-6 shadow-xl" @click.stop>
          <!-- Header -->
          <h3
            id="delete-appointment-stage-2-title"
            class="text-lg font-semibold text-slate-900"
          >
            Final Confirmation
          </h3>

          <!-- Warning: What will be deleted -->
          <div
            class="mt-4 flex gap-3 rounded-lg border-l-4 border-amber-400 bg-amber-50 p-4"
          >
            <IconWarning size="md" class="flex-shrink-0 text-amber-600" />
            <div>
              <p class="text-sm font-medium text-amber-800">
                This will permanently delete:
              </p>
              <ul class="mt-2 space-y-1 text-sm text-amber-700">
                <li>
                  • The appointment ({{
                    formatDate(appointment.scheduled_start, "MMM d 'at' h:mm a")
                  }})
                </li>
                <li v-if="sessionNoteAction === 'delete'">
                  • Session note ({{ sessionNoteWordCount }} words, 30-day recovery)
                </li>
                <li v-if="sessionNoteAction === 'delete' && sessionNoteAttachments > 0">
                  • {{ sessionNoteAttachments }} attached file(s)
                </li>
                <li
                  v-if="sessionNoteAction === 'keep'"
                  class="font-medium text-blue-700"
                >
                  ✓ Session note will be kept ({{ sessionNoteWordCount }} words
                  preserved)
                </li>
              </ul>
            </div>
          </div>

          <!-- Audit trail info -->
          <div class="mt-4 rounded-lg border-l-4 border-blue-400 bg-blue-50 p-4">
            <div class="flex gap-3">
              <svg
                class="h-5 w-5 flex-shrink-0 text-blue-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <p class="text-sm text-blue-800">
                This action is logged in your audit history, including who deleted it
                and when. The audit log provides protection in case of disputes.
              </p>
            </div>
          </div>

          <!-- Actions -->
          <div class="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-end">
            <button
              @click="goBack"
              type="button"
              :disabled="isDeleting"
              class="order-2 inline-flex min-h-[44px] w-full items-center justify-center rounded-lg px-4 py-2.5 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 sm:order-1 sm:w-auto"
            >
              Go Back
            </button>
            <button
              @click="handleFinalConfirm"
              type="button"
              :disabled="isDeleting"
              class="order-1 inline-flex min-h-[44px] w-full items-center justify-center gap-2 rounded-lg bg-red-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-red-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 sm:order-2 sm:w-auto"
            >
              <LoadingSpinner v-if="isDeleting" size="sm" color="blue" />
              <span>{{ isDeleting ? 'Deleting...' : 'Yes, Delete Everything' }}</span>
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>
