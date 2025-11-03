<script setup lang="ts">
/**
 * SessionEditor Component
 *
 * SOAP notes editor with invisible autosave for clinical session documentation.
 *
 * Features:
 * - 4 text areas for SOAP fields (Subjective, Objective, Assessment, Plan)
 * - Session metadata inputs (date, duration)
 * - Three-tier invisible autosave:
 *   - Tier 1: Instant local persistence (0ms latency to localStorage)
 *   - Tier 2: Debounced server sync (750ms after typing stops)
 *   - Tier 3: Strategic immediate syncs (field blur, finalize, Ctrl+S, navigation)
 * - Contextual banners (only shows for offline/error states)
 * - Draft/finalized status indicator
 * - "Finalize" button to lock the note
 * - Character count for each SOAP field (5000 max)
 * - Keyboard shortcuts: Cmd+Enter (finalize), Cmd+S (immediate save)
 *
 * Usage:
 *   <SessionEditor :session-id="sessionId" @finalized="handleFinalized" />
 */

import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { onKeyStroke } from '@vueuse/core'
import { useI18n } from '@/composables/useI18n'
import { useInvisibleAutosave } from '@/composables/useInvisibleAutosave'
import { useSecureOfflineBackup } from '@/composables/useSecureOfflineBackup'
import { useLocalStorage } from '@vueuse/core'
import { formatDateTimeForInput } from '@/utils/calendar/dateFormatters'
import apiClient from '@/api/client'
import type { AxiosError } from 'axios'
import type { SessionResponse } from '@/types/sessions'
import type { SessionWithAmendments } from '@/types/calendar'
import SessionNoteBadges from './SessionNoteBadges.vue'
import SessionVersionHistory from './SessionVersionHistory.vue'
import SessionAmendmentIndicator from './SessionAmendmentIndicator.vue'
import PreviousSessionPanel from './PreviousSessionPanel.vue'
import PreviousSessionSummaryStrip from './PreviousSessionSummaryStrip.vue'
import SessionAttachments from './SessionAttachments.vue'
import IconWarning from '@/components/icons/IconWarning.vue'
import AutosaveBanner from '@/components/common/AutosaveBanner.vue'

const { t } = useI18n()

interface Props {
  sessionId: string
}

interface Emits {
  (e: 'finalized'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

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
const session = ref<SessionResponse | null>(null)
const isLoading = ref(true)
const loadError = ref<string | null>(null)

// Stable client_id for PreviousSessionPanel (doesn't change during finalize)
const stableClientId = ref<string | null>(null)

// Finalize state
const isFinalizing = ref(false)
const isFinalizingInProgress = ref(false) // Internal flag: suppress autosave callback only
const finalizeError = ref<string | null>(null)

// SOAP Guide state (P1-3: Onboarding guidance)
// Track if user has dismissed SOAP guide (persisted in localStorage)
const showSoapGuide = useLocalStorage('pazpaz-show-soap-guide', true)

function dismissSoapGuide() {
  showSoapGuide.value = false
}

// Version history modal state
const showVersionHistory = ref(false)

// Treatment context bottom sheet state (mobile only)
const showPreviousSessionBottomSheet = ref(false)

function openPreviousSessionBottomSheet() {
  showPreviousSessionBottomSheet.value = true
}

function closePreviousSessionBottomSheet() {
  showPreviousSessionBottomSheet.value = false
}

// Restore prompt state (encrypted localStorage backup)
const { restoreDraft, syncToServer } = useSecureOfflineBackup()
const showRestorePrompt = ref(false)
const localBackupData = ref<{
  subjective: string | null
  objective: string | null
  assessment: string | null
  plan: string | null
  session_date: string
  duration_minutes: number | null
} | null>(null)

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

// Invisible autosave setup - Three-tier architecture
const sessionIdRef = computed(() => props.sessionId)
const {
  state: autosaveState,
  flushSync,
  retryNow,
  restoreDraft: _restoreInvisibleDraft,
  clearDraft: _clearDraft,
} = useInvisibleAutosave(
  sessionIdRef,
  formData,
  async (id, data) => {
    // Always use draft endpoint for autosave
    await apiClient.patch(`/sessions/${id}/draft`, {
      subjective: data.subjective || null,
      objective: data.objective || null,
      assessment: data.assessment || null,
      plan: data.plan || null,
      duration_minutes: data.duration_minutes,
    })

    // Update original data after successful save
    originalData.value = { ...formData.value }

    // Skip timestamp update during finalize (loadSession will update everything)
    if (isFinalizingInProgress.value) {
      return
    }

    // Only update timestamp without re-rendering form
    try {
      const response = await apiClient.get<SessionResponse>(`/sessions/${id}`)
      if (session.value) {
        session.value.draft_last_saved_at = response.data.draft_last_saved_at
      }
    } catch (error) {
      // Silent failure - not critical for UX
      console.debug('Failed to update timestamp:', error)
    }
  },
  {
    debounce: 750, // 750ms debounce for invisible autosave
    onSuccess: () => {
      console.debug('[SessionEditor] Autosave successful')
    },
    onError: (error) => {
      console.error('[SessionEditor] Autosave failed:', error)
    },
  }
)

// Banner properties for invisible autosave (only shows for errors/offline)
const showBanner = computed(
  () => autosaveState.value.type === 'offline' || autosaveState.value.type === 'error'
)

const bannerSeverity = computed(() =>
  autosaveState.value.type === 'error' ? 'error' : 'warning'
)

const bannerMessage = computed(() => {
  if (autosaveState.value.type === 'offline') {
    return t('sessions.editor.autosave.offline')
  }
  if (autosaveState.value.type === 'error') {
    return t('sessions.editor.autosave.error')
  }
  return ''
})

const bannerDescription = computed(() => {
  if (autosaveState.value.type === 'offline') {
    return t('sessions.editor.autosave.willSync')
  }
  if (autosaveState.value.type === 'error') {
    return autosaveState.value.error.message
  }
  return ''
})

const bannerActions = computed(() => {
  if (autosaveState.value.type === 'error' && autosaveState.value.recoverable) {
    return [{ label: t('sessions.editor.autosave.retryButton'), onClick: retryNow }]
  }
  return []
})

// Load session data
async function loadSession(silent = false) {
  if (!silent) {
    isLoading.value = true
  }
  loadError.value = null

  try {
    const response = await apiClient.get<SessionResponse>(
      `/sessions/${props.sessionId}`
    )

    // Update session metadata
    session.value = response.data

    // Store stable client_id on first load (for PreviousSessionPanel)
    if (!stableClientId.value && response.data.client_id) {
      stableClientId.value = response.data.client_id
    }

    // Only update form if not a silent reload (prevents re-renders)
    if (!silent) {
      formData.value = {
        subjective: response.data.subjective || '',
        objective: response.data.objective || '',
        assessment: response.data.assessment || '',
        plan: response.data.plan || '',
        session_date: response.data.session_date
          ? formatDateTimeForInput(response.data.session_date)
          : '',
        duration_minutes: response.data.duration_minutes,
      }
      originalData.value = { ...formData.value }
    } else {
      // Silent reload: only update fields that user hasn't modified
      // This prevents cursor jumping and re-renders during autosave
      if (formData.value.subjective === originalData.value.subjective) {
        formData.value.subjective = response.data.subjective || ''
      }
      if (formData.value.objective === originalData.value.objective) {
        formData.value.objective = response.data.objective || ''
      }
      if (formData.value.assessment === originalData.value.assessment) {
        formData.value.assessment = response.data.assessment || ''
      }
      if (formData.value.plan === originalData.value.plan) {
        formData.value.plan = response.data.plan || ''
      }
      if (formData.value.session_date === originalData.value.session_date) {
        formData.value.session_date = response.data.session_date
          ? formatDateTimeForInput(response.data.session_date)
          : ''
      }
      if (formData.value.duration_minutes === originalData.value.duration_minutes) {
        formData.value.duration_minutes = response.data.duration_minutes
      }
      originalData.value = { ...formData.value }
    }
  } catch (error) {
    console.error('Failed to load session:', error)
    const axiosError = error as AxiosError<{ detail?: string }>

    if (axiosError.response?.status === 404) {
      loadError.value = t('sessions.view.errorNotFound')
    } else {
      loadError.value = axiosError.response?.data?.detail || t('sessions.editor.errors.loadFailed')
    }
  } finally {
    if (!silent) {
      isLoading.value = false
    }
  }
}

// Field blur handler - Tier 3: Immediate sync on field switch
function handleFieldBlur() {
  // Trigger immediate sync when user switches between fields
  flushSync()
}

// Toggle finalize status
async function toggleFinalizeStatus() {
  if (!isFinalized.value) {
    // Finalize the session
    if (!hasContent.value) {
      finalizeError.value = t('sessions.editor.finalize.errorEmpty')
      return
    }

    // Store original state for rollback
    const originalIsDraft = session.value?.is_draft
    const originalFinalizedAt = session.value?.finalized_at

    isFinalizing.value = true
    isFinalizingInProgress.value = true // Suppress autosave callback
    finalizeError.value = null

    try {
      // Force save current data before finalizing (Tier 3: Immediate sync)
      await flushSync()

      // Optimistic update: immediately update UI
      if (session.value) {
        session.value.is_draft = false
        session.value.finalized_at = new Date().toISOString()
      }

      // Background API call
      await apiClient.post<SessionResponse>(`/sessions/${props.sessionId}/finalize`, {})

      // Emit finalized event (parent will do optimistic update too)
      emit('finalized')

      // Silent background sync to ensure we have latest server state
      // Don't await this - let it happen in background
      loadSession(true)
    } catch (error) {
      console.error('Failed to finalize session:', error)
      const axiosError = error as AxiosError<{ detail?: string }>
      finalizeError.value =
        axiosError.response?.data?.detail || t('sessions.editor.finalize.errorGeneric')

      // Rollback optimistic update on error
      if (session.value) {
        session.value.is_draft = originalIsDraft ?? true
        session.value.finalized_at = originalFinalizedAt ?? null
      }
    } finally {
      isFinalizing.value = false
      isFinalizingInProgress.value = false
    }
  } else {
    // Un-finalize the session (revert to draft)
    // Store original state for rollback
    const originalIsDraft = session.value?.is_draft
    const originalFinalizedAt = session.value?.finalized_at

    isFinalizing.value = true
    finalizeError.value = null

    try {
      // Optimistic update: immediately update UI
      if (session.value) {
        session.value.is_draft = true
        session.value.finalized_at = null
      }

      // Background API call
      await apiClient.post(`/sessions/${props.sessionId}/unfinalize`, {})

      // Silent background sync to ensure we have latest server state
      loadSession(true)
    } catch (error) {
      console.error('Failed to unfinalize session:', error)
      const axiosError = error as AxiosError<{ detail?: string }>
      finalizeError.value =
        axiosError.response?.data?.detail || t('sessions.editor.finalize.errorRevert')

      // Rollback optimistic update on error
      if (session.value) {
        session.value.is_draft = originalIsDraft ?? false
        session.value.finalized_at = originalFinalizedAt ?? null
      }
    } finally {
      isFinalizing.value = false
    }
  }
}

// P2-2: Keyboard shortcut for finalize/unfinalize (Cmd+Enter / Ctrl+Enter)
onKeyStroke(['Meta+Enter', 'Control+Enter'], (e) => {
  // Only trigger if has content and not already processing
  if (hasContent.value && !isFinalizing.value) {
    e.preventDefault()
    toggleFinalizeStatus()
  }
})

// P2-3: Optional Ctrl+S keyboard shortcut for manual save
onKeyStroke(['Meta+s', 'Control+s'], (e) => {
  e.preventDefault()
  flushSync()
})

// Escape key to close bottom sheet
onKeyStroke('Escape', () => {
  if (showPreviousSessionBottomSheet.value) {
    closePreviousSessionBottomSheet()
  }
})

// Tier 3: Immediate sync on browser close/navigation
function handleBeforeUnload(event: BeforeUnloadEvent) {
  if (
    autosaveState.value.type === 'syncing' ||
    autosaveState.value.type === 'offline'
  ) {
    event.preventDefault()
    event.returnValue = 'You have unsaved changes'
    flushSync() // Attempt immediate sync
  }
}

// Restore encrypted backup prompt functions
async function restoreFromBackup() {
  if (!localBackupData.value) return

  // Restore form data (convert null to empty string for form fields)
  formData.value = {
    subjective: localBackupData.value.subjective || '',
    objective: localBackupData.value.objective || '',
    assessment: localBackupData.value.assessment || '',
    plan: localBackupData.value.plan || '',
    session_date: localBackupData.value.session_date || '',
    duration_minutes: localBackupData.value.duration_minutes,
  }

  // Sync to server immediately
  await syncToServer(props.sessionId)

  showRestorePrompt.value = false
  localBackupData.value = null

  // Reload session to get updated server state
  await loadSession(true)
}

function discardBackup() {
  localStorage.removeItem(`session_${props.sessionId}_backup`)
  showRestorePrompt.value = false
  localBackupData.value = null
}

// Lifecycle hooks
onMounted(async () => {
  // Setup beforeunload listener for unsaved changes warning
  window.addEventListener('beforeunload', handleBeforeUnload)

  // Load session and check backup in parallel to avoid sequential loading glitches
  const [, backup] = await Promise.all([loadSession(), restoreDraft(props.sessionId)])

  // After loading session, check for encrypted localStorage backup
  if (backup && backup.draft) {
    // Compare timestamps: only prompt if backup is newer than server
    const backupTime = backup.timestamp || 0
    const serverTime = session.value?.draft_last_saved_at
      ? new Date(session.value.draft_last_saved_at).getTime()
      : 0

    if (backupTime > serverTime) {
      showRestorePrompt.value = true
      localBackupData.value = backup.draft
    } else {
      // Server is newer, discard local backup
      localStorage.removeItem(`session_${props.sessionId}_backup`)
    }
  }
})

onBeforeUnmount(() => {
  // Cleanup beforeunload listener
  window.removeEventListener('beforeunload', handleBeforeUnload)
  // Other cleanup is handled automatically by useInvisibleAutosave
})
</script>

<template>
  <div class="session-editor">
    <!-- Loading State - Skeleton Loader with delayed fade-in -->
    <div v-if="isLoading" class="skeleton-delayed flex flex-col gap-0 lg:flex-row">
      <!-- Main Content Skeleton -->
      <div class="flex-1 animate-pulse space-y-6">
        <!-- Status bar skeleton -->
        <div class="flex items-center justify-between border-b border-slate-200 pb-4">
          <div class="flex items-center gap-3">
            <div class="h-6 w-24 rounded bg-slate-200"></div>
            <div class="h-6 w-32 rounded bg-slate-200"></div>
          </div>
          <div class="h-10 w-36 rounded bg-slate-200"></div>
        </div>

        <!-- Metadata fields skeleton -->
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <div class="mb-2 h-4 w-40 rounded bg-slate-200"></div>
            <div class="h-10 w-full rounded bg-slate-200"></div>
          </div>
          <div>
            <div class="mb-2 h-4 w-36 rounded bg-slate-200"></div>
            <div class="h-10 w-full rounded bg-slate-200"></div>
          </div>
        </div>

        <!-- SOAP fields skeleton -->
        <div v-for="i in 4" :key="i" class="space-y-2">
          <div class="h-4 w-24 rounded bg-slate-200"></div>
          <div class="h-3 w-64 rounded bg-slate-200"></div>
          <div class="h-32 w-full rounded bg-slate-200"></div>
        </div>
      </div>

      <!-- Previous Session Panel Skeleton (Desktop only) -->
      <aside
        class="hidden w-[320px] animate-pulse border-l border-gray-200 bg-gray-50 p-4 lg:block"
      >
        <div
          class="mb-4 flex items-center justify-between border-b border-gray-300 pb-3"
        >
          <div>
            <div class="mb-2 h-4 w-32 rounded bg-gray-300"></div>
            <div class="h-3 w-40 rounded bg-gray-300"></div>
          </div>
          <div class="h-5 w-5 rounded bg-gray-300"></div>
        </div>
        <div class="space-y-4">
          <div v-for="i in 4" :key="i">
            <div class="mb-2 h-3 w-20 rounded bg-gray-300"></div>
            <div class="h-16 rounded bg-gray-300"></div>
          </div>
        </div>
      </aside>
    </div>

    <!-- Error State -->
    <div v-else-if="loadError" class="rounded-lg border border-red-200 bg-red-50 p-4">
      <p class="text-sm font-medium text-red-800">{{ loadError }}</p>
    </div>

    <!-- Session Editor with Previous Session Panel -->
    <div v-else class="flex flex-col gap-0 lg:flex-row">
      <!-- Autosave Banner (only shows for errors/offline) -->
      <AutosaveBanner
        :visible="showBanner"
        :severity="bannerSeverity"
        :message="bannerMessage"
        :description="bannerDescription"
        :actions="bannerActions"
      />

      <!-- Main Content Area -->
      <div class="flex-1 space-y-6 pb-20 lg:pb-0">
        <!-- Tier 1: Previous Session Summary Strip (Mobile Only) -->
        <PreviousSessionSummaryStrip
          v-if="stableClientId"
          :client-id="stableClientId"
          :current-session-id="props.sessionId"
          @expand="openPreviousSessionBottomSheet"
        />

        <!-- SOAP Guide Panel (P1-3: Onboarding for first-time users) -->
        <div
          v-if="showSoapGuide"
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
              <svg
                class="h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
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

        <!-- Status Bar - Reserve min-height to prevent layout shifts -->
        <div
          class="flex min-h-[48px] flex-col gap-3 border-b border-slate-200 pb-4 sm:flex-row sm:items-center sm:justify-between"
        >
          <div class="flex min-h-[32px] flex-wrap items-center gap-3">
            <!-- Session Note Badges Component -->
            <Transition name="badge-fade" mode="out-in">
              <SessionNoteBadges v-if="session" :key="session.id" :session="session" />
            </Transition>

            <!-- View Version History Button (if amended) -->
            <Transition name="badge-fade">
              <button
                v-if="session?.amended_at"
                @click="showVersionHistory = true"
                type="button"
                class="text-sm text-blue-600 hover:text-blue-700 focus:underline focus:outline-none"
              >
                View Original Version
              </button>
            </Transition>
          </div>

          <!-- Finalize/Unfinalize Toggle Button -->
          <button
            type="button"
            :disabled="(!hasContent && !isFinalized) || isFinalizing"
            @click="toggleFinalizeStatus"
            :class="[
              'group inline-flex min-h-[44px] items-center justify-center gap-2 rounded-md px-4 py-2.5 text-sm font-semibold shadow-sm transition-colors focus:ring-2 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-500',
              'w-full sm:w-auto',
              isFinalized
                ? 'bg-slate-600 text-white hover:bg-slate-700 focus:ring-slate-600'
                : 'bg-green-600 text-white hover:bg-green-700 focus:ring-green-600',
            ]"
          >
            <!-- Loading spinner (existing) -->
            <svg
              v-if="isFinalizing"
              class="h-4 w-4 flex-shrink-0 animate-spin"
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
              />
              <path
                class="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>

            <!-- Icon (checkmark for finalize, revert arrow for draft) -->
            <svg
              v-else
              class="h-4 w-4 flex-shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                v-if="!isFinalized"
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M5 13l4 4L19 7"
              />
              <path
                v-else
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"
              />
            </svg>

            <!-- Abbreviated text on mobile -->
            <span class="sm:hidden">
              {{
                isFinalizing
                  ? isFinalized
                    ? 'Reverting...'
                    : 'Finalizing...'
                  : isFinalized
                    ? 'Revert'
                    : 'Finalize'
              }}
            </span>

            <!-- Full text on desktop -->
            <span class="hidden sm:inline">
              {{
                isFinalizing
                  ? isFinalized
                    ? 'Reverting...'
                    : 'Finalizing...'
                  : isFinalized
                    ? 'Revert to Draft'
                    : 'Finalize Session'
              }}
            </span>

            <!-- Keyboard hint (desktop only) -->
            <kbd
              v-if="!isFinalizing"
              :class="[
                'ml-1 hidden rounded px-1.5 py-0.5 font-mono text-xs opacity-0 transition-opacity group-hover:opacity-100 sm:inline-block',
                isFinalized
                  ? 'bg-slate-700 text-slate-100'
                  : 'bg-green-700 text-green-100',
              ]"
            >
              ⌘↵
            </kbd>
          </button>
        </div>

        <!-- Finalize Error -->
        <div
          v-if="finalizeError"
          class="rounded-lg border border-red-200 bg-red-50 p-3"
        >
          <p class="text-sm text-red-800">{{ finalizeError }}</p>
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
              @blur="handleFieldBlur"
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
              @blur="handleFieldBlur"
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
              <label
                for="subjective"
                class="block text-sm font-semibold text-slate-900"
              >
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
              v-rtl
              :maxlength="CHAR_LIMIT"
              @blur="handleFieldBlur"
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
              v-rtl
              :maxlength="CHAR_LIMIT"
              @blur="handleFieldBlur"
              rows="6"
              placeholder="What did you observe during the examination?"
              class="block w-full rounded-md border-slate-300 shadow-sm transition-colors focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            ></textarea>
          </div>

          <!-- Assessment -->
          <div>
            <div class="mb-1 flex items-center justify-between">
              <label
                for="assessment"
                class="block text-sm font-semibold text-slate-900"
              >
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
              v-rtl
              :maxlength="CHAR_LIMIT"
              @blur="handleFieldBlur"
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
              v-rtl
              :maxlength="CHAR_LIMIT"
              @blur="handleFieldBlur"
              rows="6"
              placeholder="What is the treatment plan going forward?"
              class="block w-full rounded-md border-slate-300 shadow-sm transition-colors focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
            ></textarea>
          </div>
        </div>

        <!-- Attachments Section (only for existing sessions) -->
        <div v-if="session && !session.deleted_at" class="mt-8">
          <h3 class="mb-4 text-lg font-semibold text-slate-900">Attachments</h3>
          <SessionAttachments :session-id="props.sessionId" />
        </div>
      </div>

      <!-- Previous Session Context Panel -->
      <PreviousSessionPanel
        v-if="stableClientId"
        :client-id="stableClientId"
        :current-session-id="props.sessionId"
      />
    </div>

    <!-- Session Version History Modal -->
    <SessionVersionHistory
      v-if="session"
      :session-id="props.sessionId"
      :session="session as SessionWithAmendments"
      :open="showVersionHistory"
      @close="showVersionHistory = false"
    />

    <!-- Restore Unsaved Changes Prompt (Encrypted localStorage backup) -->
    <Teleport to="body">
      <div
        v-if="showRestorePrompt"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
        @click.self="discardBackup"
      >
        <div class="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
          <div class="mb-4 flex items-start gap-3">
            <IconWarning size="lg" class="mt-0.5 flex-shrink-0 text-blue-600" />
            <div>
              <h3 class="text-lg font-semibold text-slate-900">
                Restore Unsaved Changes?
              </h3>
              <p class="mt-2 text-sm text-slate-600">
                You have unsaved changes from a previous session that were saved
                locally. Would you like to restore them?
              </p>
            </div>
          </div>
          <div class="mt-6 flex justify-end gap-3">
            <button
              @click="discardBackup"
              type="button"
              class="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 focus:outline-none"
            >
              Discard
            </button>
            <button
              @click="restoreFromBackup"
              type="button"
              class="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 focus:ring-2 focus:ring-blue-600 focus:ring-offset-2 focus:outline-none"
            >
              Restore Changes
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Tier 2: Previous Session Bottom Sheet (Mobile) -->
    <Teleport to="body">
      <Transition name="bottom-sheet">
        <div
          v-if="showPreviousSessionBottomSheet"
          class="fixed inset-0 z-50 lg:hidden"
          @click.self="closePreviousSessionBottomSheet"
        >
          <!-- Backdrop -->
          <div class="absolute inset-0 bg-black/20 transition-opacity"></div>

          <!-- Bottom Sheet -->
          <div
            class="absolute right-0 bottom-0 left-0 flex max-h-[90vh] flex-col rounded-t-2xl bg-white shadow-2xl"
            style="height: 60vh"
            role="dialog"
            aria-modal="true"
            aria-labelledby="bottom-sheet-title"
          >
            <!-- Drag Handle -->
            <div class="flex shrink-0 justify-center py-2">
              <div class="h-1 w-12 rounded-full bg-gray-300" aria-hidden="true"></div>
            </div>

            <!-- Header -->
            <div
              class="flex shrink-0 items-center justify-between border-b border-gray-200 px-4 pb-3"
            >
              <h2 id="bottom-sheet-title" class="text-lg font-semibold text-gray-900">
                Treatment Context
              </h2>
              <button
                @click="closePreviousSessionBottomSheet"
                class="rounded p-2 text-gray-600 hover:bg-gray-100 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                aria-label="Close treatment context"
              >
                <svg
                  class="h-5 w-5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    stroke-width="2"
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            <!-- Content - Scrollable -->
            <div class="flex-1 overflow-y-auto px-4 pt-4 pb-8">
              <PreviousSessionPanel
                v-if="stableClientId"
                :client-id="stableClientId"
                :current-session-id="props.sessionId"
                :force-mobile-view="true"
              />
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
/* Delayed skeleton loader - only shows after 150ms to prevent flash on fast loads */
.skeleton-delayed {
  animation: delayedFadeIn 0.2s ease-in;
}

@keyframes delayedFadeIn {
  0%,
  75% {
    opacity: 0;
  }
  100% {
    opacity: 1;
  }
}

/* Smooth transitions for all interactive elements */
.session-editor textarea,
.session-editor input {
  transition:
    border-color 0.15s ease-in-out,
    box-shadow 0.15s ease-in-out;
}

/* Prevent layout shift when badges appear/disappear */
.session-editor .flex.items-center.gap-3 {
  min-height: 2rem;
  min-width: fit-content;
}

/* Badge transition animations - smooth fade and scale */
.badge-fade-enter-active {
  transition:
    opacity 0.2s ease-out,
    transform 0.2s ease-out;
}

.badge-fade-leave-active {
  transition:
    opacity 0.15s ease-in,
    transform 0.15s ease-in;
}

.badge-fade-enter-from {
  opacity: 0;
  transform: scale(0.96) translateY(-2px);
}

.badge-fade-leave-to {
  opacity: 0;
  transform: scale(0.96) translateY(-2px);
}

/* Smooth badge transitions */
.session-editor span[class*='rounded-full'] {
  transition:
    background-color 0.2s ease-in-out,
    color 0.2s ease-in-out;
  will-change: background-color, color;
}

/* Smooth button state transitions */
.session-editor button {
  transition:
    background-color 0.2s ease-in-out,
    color 0.2s ease-in-out,
    opacity 0.2s ease-in-out,
    transform 0.1s ease-in-out;
  will-change: background-color, color, opacity;
}

/* Prevent button layout shift during state changes */
.session-editor button[type='button'] {
  min-width: fit-content;
}

/* Bottom Sheet Transitions */
.bottom-sheet-enter-active {
  transition: opacity 0.3s ease-out;
}

.bottom-sheet-leave-active {
  transition: opacity 0.25s ease-in;
}

.bottom-sheet-enter-active .absolute:last-child,
.bottom-sheet-leave-active .absolute:last-child {
  transition: transform 0.3s cubic-bezier(0.32, 0.72, 0, 1);
}

.bottom-sheet-enter-from {
  opacity: 0;
}

.bottom-sheet-enter-from .absolute:last-child {
  transform: translateY(100%);
}

.bottom-sheet-leave-to {
  opacity: 0;
}

.bottom-sheet-leave-to .absolute:last-child {
  transform: translateY(100%);
}

/* Reduced motion support */
@media (prefers-reduced-motion: reduce) {
  .bottom-sheet-enter-active,
  .bottom-sheet-leave-active {
    transition: opacity 0.2s;
  }

  .bottom-sheet-enter-active .absolute:last-child,
  .bottom-sheet-leave-active .absolute:last-child {
    transition: none;
  }
}
</style>
