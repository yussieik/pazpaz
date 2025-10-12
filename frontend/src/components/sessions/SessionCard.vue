<script setup lang="ts">
/**
 * SessionCard Component
 *
 * Individual session note card for timeline display with inline deletion.
 * Features:
 * - Touch-optimized kebab menu with actions (always visible on mobile)
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

import { ref, computed } from 'vue'
import KebabMenu from '@/components/common/KebabMenu.vue'
import type { MenuItem } from '@/components/common/KebabMenu.vue'
import { useToast } from '@/composables/useToast'
import apiClient from '@/api/client'
import type { AxiosError } from 'axios'

interface SessionItem {
  id: string
  client_id: string
  appointment_id: string | null
  subjective: string | null
  objective: string | null
  assessment: string | null
  plan: string | null
  session_date: string
  duration_minutes: number | null
  is_draft: boolean
  draft_last_saved_at: string | null
  finalized_at: string | null
}

interface Props {
  session: SessionItem
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
 * Menu items configuration for KebabMenu
 */
const menuItems = computed<MenuItem[]>(() => [
  {
    label: 'View Full Note',
    action: () => {
      emit('view', props.session.id)
    },
    shortcut: 'V',
  },
  {
    label: 'Delete Note',
    action: openDeleteConfirmation,
    destructive: true,
    divider: true,
  },
])

/**
 * Open the delete confirmation state
 */
function openDeleteConfirmation() {
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
    await apiClient.delete(`/api/v1/sessions/${props.session.id}`)

    // Notify parent to remove from list
    emit('deleted', props.session.id)

    // Show success toast
    showSuccess('Session note deleted. Undo available for 30 days.')
  } catch (error) {
    console.error('Failed to delete session:', error)

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
  <!-- Normal Card State -->
  <div
    v-if="!showDeleteConfirmation"
    class="group relative rounded-lg border border-slate-200 bg-white p-4 transition-all hover:border-slate-300 hover:shadow-md"
  >
    <!-- Kebab Menu (Touch-Optimized) -->
    <div class="absolute top-4 right-4">
      <KebabMenu
        :aria-label="`More actions for session on ${new Date(session.session_date).toLocaleDateString()}`"
        :items="menuItems"
        position="bottom-right"
        :always-visible-on-mobile="true"
      />
    </div>

    <!-- Session Card Content (slot) -->
    <slot name="content" />
  </div>

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
      <svg
        class="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-600"
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
