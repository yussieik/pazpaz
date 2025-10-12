<script setup lang="ts">
/**
 * DeletedNotesSection Component
 *
 * Displays soft-deleted session notes with restoration options
 * Features:
 * - Collapsible section with deleted note count
 * - 30-day grace period countdown
 * - Restore and permanent delete actions
 * - Handles expired grace periods
 * - Empty state when no deleted notes
 *
 * Usage:
 *   <DeletedNotesSection :client-id="clientId" @restored="handleRestore" />
 */

import { ref, computed, onMounted, watch } from 'vue'
import { useToast } from '@/composables/useToast'
import apiClient from '@/api/client'
import type { SessionResponse } from '@/types/sessions'
import { isGracePeriodExpired } from '@/types/sessions'
import {
  getDaysRemaining,
  formatRelativeTime,
  formatLongDate,
} from '@/utils/calendar/dateFormatters'
import { SESSION_DELETION_GRACE_PERIOD_DAYS } from '@/constants/sessions'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import type { AxiosError } from 'axios'

interface Props {
  clientId: string
  triggerPulse?: boolean
}

interface Emits {
  (e: 'restored'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()
const { showSuccess, showError, showInfo } = useToast()

// State
const deletedNotes = ref<SessionResponse[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const isExpanded = ref(false)
const restoringNoteId = ref<string | null>(null)
const deletingNoteId = ref<string | null>(null)

// Computed
const deletedNotesCount = computed(() => deletedNotes.value.length)
const isEmpty = computed(() => deletedNotes.value.length === 0)

// Badge pulse state
const badgeRef = ref<HTMLElement | null>(null)

// Watch for pulse trigger (when session deleted and section collapsed)
watch(
  () => props.triggerPulse,
  (shouldPulse) => {
    if (shouldPulse && !isExpanded.value && badgeRef.value) {
      // Apply pulse animation class
      badgeRef.value.classList.add('pulse-animation')
      // Remove class after animation completes
      setTimeout(() => {
        badgeRef.value?.classList.remove('pulse-animation')
      }, 600)

      // Also refresh the deleted notes list to show new deletion
      fetchDeletedNotes()
    }
  }
)

// Fetch deleted sessions
onMounted(async () => {
  await fetchDeletedNotes()
})

async function fetchDeletedNotes() {
  loading.value = true
  error.value = null

  try {
    const response = await apiClient.get<{ items: SessionResponse[] }>(
      `/sessions?client_id=${props.clientId}&include_deleted=true`
    )

    // Filter to only show deleted sessions
    deletedNotes.value = (response.data.items || []).filter(
      (session) => session.deleted_at !== null && session.deleted_at !== undefined
    )
  } catch (err) {
    console.error('Failed to fetch deleted sessions:', err)
    const axiosError = err as AxiosError<{ detail?: string }>
    error.value = axiosError.response?.data?.detail || 'Failed to load deleted notes'
  } finally {
    loading.value = false
  }
}

/**
 * Toggle expand/collapse
 */
function toggleExpanded() {
  isExpanded.value = !isExpanded.value
}

/**
 * Get preview text from session content
 */
function getPreviewText(session: SessionResponse): string {
  const content = [
    session.subjective,
    session.objective,
    session.assessment,
    session.plan,
  ]
    .filter(Boolean)
    .join(' ')

  return content.trim().substring(0, 100) + (content.length > 100 ? '...' : '')
}

/**
 * Restore a soft-deleted session
 */
async function restoreSession(session: SessionResponse) {
  console.log('[DeletedNotesSection] Attempting to restore session:', session.id)
  console.log('[DeletedNotesSection] Session data:', {
    id: session.id,
    date: session.session_date,
    deleted_at: session.deleted_at,
    permanent_delete_after: session.permanent_delete_after
  })

  // Check if grace period expired
  if (
    session.permanent_delete_after &&
    isGracePeriodExpired(session.permanent_delete_after)
  ) {
    showError('Cannot restore - grace period expired')
    return
  }

  restoringNoteId.value = session.id

  try {
    const restoreUrl = `/sessions/${session.id}/restore`
    console.log('[DeletedNotesSection] POST request to:', restoreUrl)
    await apiClient.post(restoreUrl)

    console.log('[DeletedNotesSection] Restore successful')

    // Show success
    showSuccess('Session note restored successfully')

    // Remove from local list
    deletedNotes.value = deletedNotes.value.filter((s) => s.id !== session.id)

    console.log('[DeletedNotesSection] Emitting "restored" event to parent')
    // Notify parent to refresh main timeline
    emit('restored')
  } catch (err) {
    console.error('[DeletedNotesSection] Restore failed:', err)
    const axiosError = err as AxiosError<{ detail?: string; status?: number }>

    console.error('[DeletedNotesSection] Error status:', axiosError.response?.status)
    console.error('[DeletedNotesSection] Error detail:', axiosError.response?.data?.detail)

    if (axiosError.response?.status === 410) {
      showError('Cannot restore - grace period expired')
      // Refresh to update UI
      await fetchDeletedNotes()
    } else if (axiosError.response?.status === 422) {
      showError('Cannot delete amended notes due to medical-legal requirements')
    } else {
      showError(axiosError.response?.data?.detail || 'Failed to restore session note')
    }
  } finally {
    restoringNoteId.value = null
  }
}

/**
 * Permanently delete a session
 */
async function permanentlyDeleteSession(session: SessionResponse) {
  deletingNoteId.value = session.id

  try {
    await apiClient.delete(`/sessions/${session.id}/permanent`)

    showInfo('Session note permanently deleted')

    deletedNotes.value = deletedNotes.value.filter((s) => s.id !== session.id)
  } catch (err) {
    console.error('Failed to permanently delete session:', err)
    const axiosError = err as AxiosError<{ detail?: string }>

    showError(
      axiosError.response?.data?.detail || 'Failed to permanently delete session note'
    )
  } finally {
    deletingNoteId.value = null
  }
}

/**
 * Format deletion time with "Deleted" prefix
 */
function formatDeletionTime(deletedAt: string): string {
  return `Deleted ${formatRelativeTime(deletedAt).toLowerCase()}`
}
</script>

<template>
  <div class="mt-8 border-t border-slate-200 pt-8">
    <!-- Header (collapsible trigger) -->
    <button
      @click="toggleExpanded"
      type="button"
      class="flex w-full items-center justify-between text-left transition-colors hover:text-slate-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2"
      :aria-expanded="isExpanded"
      aria-controls="deleted-notes-content"
    >
      <div class="flex items-center gap-2">
        <h3 class="text-lg font-semibold text-slate-900">Deleted Notes</h3>
        <span
          v-if="deletedNotesCount > 0"
          ref="badgeRef"
          class="deleted-notes-badge rounded-full bg-slate-100 px-2.5 py-0.5 text-sm font-medium text-slate-700"
        >
          {{ deletedNotesCount }}
        </span>
      </div>
      <svg
        class="h-5 w-5 text-slate-400 transition-transform"
        :class="{ 'rotate-180': isExpanded }"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M19 9l-7 7-7-7"
        />
      </svg>
    </button>

    <!-- Loading state -->
    <div v-if="loading" class="mt-4">
      <div class="flex items-center gap-3 text-sm text-slate-600">
        <LoadingSpinner size="md" color="slate" />
        <span>Loading deleted notes...</span>
      </div>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="mt-4 rounded-lg border border-red-200 bg-red-50 p-4">
      <div class="flex gap-3">
        <svg
          class="h-5 w-5 flex-shrink-0 text-red-600"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <div>
          <p class="text-sm font-medium text-red-800">Failed to load deleted notes</p>
          <p class="mt-1 text-sm text-red-700">{{ error }}</p>
          <button
            @click="fetchDeletedNotes"
            class="mt-2 text-sm font-medium text-red-800 underline hover:no-underline"
          >
            Try again
          </button>
        </div>
      </div>
    </div>

    <!-- Content (expanded) -->
    <Transition
      enter-active-class="transition-all duration-200 ease-out"
      leave-active-class="transition-all duration-150 ease-in"
      enter-from-class="max-h-0 opacity-0"
      enter-to-class="max-h-[2000px] opacity-100"
      leave-from-class="max-h-[2000px] opacity-100"
      leave-to-class="max-h-0 opacity-0"
    >
      <div
        v-if="isExpanded && !loading && !error"
        id="deleted-notes-content"
        class="mt-4 overflow-hidden"
      >
        <!-- Empty state -->
        <div
          v-if="isEmpty"
          class="rounded-lg border border-slate-200 bg-slate-50 p-8 text-center"
        >
          <svg
            class="mx-auto h-12 w-12 text-slate-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
            />
          </svg>
          <p class="mt-3 text-sm font-medium text-slate-900">No deleted notes</p>
          <p class="mt-1 text-sm text-slate-600">
            Deleted session notes will appear here for
            {{ SESSION_DELETION_GRACE_PERIOD_DAYS }}
            days
          </p>
        </div>

        <!-- Deleted notes list -->
        <div v-else class="space-y-3">
          <div
            v-for="session in deletedNotes"
            :key="session.id"
            class="rounded-lg border border-slate-200 bg-white p-4 shadow-sm transition-shadow hover:shadow-md"
          >
            <!-- Session date and deletion info -->
            <div class="flex items-start justify-between">
              <div class="flex-1">
                <p class="text-sm font-medium text-slate-900">
                  {{ formatLongDate(session.session_date) }}
                </p>
                <p class="mt-1 text-xs text-slate-600">
                  {{ session.deleted_at ? formatDeletionTime(session.deleted_at) : '' }}
                </p>
              </div>

              <!-- Days remaining badge -->
              <div
                v-if="
                  session.permanent_delete_after &&
                  !isGracePeriodExpired(session.permanent_delete_after)
                "
                class="flex items-center gap-1.5 rounded-full bg-amber-100 px-2.5 py-1 text-xs font-medium text-amber-800"
              >
                <svg
                  class="h-3.5 w-3.5"
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
                <span
                  >{{ getDaysRemaining(session.permanent_delete_after) }} days
                  left</span
                >
              </div>

              <!-- Expired badge -->
              <div
                v-else-if="
                  session.permanent_delete_after &&
                  isGracePeriodExpired(session.permanent_delete_after)
                "
                class="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700"
              >
                Permanently deleted
              </div>
            </div>

            <!-- Preview -->
            <div class="mt-3">
              <p class="text-sm text-slate-600">
                {{ getPreviewText(session) || 'No content' }}
              </p>
            </div>

            <!-- Deletion reason (if provided) -->
            <div v-if="session.deleted_reason" class="mt-3 rounded-md bg-slate-50 p-2">
              <p class="text-xs text-slate-600">
                <span class="font-medium">Reason:</span> {{ session.deleted_reason }}
              </p>
            </div>

            <!-- Actions -->
            <div class="mt-4 flex items-center justify-end gap-3">
              <!-- Restore button -->
              <button
                v-if="
                  session.permanent_delete_after &&
                  !isGracePeriodExpired(session.permanent_delete_after)
                "
                @click="restoreSession(session)"
                :disabled="restoringNoteId === session.id"
                class="flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <LoadingSpinner
                  v-if="restoringNoteId === session.id"
                  size="sm"
                  color="blue"
                />
                <svg
                  v-else
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
                <span>{{
                  restoringNoteId === session.id ? 'Restoring...' : 'Restore'
                }}</span>
              </button>

              <!-- Delete permanently button -->
              <button
                @click="permanentlyDeleteSession(session)"
                :disabled="deletingNoteId === session.id"
                class="flex items-center gap-1.5 rounded-md border border-red-300 bg-white px-3 py-1.5 text-sm font-medium text-red-700 transition-colors hover:bg-red-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <LoadingSpinner
                  v-if="deletingNoteId === session.id"
                  size="sm"
                  color="red"
                />
                <svg
                  v-else
                  class="h-4 w-4"
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
                <span>{{
                  deletingNoteId === session.id ? 'Deleting...' : 'Delete Forever'
                }}</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Info box -->
        <div class="mt-4 rounded-lg border border-blue-200 bg-blue-50 p-4">
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
            <div class="text-sm text-blue-900">
              <p class="font-medium">
                {{ SESSION_DELETION_GRACE_PERIOD_DAYS }}-day recovery period
              </p>
              <p class="mt-1 text-blue-800">
                Deleted session notes are kept for
                {{ SESSION_DELETION_GRACE_PERIOD_DAYS }} days before permanent deletion.
                You can restore them at any time during this period.
              </p>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
/* Badge pulse animation when session deleted */
@keyframes badgePulse {
  0% {
    box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.5);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(59, 130, 246, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(59, 130, 246, 0);
  }
}

.pulse-animation {
  animation: badgePulse 600ms ease-out;
}
</style>
