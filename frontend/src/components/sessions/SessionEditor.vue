<script setup lang="ts">
/**
 * SessionEditor Component
 *
 * SOAP notes editor with autosave functionality for clinical session documentation.
 *
 * Features:
 * - 4 text areas for SOAP fields (Subjective, Objective, Assessment, Plan)
 * - Session metadata inputs (date, duration)
 * - Autosave every 5 seconds after typing stops
 * - Draft/finalized status indicator with "Saved X ago" timestamp
 * - "Finalize" button to lock the note
 * - Loading states during save operations
 * - Character count for each SOAP field (5000 max)
 * - Read-only mode for finalized sessions
 *
 * Usage:
 *   <SessionEditor :session-id="sessionId" @finalized="handleFinalized" />
 */

import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { onKeyStroke } from '@vueuse/core'
import { useAutosave } from '@/composables/useAutosave'
import { useLocalStorage } from '@vueuse/core'
import { formatDistanceToNow } from 'date-fns'
import apiClient from '@/api/client'
import type { AxiosError } from 'axios'
import SessionNoteBadges from './SessionNoteBadges.vue'
import SessionVersionHistory from './SessionVersionHistory.vue'
import SessionAmendmentIndicator from './SessionAmendmentIndicator.vue'

interface Props {
  sessionId: string
}

interface Emits {
  (e: 'finalized'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// Session data interface matching backend SessionResponse
interface SessionData {
  id: string
  client_id: string
  workspace_id: string
  subjective: string | null
  objective: string | null
  assessment: string | null
  plan: string | null
  session_date: string
  duration_minutes: number | null
  is_draft: boolean
  draft_last_saved_at: string | null
  finalized_at: string | null
  amended_at?: string | null
  amendment_count?: number
  version: number
  created_at: string
  updated_at: string
}

// Local form state
const formData = ref({
  subjective: '',
  objective: '',
  assessment: '',
  plan: '',
  session_date: '',
  duration_minutes: null as number | null,
})

// Original data for unsaved changes detection
const originalData = ref({ ...formData.value })

// Session metadata
const session = ref<SessionData | null>(null)
const isLoading = ref(true)
const loadError = ref<string | null>(null)

// Finalize state
const isFinalizing = ref(false)
const finalizeError = ref<string | null>(null)

// SOAP Guide state (P1-3: Onboarding guidance)
// Track if user has dismissed SOAP guide (persisted in localStorage)
const showSoapGuide = useLocalStorage('pazpaz-show-soap-guide', true)

function dismissSoapGuide() {
  showSoapGuide.value = false
}

// Version history modal state
const showVersionHistory = ref(false)

// Character limits
const CHAR_LIMIT = 5000

// Character counts
const subjectiveCount = computed(() => formData.value.subjective.length)
const objectiveCount = computed(() => formData.value.objective.length)
const assessmentCount = computed(() => formData.value.assessment.length)
const planCount = computed(() => formData.value.plan.length)

// Character count helpers
function getCharCountClass(count: number): string {
  if (count > CHAR_LIMIT) return 'text-red-600'
  if (count > CHAR_LIMIT * 0.9) return 'text-yellow-600'
  return 'text-slate-500'
}

// Computed properties
const isFinalized = computed(() => session.value?.is_draft === false)

const hasContent = computed(() => {
  return (
    formData.value.subjective.trim() !== '' ||
    formData.value.objective.trim() !== '' ||
    formData.value.assessment.trim() !== '' ||
    formData.value.plan.trim() !== ''
  )
})

const hasUnsavedChanges = computed(() => {
  if (isFinalized.value) return false

  return (
    formData.value.subjective !== originalData.value.subjective ||
    formData.value.objective !== originalData.value.objective ||
    formData.value.assessment !== originalData.value.assessment ||
    formData.value.plan !== originalData.value.plan ||
    formData.value.session_date !== originalData.value.session_date ||
    formData.value.duration_minutes !== originalData.value.duration_minutes
  )
})

// Autosave setup
const {
  isSaving,
  saveError,
  save: triggerAutosave,
  forceSave,
  stop: stopAutosave,
} = useAutosave<Record<string, unknown>>(
  async (data) => {
    // Allow saving finalized notes - backend will track amendments
    // Use appropriate endpoint based on finalization status
    if (isFinalized.value) {
      // Save as amendment to finalized note
      await apiClient.patch(`/sessions/${props.sessionId}/amend`, data)
    } else {
      // Save as draft
      await apiClient.patch(`/sessions/${props.sessionId}/draft`, data)
    }

    // Update original data after successful save
    originalData.value = { ...formData.value }
  },
  {
    debounceMs: 5000,
    onSuccess: () => {
      // Reload session to get updated draft_last_saved_at
      loadSession(true) // silent reload
    },
  }
)

// Last saved display
const lastSavedDisplay = computed(() => {
  if (isSaving.value) {
    return 'Saving...'
  }

  if (saveError.value) {
    return 'Save failed'
  }

  if (session.value?.draft_last_saved_at) {
    try {
      const distance = formatDistanceToNow(
        new Date(session.value.draft_last_saved_at),
        {
          addSuffix: true,
        }
      )
      return `Saved ${distance}`
    } catch {
      return 'Saved recently'
    }
  }

  return 'Not saved yet'
})

// Load session data
async function loadSession(silent = false) {
  if (!silent) {
    isLoading.value = true
  }
  loadError.value = null

  try {
    const response = await apiClient.get<SessionData>(`/sessions/${props.sessionId}`)
    session.value = response.data

    // Populate form
    formData.value = {
      subjective: response.data.subjective || '',
      objective: response.data.objective || '',
      assessment: response.data.assessment || '',
      plan: response.data.plan || '',
      session_date: response.data.session_date || '',
      duration_minutes: response.data.duration_minutes,
    }

    // Update original data
    originalData.value = { ...formData.value }
  } catch (error) {
    console.error('Failed to load session:', error)
    const axiosError = error as AxiosError<{ detail?: string }>

    if (axiosError.response?.status === 404) {
      loadError.value = 'Session not found'
    } else {
      loadError.value = axiosError.response?.data?.detail || 'Failed to load session'
    }
  } finally {
    if (!silent) {
      isLoading.value = false
    }
  }
}

// Handle field changes
function handleFieldChange() {
  // Allow editing finalized notes - changes will be tracked as amendments
  // Backend will handle version history and amendment tracking

  // Trigger autosave with current form data
  triggerAutosave({
    subjective: formData.value.subjective || null,
    objective: formData.value.objective || null,
    assessment: formData.value.assessment || null,
    plan: formData.value.plan || null,
    duration_minutes: formData.value.duration_minutes,
  })
}

// Finalize session
async function finalizeSession() {
  if (!hasContent.value) {
    finalizeError.value =
      'Cannot finalize empty session. Add content to at least one field.'
    return
  }

  if (
    !confirm('Finalize this session? You will not be able to edit it after finalizing.')
  ) {
    return
  }

  isFinalizing.value = true
  finalizeError.value = null

  try {
    // Force save current data before finalizing
    await forceSave({
      subjective: formData.value.subjective || null,
      objective: formData.value.objective || null,
      assessment: formData.value.assessment || null,
      plan: formData.value.plan || null,
      duration_minutes: formData.value.duration_minutes,
    })

    // Call finalize endpoint
    await apiClient.post(`/sessions/${props.sessionId}/finalize`)

    // Reload session to get finalized status
    await loadSession(true)

    emit('finalized')
  } catch (error) {
    console.error('Failed to finalize session:', error)
    const axiosError = error as AxiosError<{ detail?: string }>
    finalizeError.value =
      axiosError.response?.data?.detail || 'Failed to finalize session'
  } finally {
    isFinalizing.value = false
  }
}

// P2-2: Keyboard shortcut for finalize (Cmd+Enter / Ctrl+Enter)
onKeyStroke(['Meta+Enter', 'Control+Enter'], (e) => {
  // Only trigger if session is draft, has content, and not already finalizing
  if (!isFinalized.value && hasContent.value && !isFinalizing.value) {
    e.preventDefault()
    finalizeSession()
  }
})

// Note: Removed unsaved changes warning - autosave handles persistence automatically
// Users can safely navigate away as changes are saved every 5 seconds

// Lifecycle hooks
onMounted(() => {
  loadSession()
})

onBeforeUnmount(() => {
  stopAutosave()
})

// Format date for datetime-local input
function formatDateForInput(dateString: string): string {
  if (!dateString) return ''
  try {
    const date = new Date(dateString)
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    return `${year}-${month}-${day}T${hours}:${minutes}`
  } catch {
    return ''
  }
}

// Watch session_date for formatting
watch(
  () => session.value?.session_date,
  (newDate) => {
    if (newDate) {
      formData.value.session_date = formatDateForInput(newDate)
    }
  }
)
</script>

<template>
  <div class="session-editor">
    <!-- Loading State -->
    <div v-if="isLoading" class="flex items-center justify-center py-12">
      <div class="text-center">
        <div
          class="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent"
        ></div>
        <p class="text-sm text-slate-600">Loading session...</p>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="loadError" class="rounded-lg border border-red-200 bg-red-50 p-4">
      <p class="text-sm font-medium text-red-800">{{ loadError }}</p>
    </div>

    <!-- Session Editor -->
    <div v-else class="space-y-6">
      <!-- SOAP Guide Panel (P1-3: Onboarding for first-time users) -->
      <div
        v-if="showSoapGuide && session?.is_draft"
        class="rounded-lg border border-blue-200 bg-blue-50 p-4"
      >
        <div class="flex items-start justify-between gap-3">
          <div class="flex items-start gap-3">
            <svg
              class="mt-0.5 h-5 w-5 flex-shrink-0 text-blue-600"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <div class="flex-1">
              <h3 class="text-sm font-semibold text-blue-900">SOAP Note Guide</h3>
              <div class="mt-2 space-y-2 text-sm text-blue-800">
                <div>
                  <strong>S - Subjective:</strong> What the patient reports
                  <span class="mt-0.5 block text-xs text-blue-700">
                    Example: "Patient states shoulder pain started 2 weeks ago after
                    gardening..."
                  </span>
                </div>
                <div>
                  <strong>O - Objective:</strong> What you observe & measure
                  <span class="mt-0.5 block text-xs text-blue-700">
                    Example: "ROM: 120° abduction, palpation reveals tenderness at
                    supraspinatus insertion..."
                  </span>
                </div>
                <div>
                  <strong>A - Assessment:</strong> Your clinical interpretation
                  <span class="mt-0.5 block text-xs text-blue-700">
                    Example: "Likely rotator cuff tendinitis, moderate severity..."
                  </span>
                </div>
                <div>
                  <strong>P - Plan:</strong> Treatment plan & next steps
                  <span class="mt-0.5 block text-xs text-blue-700">
                    Example: "Ice 15min 3x/day, gentle ROM exercises, follow-up in 1
                    week..."
                  </span>
                </div>
              </div>
            </div>
          </div>
          <button
            @click="dismissSoapGuide"
            class="text-blue-600 hover:text-blue-800"
            aria-label="Dismiss SOAP guide"
          >
            <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      </div>

      <!-- Amendment Indicator -->
      <SessionAmendmentIndicator
        v-if="session && session.amendment_count && session.amendment_count > 0"
        :amendment-count="session.amendment_count"
        :amended-at="session.amended_at"
        @view-history="showVersionHistory = true"
      />

      <!-- Status Bar -->
      <div class="flex items-center justify-between border-b border-slate-200 pb-4">
        <div class="flex items-center gap-3">
          <!-- Session Note Badges Component -->
          <SessionNoteBadges v-if="session" :session="session" />

          <!-- View Version History Button (if amended) -->
          <button
            v-if="session?.amended_at"
            @click="showVersionHistory = true"
            type="button"
            class="text-sm text-blue-600 hover:text-blue-700 focus:outline-none focus:underline"
          >
            View Original Version
          </button>

          <!-- Last Saved Indicator -->
          <span
            class="text-sm"
            :class="{
              'text-slate-600': !isSaving && !saveError,
              'text-blue-600': isSaving,
              'text-red-600': saveError,
            }"
            aria-live="polite"
            aria-atomic="true"
          >
            {{ lastSavedDisplay }}
          </span>
        </div>

        <!-- Finalize/Save Button -->
        <button
          v-if="!isFinalized"
          type="button"
          :disabled="!hasContent || isFinalizing"
          @click="finalizeSession"
          class="group inline-flex items-center rounded-md bg-green-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-green-700 focus:ring-2 focus:ring-green-600 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-500"
        >

          <svg
            v-if="isFinalizing"
            class="mr-2 h-4 w-4 animate-spin"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              class="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              stroke-width="4"
            ></circle>
            <path
              class="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            ></path>
          </svg>
          {{ isFinalizing ? 'Finalizing...' : 'Finalize Session' }}
          <kbd
            v-if="!isFinalizing"
            class="ml-2 rounded bg-green-700 px-1.5 py-0.5 font-mono text-xs text-green-100 opacity-0 transition-opacity group-hover:opacity-100"
          >
            ⌘↵
          </kbd>
        </button>
      </div>

      <!-- Finalize Error -->
      <div v-if="finalizeError" class="rounded-lg border border-red-200 bg-red-50 p-3">
        <p class="text-sm text-red-800">{{ finalizeError }}</p>
      </div>

      <!-- Save Error -->
      <div v-if="saveError" class="rounded-lg border border-red-200 bg-red-50 p-3">
        <p class="text-sm text-red-800">{{ saveError }}</p>
      </div>

      <!-- Info Message: Editing Finalized Note -->
      <div
        v-if="isFinalized && !session?.amended_at"
        class="flex gap-3 rounded-lg border-l-4 border-blue-400 bg-blue-50 p-4"
      >
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
        <p class="text-sm leading-relaxed text-blue-800">
          You're editing a finalized note. Changes will be marked as amendments and the
          original preserved.
        </p>
      </div>

      <!-- Session Metadata -->
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <label for="session-date" class="block text-sm font-medium text-slate-700">
            Session Date & Time
          </label>
          <input
            id="session-date"
            v-model="formData.session_date"
            type="datetime-local"
            @change="handleFieldChange"
            class="mt-1 block w-full rounded-md border-slate-300 shadow-sm transition-colors focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
          />
        </div>

        <div>
          <label for="duration" class="block text-sm font-medium text-slate-700">
            Duration (minutes)
          </label>
          <input
            id="duration"
            v-model.number="formData.duration_minutes"
            type="number"
            min="0"
            max="480"
            @input="handleFieldChange"
            placeholder="60"
            class="mt-1 block w-full rounded-md border-slate-300 shadow-sm transition-colors focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
          />
        </div>
      </div>

      <!-- SOAP Fields -->
      <div class="space-y-6">
        <!-- Subjective -->
        <div>
          <div class="mb-1 flex items-center justify-between">
            <label for="subjective" class="block text-sm font-semibold text-slate-900">
              Subjective
            </label>
            <span class="text-xs" :class="getCharCountClass(subjectiveCount)">
              {{ subjectiveCount }} / {{ CHAR_LIMIT }}
            </span>
          </div>
          <p class="mb-2 text-xs text-slate-600">
            Patient-reported symptoms, complaints, and history
          </p>
          <textarea
            id="subjective"
            v-model="formData.subjective"
            :maxlength="CHAR_LIMIT"
            @input="handleFieldChange"
            rows="6"
            placeholder="What did the patient tell you about their condition?"
            class="block w-full rounded-md border-slate-300 shadow-sm transition-colors focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
          ></textarea>
        </div>

        <!-- Objective -->
        <div>
          <div class="mb-1 flex items-center justify-between">
            <label for="objective" class="block text-sm font-semibold text-slate-900">
              Objective
            </label>
            <span class="text-xs" :class="getCharCountClass(objectiveCount)">
              {{ objectiveCount }} / {{ CHAR_LIMIT }}
            </span>
          </div>
          <p class="mb-2 text-xs text-slate-600">
            Therapist observations, measurements, and test results
          </p>
          <textarea
            id="objective"
            v-model="formData.objective"
            :maxlength="CHAR_LIMIT"
            @input="handleFieldChange"
            rows="6"
            placeholder="What did you observe during the examination?"
            class="block w-full rounded-md border-slate-300 shadow-sm transition-colors focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
          ></textarea>
        </div>

        <!-- Assessment -->
        <div>
          <div class="mb-1 flex items-center justify-between">
            <label for="assessment" class="block text-sm font-semibold text-slate-900">
              Assessment
            </label>
            <span class="text-xs" :class="getCharCountClass(assessmentCount)">
              {{ assessmentCount }} / {{ CHAR_LIMIT }}
            </span>
          </div>
          <p class="mb-2 text-xs text-slate-600">
            Clinical interpretation and diagnosis
          </p>
          <textarea
            id="assessment"
            v-model="formData.assessment"
            :maxlength="CHAR_LIMIT"
            @input="handleFieldChange"
            rows="6"
            placeholder="What is your clinical assessment of the patient's condition?"
            class="block w-full rounded-md border-slate-300 shadow-sm transition-colors focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
          ></textarea>
        </div>

        <!-- Plan -->
        <div>
          <div class="mb-1 flex items-center justify-between">
            <label for="plan" class="block text-sm font-semibold text-slate-900">
              Plan
            </label>
            <span class="text-xs" :class="getCharCountClass(planCount)">
              {{ planCount }} / {{ CHAR_LIMIT }}
            </span>
          </div>
          <p class="mb-2 text-xs text-slate-600">
            Treatment plan, next steps, and follow-up
          </p>
          <textarea
            id="plan"
            v-model="formData.plan"
            :maxlength="CHAR_LIMIT"
            @input="handleFieldChange"
            rows="6"
            placeholder="What is the treatment plan going forward?"
            class="block w-full rounded-md border-slate-300 shadow-sm transition-colors focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
          ></textarea>
        </div>
      </div>
    </div>

    <!-- Session Version History Modal -->
    <SessionVersionHistory
      v-if="session"
      :session-id="props.sessionId"
      :session="session"
      :open="showVersionHistory"
      @close="showVersionHistory = false"
    />
  </div>
</template>

<style scoped>
/* Additional styles if needed */
</style>
