<script setup lang="ts">
/**
 * SessionCard Component
 *
 * Individual session note card for timeline display with inline deletion.
 * Features:
 * - Clickable card to view session (primary action)
 * - Trash icon for deletion (secondary action, hover-visible on desktop, always visible on mobile)
 * - Inline deletion confirmation (no browser alerts)
 * - Extra warning for finalized notes (medical records)
 * - Smooth animations on deletion
 * - Full keyboard accessibility
 * - Professional UX patterns
 *
 * Usage:
 *   <SessionCard :session="session" @deleted="handleDeleted" @view="handleView">
 *     <template #content>
 *       <!-- Card content slot -->
 *     </template>
 *   </SessionCard>
 */

import { ref } from 'vue'
import IconWarning from '@/components/icons/IconWarning.vue'
import { useToast } from '@/composables/useToast'
import apiClient from '@/api/client'
import type { AxiosError } from 'axios'
import type { SessionResponse } from '@/types/sessions'

interface Props {
  session: SessionResponse
}

interface Emits {
  (e: 'deleted', sessionId: string): void
  (e: 'view', sessionId: string): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()
const { showSuccess, showError } = useToast()

// State
const showDeleteConfirmation = ref(false)
const isDeleting = ref(false)

/**
 * Handle card click to view session
 */
function handleViewClick() {
  emit('view', props.session.id)
}

/**
 * Handle delete button click
 */
function handleDeleteClick() {
  showDeleteConfirmation.value = true
}

/**
 * Cancel deletion and return to normal card state
 */
function cancelDelete() {
  showDeleteConfirmation.value = false
}

/**
 * Confirm and execute deletion
 */
async function confirmDelete() {
  isDeleting.value = true

  try {
    // Soft delete the session (30-day grace period)
    await apiClient.delete(`/sessions/${props.session.id}`)

    // Notify parent to remove from list
    emit('deleted', props.session.id)

    // Show success toast
    showSuccess('Session note deleted. Undo available for 30 days.')
  } catch (error) {
    console.error('[SessionCard] Delete failed:', error)

    // Handle specific error cases
    const axiosError = error as AxiosError<{ detail?: string; status?: number }>
    const status = axiosError.response?.status
    const detail = axiosError.response?.data?.detail

    if (status === 404) {
      showError('Session note no longer exists')
      // Remove from UI since it's already gone
      emit('deleted', props.session.id)
    } else if (status === 403) {
      showError("You don't have permission to delete this note")
    } else if (status === 410) {
      showError('This note has already been deleted')
      // Remove from UI
      emit('deleted', props.session.id)
    } else if (status === 422) {
      showError('Cannot delete amended notes due to medical-legal requirements')
    } else {
      showError(detail || 'Failed to delete note - please try again')
    }

    // Revert confirmation state on error
    showDeleteConfirmation.value = false
  } finally {
    isDeleting.value = false
  }
}

/**
 * Handle Escape key in confirmation state
 */
function handleEscape(e: KeyboardEvent) {
  if (e.key === 'Escape' && showDeleteConfirmation.value) {
    cancelDelete()
  }
}
</script>

<template>
  <!-- Normal Card State: Clickable Card with Trash Icon -->
  <button
    v-if="!showDeleteConfirmation"
    type="button"
    @click="handleViewClick"
    :aria-label="`Session from ${new Date(session.session_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}. ${session.is_draft ? 'Draft' : 'Finalized'}. Click to view full note.`"
    class="group relative w-full rounded-lg border border-slate-200 bg-white p-4 text-left transition-all hover:border-blue-300 hover:bg-blue-50 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
  >
    <!-- Session Card Content (slot) -->
    <div class="pointer-events-none">
      <slot name="content" />
    </div>

    <!-- Delete Button: Hidden on hover (desktop), always visible (mobile) -->
    <div
      class="absolute end-3 top-3 opacity-0 transition-opacity group-hover:opacity-100 md:opacity-100"
    >
      <button
        type="button"
        @click.stop="handleDeleteClick"
        class="pointer-events-auto rounded-md p-2 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
        aria-label="Delete session note"
      >
        <svg
          class="h-5 w-5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
          />
        </svg>
      </button>
    </div>
  </button>

  <!-- Delete Confirmation State -->
  <div
    v-else
    role="alertdialog"
    aria-labelledby="delete-confirmation-title"
    aria-describedby="delete-confirmation-description"
    class="rounded-lg border border-amber-200 bg-amber-50 p-6"
    @keydown="handleEscape"
  >
    <div class="flex items-start gap-3">
      <!-- Warning Icon -->
      <IconWarning size="md" class="mt-0.5 flex-shrink-0 text-amber-600" />

      <div class="flex-1">
        <h3
          id="delete-confirmation-title"
          class="text-base font-semibold text-slate-900"
        >
          Delete this {{ session.finalized_at ? 'finalized ' : '' }}session note?
        </h3>
        <p
          id="delete-confirmation-description"
          class="mt-2 text-sm leading-relaxed text-slate-700"
        >
          <template v-if="session.finalized_at">
            ⚠️ This is a medical record. It
          </template>
          <template v-else> This note </template>
          will be moved to Deleted Notes for 30 days, during which you can restore it.
        </p>
      </div>
    </div>

    <!-- Actions -->
    <div class="mt-4 flex justify-end gap-3">
      <button
        @click="cancelDelete"
        :disabled="isDeleting"
        class="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
      >
        Cancel
      </button>
      <button
        @click="confirmDelete"
        :disabled="isDeleting"
        class="rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <span v-if="isDeleting">Deleting...</span>
        <span v-else>Delete Note</span>
      </button>
    </div>
  </div>
</template>
