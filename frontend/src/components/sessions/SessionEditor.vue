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
 * - Unsaved changes warning when navigating away
 * - Read-only mode for finalized sessions
 *
 * Usage:
 *   <SessionEditor :session-id="sessionId" @finalized="handleFinalized" />
 */

import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { useAutosave } from '@/composables/useAutosave'
import { formatDistanceToNow } from 'date-fns'
import apiClient from '@/api/client'
import type { AxiosError } from 'axios'

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
    if (isFinalized.value) {
      console.warn('Cannot autosave finalized session')
      return
    }

    await apiClient.patch(`/sessions/${props.sessionId}/draft`, data)

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
      const distance = formatDistanceToNow(new Date(session.value.draft_last_saved_at), {
        addSuffix: true,
      })
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
  if (isFinalized.value) return

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
    finalizeError.value = 'Cannot finalize empty session. Add content to at least one field.'
    return
  }

  if (!confirm('Finalize this session? You will not be able to edit it after finalizing.')) {
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
    finalizeError.value = axiosError.response?.data?.detail || 'Failed to finalize session'
  } finally {
    isFinalizing.value = false
  }
}

// Unsaved changes warning
onBeforeRouteLeave((_to, _from, next) => {
  if (hasUnsavedChanges.value && !isFinalized.value) {
    const answer = window.confirm(
      'You have unsaved changes. Are you sure you want to leave? Changes are autosaved every 5 seconds.'
    )
    if (!answer) {
      return next(false)
    }
  }
  next()
})

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
        <div class="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-blue-600 border-t-transparent"></div>
        <p class="text-sm text-slate-600">Loading session...</p>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="loadError" class="rounded-lg border border-red-200 bg-red-50 p-4">
      <p class="text-sm font-medium text-red-800">{{ loadError }}</p>
    </div>

    <!-- Session Editor -->
    <div v-else class="space-y-6">
      <!-- Status Bar -->
      <div class="flex items-center justify-between border-b border-slate-200 pb-4">
        <div class="flex items-center gap-3">
          <!-- Draft/Finalized Badge -->
          <span
            v-if="isFinalized"
            class="inline-flex items-center rounded-full bg-green-100 px-3 py-1 text-sm font-medium text-green-800"
          >
            <svg class="mr-1.5 h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
            </svg>
            Finalized
          </span>
          <span
            v-else
            class="inline-flex items-center rounded-full bg-blue-100 px-3 py-1 text-sm font-medium text-blue-800"
          >
            <svg class="mr-1.5 h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd" />
            </svg>
            Draft
          </span>

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

        <!-- Finalize Button -->
        <button
          v-if="!isFinalized"
          type="button"
          :disabled="!hasContent || isFinalizing"
          @click="finalizeSession"
          class="inline-flex items-center rounded-md bg-green-600 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-green-600 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-500"
        >
          <svg
            v-if="isFinalizing"
            class="mr-2 h-4 w-4 animate-spin"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          {{ isFinalizing ? 'Finalizing...' : 'Finalize Session' }}
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
            :disabled="isFinalized"
            @change="handleFieldChange"
            class="mt-1 block w-full rounded-md border-slate-300 shadow-sm transition-colors focus:border-blue-500 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 sm:text-sm"
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
            :disabled="isFinalized"
            @input="handleFieldChange"
            placeholder="60"
            class="mt-1 block w-full rounded-md border-slate-300 shadow-sm transition-colors focus:border-blue-500 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 sm:text-sm"
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
            <span
              class="text-xs"
              :class="getCharCountClass(subjectiveCount)"
            >
              {{ subjectiveCount }} / {{ CHAR_LIMIT }}
            </span>
          </div>
          <p class="mb-2 text-xs text-slate-600">
            Patient-reported symptoms, complaints, and history
          </p>
          <textarea
            id="subjective"
            v-model="formData.subjective"
            :disabled="isFinalized"
            :maxlength="CHAR_LIMIT"
            @input="handleFieldChange"
            rows="6"
            placeholder="What did the patient tell you about their condition?"
            class="block w-full rounded-md border-slate-300 shadow-sm transition-colors focus:border-blue-500 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 sm:text-sm"
          ></textarea>
        </div>

        <!-- Objective -->
        <div>
          <div class="mb-1 flex items-center justify-between">
            <label for="objective" class="block text-sm font-semibold text-slate-900">
              Objective
            </label>
            <span
              class="text-xs"
              :class="getCharCountClass(objectiveCount)"
            >
              {{ objectiveCount }} / {{ CHAR_LIMIT }}
            </span>
          </div>
          <p class="mb-2 text-xs text-slate-600">
            Therapist observations, measurements, and test results
          </p>
          <textarea
            id="objective"
            v-model="formData.objective"
            :disabled="isFinalized"
            :maxlength="CHAR_LIMIT"
            @input="handleFieldChange"
            rows="6"
            placeholder="What did you observe during the examination?"
            class="block w-full rounded-md border-slate-300 shadow-sm transition-colors focus:border-blue-500 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 sm:text-sm"
          ></textarea>
        </div>

        <!-- Assessment -->
        <div>
          <div class="mb-1 flex items-center justify-between">
            <label for="assessment" class="block text-sm font-semibold text-slate-900">
              Assessment
            </label>
            <span
              class="text-xs"
              :class="getCharCountClass(assessmentCount)"
            >
              {{ assessmentCount }} / {{ CHAR_LIMIT }}
            </span>
          </div>
          <p class="mb-2 text-xs text-slate-600">
            Clinical interpretation and diagnosis
          </p>
          <textarea
            id="assessment"
            v-model="formData.assessment"
            :disabled="isFinalized"
            :maxlength="CHAR_LIMIT"
            @input="handleFieldChange"
            rows="6"
            placeholder="What is your clinical assessment of the patient's condition?"
            class="block w-full rounded-md border-slate-300 shadow-sm transition-colors focus:border-blue-500 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 sm:text-sm"
          ></textarea>
        </div>

        <!-- Plan -->
        <div>
          <div class="mb-1 flex items-center justify-between">
            <label for="plan" class="block text-sm font-semibold text-slate-900">
              Plan
            </label>
            <span
              class="text-xs"
              :class="getCharCountClass(planCount)"
            >
              {{ planCount }} / {{ CHAR_LIMIT }}
            </span>
          </div>
          <p class="mb-2 text-xs text-slate-600">
            Treatment plan, next steps, and follow-up
          </p>
          <textarea
            id="plan"
            v-model="formData.plan"
            :disabled="isFinalized"
            :maxlength="CHAR_LIMIT"
            @input="handleFieldChange"
            rows="6"
            placeholder="What is the treatment plan going forward?"
            class="block w-full rounded-md border-slate-300 shadow-sm transition-colors focus:border-blue-500 focus:ring-blue-500 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 sm:text-sm"
          ></textarea>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Additional styles if needed */
</style>
