<script setup lang="ts">
/**
 * PreviousSessionPanel Component
 *
 * Displays the previous finalized session's SOAP fields to provide context
 * when creating or editing a new session note.
 *
 * Features:
 * - Desktop: Right sidebar (400px, sticky, collapsible)
 * - Mobile: Bottom drawer (collapsed by default, max-h-96)
 * - Shows all 4 SOAP fields with labels
 * - Link to open full session in new tab
 * - Loading state with skeleton placeholders
 * - Error state for API failures
 * - Auto-hides if no previous sessions (404)
 * - Collapse state persists in localStorage
 *
 * Usage:
 *   <PreviousSessionPanel :client-id="clientId" />
 */

import { computed, ref, watch } from 'vue'
import { useLocalStorage } from '@vueuse/core'
import { useI18n } from '@/composables/useI18n'
import { usePreviousSession } from '@/composables/usePreviousSession'
import { useClipboard } from '@/composables/useClipboard'
import { formatLongDate, formatRelativeDate } from '@/utils/calendar/dateFormatters'
import IconCopy from '@/components/icons/IconCopy.vue'
import IconCheck from '@/components/icons/IconCheck.vue'
import PreviousSessionSummary from './PreviousSessionSummary.vue'
import PreviousSessionHistory from './PreviousSessionHistory.vue'
import apiClient from '@/api/client'
import type { SessionResponse } from '@/types/sessions'

const { t } = useI18n()

interface Props {
  clientId: string
  currentSessionId?: string // Optional: ID of current session being edited (to exclude from results)
  forceMobileView?: boolean // Optional: Force mobile content layout (for modal)
}

const props = withDefaults(defineProps<Props>(), {
  forceMobileView: false,
})

// Composable - start in loading state to prevent initial glitch
const { loading, session, error, notFound, fetchLatestFinalized } =
  usePreviousSession(true)

// Collapse state (persisted in localStorage)
const collapsed = useLocalStorage('previousSessionPanel.collapsed', false)

// Clipboard functionality
const { copy } = useClipboard()
const copiedField = ref<string | null>(null)

async function copyField(fieldName: string, content: string) {
  const success = await copy(content)
  if (success) {
    copiedField.value = fieldName
    // Reset after 2 seconds
    setTimeout(() => {
      copiedField.value = null
    }, 2000)
  }
}

// View mode state (Phase 3: summary, detail, history)
type ViewMode = 'summary' | 'detail' | 'history'
const viewMode = ref<ViewMode>('summary')

// For history view: track selected historical session
const selectedHistoricalSession = ref<SessionResponse | null>(null)
const loadingHistoricalSession = ref(false)

// Navigation functions
function showSummary() {
  viewMode.value = 'summary'
  selectedHistoricalSession.value = null
}

function showDetail() {
  viewMode.value = 'detail'
}

function showHistory() {
  viewMode.value = 'history'
}

// Load historical session from history view
async function loadHistoricalSession(sessionId: string) {
  try {
    loadingHistoricalSession.value = true
    const response = await apiClient.get<SessionResponse>(`/sessions/${sessionId}`)
    selectedHistoricalSession.value = response.data
    showDetail() // Switch to detail view with historical session
  } catch (err) {
    console.error('Failed to load historical session:', err)
    // TODO: Show error toast notification
  } finally {
    loadingHistoricalSession.value = false
  }
}

// Get the session to display (historical or most recent)
const displaySession = computed(() => {
  return selectedHistoricalSession.value || session.value
})

// Start loading immediately when component is created (not onMounted)
// This prevents layout shift by ensuring loading state is active from the start
if (props.clientId) {
  fetchLatestFinalized(props.clientId)
}

// Computed
const shouldShow = computed(() => {
  // Hide if the returned session is the same as current session (happens for first session)
  if (
    session.value &&
    props.currentSessionId &&
    session.value.id === props.currentSessionId
  ) {
    return false
  }

  // Show if loading, has session, has error, or no previous sessions (for empty state)
  return (
    loading.value || session.value !== null || error.value !== null || notFound.value
  )
})

// Removed unused computed properties: sessionDate, relativeDate, sessionLink
// These are now computed inline in the template or replaced by displaySession

// Methods
function toggleCollapse() {
  collapsed.value = !collapsed.value
}

// Watch for clientId changes (if component is reused)
watch(
  () => props.clientId,
  (newClientId) => {
    if (newClientId) {
      fetchLatestFinalized(newClientId)
      // Reset to summary view when client changes
      viewMode.value = 'summary'
      selectedHistoricalSession.value = null
    }
  }
)

// Watch for currentSessionId changes (reset to summary)
watch(
  () => props.currentSessionId,
  () => {
    viewMode.value = 'summary'
    selectedHistoricalSession.value = null
  }
)
</script>

<template>
  <!-- Desktop Sidebar (only shown when not in modal mode) -->
  <aside
    v-if="!forceMobileView && shouldShow"
    class="sticky top-0 hidden h-screen w-[360px] flex-shrink-0 overflow-y-auto border-l border-gray-200 bg-gray-50 lg:block"
  >
    <div class="h-full p-4">
      <!-- Panel Header -->
      <div class="mb-4 flex items-center justify-between border-b border-gray-300 pb-3">
        <div>
          <h3 class="text-sm font-semibold text-gray-900">
            {{ t('sessions.previousPanel.title') }}
          </h3>
          <span
            v-if="displaySession && viewMode !== 'history'"
            class="text-xs text-gray-600"
          >
            {{ formatLongDate(displaySession.session_date) }} ({{
              formatRelativeDate(displaySession.session_date)
            }})
          </span>
        </div>
        <button
          v-if="viewMode !== 'history'"
          @click="toggleCollapse"
          class="rounded p-1 text-gray-500 hover:text-gray-700 focus:ring-2 focus:ring-blue-500 focus:outline-none"
          aria-label="Toggle treatment context panel"
        >
          <!-- When expanded: show down chevron (collapse) -->
          <svg
            v-if="!collapsed"
            class="h-5 w-5"
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
          <!-- When collapsed: show up chevron (expand) -->
          <svg
            v-else
            class="h-5 w-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M5 15l7-7 7 7"
            />
          </svg>
        </button>
      </div>

      <!-- Loading State -->
      <div v-if="loading" class="space-y-4">
        <div class="animate-pulse">
          <div class="mb-2 h-4 w-1/4 rounded bg-gray-300"></div>
          <div class="h-16 rounded bg-gray-300"></div>
        </div>
        <div class="animate-pulse">
          <div class="mb-2 h-4 w-1/4 rounded bg-gray-300"></div>
          <div class="h-16 rounded bg-gray-300"></div>
        </div>
        <div class="animate-pulse">
          <div class="mb-2 h-4 w-1/4 rounded bg-gray-300"></div>
          <div class="h-16 rounded bg-gray-300"></div>
        </div>
        <div class="animate-pulse">
          <div class="mb-2 h-4 w-1/4 rounded bg-gray-300"></div>
          <div class="h-16 rounded bg-gray-300"></div>
        </div>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="rounded-lg border border-red-200 bg-red-50 p-3">
        <p class="text-sm text-red-800">{{ error }}</p>
      </div>

      <!-- Empty State (no previous sessions) -->
      <div
        v-else-if="notFound && !collapsed"
        class="flex flex-col items-center justify-center px-4 py-8 text-center"
      >
        <svg
          class="mb-4 h-16 w-16 text-gray-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="1.5"
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
        <h4 class="text-sm font-semibold text-gray-900">
          {{ t('sessions.previousPanel.noSessionsTitle') }}
        </h4>
      </div>

      <!-- Collapsed State Message -->
      <div v-else-if="collapsed" class="text-center text-sm text-gray-600">
        <p>{{ t('sessions.previousPanel.collapsedMessage') }}</p>
      </div>

      <!-- View Mode: Summary (default) -->
      <div
        v-else-if="viewMode === 'summary' && session && !collapsed"
        class="space-y-4"
      >
        <PreviousSessionSummary :session="session" @view-full="showDetail" />

        <!-- View History Button -->
        <button
          @click="showHistory"
          class="w-full rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:outline-none"
          type="button"
        >
          View All Sessions
        </button>
      </div>

      <!-- View Mode: Detail -->
      <div
        v-else-if="viewMode === 'detail' && displaySession && !collapsed"
        class="space-y-4"
      >
        <!-- Back to Summary -->
        <button
          @click="showSummary"
          class="mb-2 flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900 focus:underline focus:outline-none"
          type="button"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M15 19l-7-7 7-7"
            />
          </svg>
          Back to Summary
        </button>

        <!-- Session Metadata -->
        <div class="rounded-lg border border-gray-200 bg-white p-3">
          <div class="flex items-start justify-between">
            <div>
              <h4 class="text-sm font-semibold text-gray-900">
                {{ formatLongDate(displaySession.session_date) }}
              </h4>
              <p class="text-xs text-gray-600">
                {{ formatRelativeDate(displaySession.session_date) }}
              </p>
            </div>
            <span
              :class="[
                'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
                displaySession.is_draft
                  ? 'bg-blue-100 text-blue-800'
                  : 'bg-green-100 text-green-800',
              ]"
            >
              {{ displaySession.is_draft ? 'Draft' : 'Finalized' }}
            </span>
          </div>
        </div>

        <!-- SOAP Fields (Standard Clinical Order: Subjective → Objective → Assessment → Plan) -->
        <!-- Subjective -->
        <div class="soap-field group">
          <div class="mb-1.5 flex items-center justify-between">
            <label
              class="block text-xs font-semibold tracking-wide text-gray-700 uppercase"
            >
              S: Subjective
            </label>
            <button
              v-if="displaySession.subjective"
              @click="copyField('subjective', displaySession.subjective)"
              class="rounded p-1 text-gray-500 opacity-0 transition-opacity duration-150 group-hover:opacity-100 hover:text-gray-700 focus:opacity-100 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              :title="
                copiedField === 'subjective'
                  ? t('sessions.previousPanel.copiedTooltip')
                  : t('sessions.previousPanel.copyTooltip')
              "
              type="button"
            >
              <IconCheck
                v-if="copiedField === 'subjective'"
                class="h-4 w-4 text-green-600"
              />
              <IconCopy v-else class="h-4 w-4" />
            </button>
          </div>
          <p
            v-if="displaySession.subjective"
            class="max-h-32 overflow-y-auto text-sm leading-relaxed whitespace-pre-wrap text-gray-800"
          >
            {{ displaySession.subjective }}
          </p>
          <p v-else class="text-sm text-gray-500 italic">
            {{ t('sessions.previousPanel.noFieldNotes.subjective') }}
          </p>
        </div>

        <!-- Objective -->
        <div class="soap-field group">
          <div class="mb-1.5 flex items-center justify-between">
            <label
              class="block text-xs font-semibold tracking-wide text-gray-700 uppercase"
            >
              O: Objective
            </label>
            <button
              v-if="displaySession.objective"
              @click="copyField('objective', displaySession.objective)"
              class="rounded p-1 text-gray-500 opacity-0 transition-opacity duration-150 group-hover:opacity-100 hover:text-gray-700 focus:opacity-100 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              :title="
                copiedField === 'objective'
                  ? t('sessions.previousPanel.copiedTooltip')
                  : t('sessions.previousPanel.copyTooltip')
              "
              type="button"
            >
              <IconCheck
                v-if="copiedField === 'objective'"
                class="h-4 w-4 text-green-600"
              />
              <IconCopy v-else class="h-4 w-4" />
            </button>
          </div>
          <p
            v-if="displaySession.objective"
            class="max-h-32 overflow-y-auto text-sm leading-relaxed whitespace-pre-wrap text-gray-800"
          >
            {{ displaySession.objective }}
          </p>
          <p v-else class="text-sm text-gray-500 italic">
            {{ t('sessions.previousPanel.noFieldNotes.objective') }}
          </p>
        </div>

        <!-- Assessment -->
        <div class="soap-field group">
          <div class="mb-1.5 flex items-center justify-between">
            <label
              class="block text-xs font-semibold tracking-wide text-gray-700 uppercase"
            >
              A: Assessment
            </label>
            <button
              v-if="displaySession.assessment"
              @click="copyField('assessment', displaySession.assessment)"
              class="rounded p-1 text-gray-500 opacity-0 transition-opacity duration-150 group-hover:opacity-100 hover:text-gray-700 focus:opacity-100 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              :title="
                copiedField === 'assessment'
                  ? t('sessions.previousPanel.copiedTooltip')
                  : t('sessions.previousPanel.copyTooltip')
              "
              type="button"
            >
              <IconCheck
                v-if="copiedField === 'assessment'"
                class="h-4 w-4 text-green-600"
              />
              <IconCopy v-else class="h-4 w-4" />
            </button>
          </div>
          <p
            v-if="displaySession.assessment"
            class="max-h-32 overflow-y-auto text-sm leading-relaxed whitespace-pre-wrap text-gray-800"
          >
            {{ displaySession.assessment }}
          </p>
          <p v-else class="text-sm text-gray-500 italic">
            {{ t('sessions.previousPanel.noFieldNotes.assessment') }}
          </p>
        </div>

        <!-- Plan -->
        <div class="soap-field group">
          <div class="mb-1.5 flex items-center justify-between">
            <label
              class="block text-xs font-semibold tracking-wide text-gray-700 uppercase"
            >
              P: Plan
            </label>
            <button
              v-if="displaySession.plan"
              @click="copyField('plan', displaySession.plan)"
              class="rounded p-1 text-gray-500 opacity-0 transition-opacity duration-150 group-hover:opacity-100 hover:text-gray-700 focus:opacity-100 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              :title="
                copiedField === 'plan'
                  ? t('sessions.previousPanel.copiedTooltip')
                  : t('sessions.previousPanel.copyTooltip')
              "
              type="button"
            >
              <IconCheck v-if="copiedField === 'plan'" class="h-4 w-4 text-green-600" />
              <IconCopy v-else class="h-4 w-4" />
            </button>
          </div>
          <p
            v-if="displaySession.plan"
            class="max-h-32 overflow-y-auto text-sm leading-relaxed whitespace-pre-wrap text-gray-800"
          >
            {{ displaySession.plan }}
          </p>
          <p v-else class="text-sm text-gray-500 italic">
            {{ t('sessions.previousPanel.noFieldNotes.plan') }}
          </p>
        </div>

        <!-- Link to Full Session -->
        <div class="border-t border-gray-300 pt-2">
          <a
            :href="`/sessions/${displaySession.id}`"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center text-sm text-blue-600 hover:text-blue-700 focus:underline focus:outline-none"
          >
            Open full session
            <svg
              class="ml-1 h-4 w-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
              />
            </svg>
          </a>
        </div>

        <!-- View History Button -->
        <button
          @click="showHistory"
          class="w-full rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:outline-none"
          type="button"
        >
          View All Sessions
        </button>
      </div>

      <!-- View Mode: History -->
      <div v-else-if="viewMode === 'history' && !collapsed" class="h-full">
        <PreviousSessionHistory
          :client-id="clientId"
          :current-session-id="currentSessionId || ''"
          @select-session="loadHistoricalSession"
          @back="showSummary"
        />
      </div>
    </div>
  </aside>

  <!-- Mobile Modal Content (no wrappers, just content for modal) -->
  <div v-if="forceMobileView" class="space-y-4">
    <!-- Session Date (only show in summary/detail views, not history) -->
    <div
      v-if="displaySession && viewMode !== 'history'"
      class="border-b border-gray-300 pb-3"
    >
      <span class="text-sm text-gray-900">{{
        formatLongDate(displaySession.session_date)
      }}</span>
      <span class="ml-1 text-xs text-gray-600"
        >({{ formatRelativeDate(displaySession.session_date) }})</span
      >
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="space-y-4">
      <div class="animate-pulse">
        <div class="mb-2 h-4 w-1/4 rounded bg-gray-300"></div>
        <div class="h-16 rounded bg-gray-300"></div>
      </div>
      <div class="animate-pulse">
        <div class="mb-2 h-4 w-1/4 rounded bg-gray-300"></div>
        <div class="h-16 rounded bg-gray-300"></div>
      </div>
      <div class="animate-pulse">
        <div class="mb-2 h-4 w-1/4 rounded bg-gray-300"></div>
        <div class="h-16 rounded bg-gray-300"></div>
      </div>
      <div class="animate-pulse">
        <div class="mb-2 h-4 w-1/4 rounded bg-gray-300"></div>
        <div class="h-16 rounded bg-gray-300"></div>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="rounded-lg border border-red-200 bg-red-50 p-3">
      <p class="text-sm text-red-800">{{ error }}</p>
    </div>

    <!-- Empty State -->
    <div
      v-else-if="notFound"
      class="flex flex-col items-center justify-center py-8 text-center"
    >
      <svg
        class="mb-4 h-16 w-16 text-gray-400"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="1.5"
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>
      <h4 class="text-sm font-semibold text-gray-900">
        {{ t('sessions.previousPanel.noSessionsTitle') }}
      </h4>
    </div>

    <!-- View Mode: Summary (default) -->
    <div v-else-if="viewMode === 'summary' && session" class="space-y-4">
      <PreviousSessionSummary :session="session" @view-full="showDetail" />

      <!-- View History Button -->
      <button
        @click="showHistory"
        class="w-full rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:outline-none"
        type="button"
      >
        View All Sessions
      </button>
    </div>

    <!-- View Mode: Detail -->
    <div v-else-if="viewMode === 'detail' && displaySession" class="space-y-4">
      <!-- Back to Summary -->
      <button
        @click="showSummary"
        class="mb-2 flex items-center gap-1 text-sm text-gray-600 hover:text-gray-900 focus:underline focus:outline-none"
        type="button"
      >
        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M15 19l-7-7 7-7"
          />
        </svg>
        Back to Summary
      </button>

      <!-- SOAP Fields (Standard Clinical Order: Subjective → Objective → Assessment → Plan) -->
      <!-- Subjective -->
      <div class="soap-field group">
        <div class="mb-1.5 flex items-center justify-between">
          <label
            class="block text-xs font-semibold tracking-wide text-gray-700 uppercase"
          >
            S: Subjective
          </label>
          <button
            v-if="displaySession.subjective"
            @click="copyField('subjective', displaySession.subjective)"
            class="rounded p-1 text-gray-500 opacity-100 transition-opacity duration-150 hover:text-gray-700 focus:opacity-100 focus:ring-2 focus:ring-blue-500 focus:outline-none md:opacity-0 md:group-hover:opacity-100"
            :title="copiedField === 'subjective' ? 'Copied!' : 'Copy to clipboard'"
            type="button"
          >
            <IconCheck
              v-if="copiedField === 'subjective'"
              class="h-4 w-4 text-green-600"
            />
            <IconCopy v-else class="h-4 w-4" />
          </button>
        </div>
        <p
          v-if="displaySession.subjective"
          class="text-sm leading-relaxed whitespace-pre-wrap text-gray-800"
        >
          {{ displaySession.subjective }}
        </p>
        <p v-else class="text-sm text-gray-500 italic">No subjective notes</p>
      </div>

      <!-- Objective -->
      <div class="soap-field group">
        <div class="mb-1.5 flex items-center justify-between">
          <label
            class="block text-xs font-semibold tracking-wide text-gray-700 uppercase"
          >
            O: Objective
          </label>
          <button
            v-if="displaySession.objective"
            @click="copyField('objective', displaySession.objective)"
            class="rounded p-1 text-gray-500 opacity-100 transition-opacity duration-150 hover:text-gray-700 focus:opacity-100 focus:ring-2 focus:ring-blue-500 focus:outline-none md:opacity-0 md:group-hover:opacity-100"
            :title="copiedField === 'objective' ? 'Copied!' : 'Copy to clipboard'"
            type="button"
          >
            <IconCheck
              v-if="copiedField === 'objective'"
              class="h-4 w-4 text-green-600"
            />
            <IconCopy v-else class="h-4 w-4" />
          </button>
        </div>
        <p
          v-if="displaySession.objective"
          class="text-sm leading-relaxed whitespace-pre-wrap text-gray-800"
        >
          {{ displaySession.objective }}
        </p>
        <p v-else class="text-sm text-gray-500 italic">No objective notes</p>
      </div>

      <!-- Assessment -->
      <div class="soap-field group">
        <div class="mb-1.5 flex items-center justify-between">
          <label
            class="block text-xs font-semibold tracking-wide text-gray-700 uppercase"
          >
            A: Assessment
          </label>
          <button
            v-if="displaySession.assessment"
            @click="copyField('assessment', displaySession.assessment)"
            class="rounded p-1 text-gray-500 opacity-100 transition-opacity duration-150 hover:text-gray-700 focus:opacity-100 focus:ring-2 focus:ring-blue-500 focus:outline-none md:opacity-0 md:group-hover:opacity-100"
            :title="copiedField === 'assessment' ? 'Copied!' : 'Copy to clipboard'"
            type="button"
          >
            <IconCheck
              v-if="copiedField === 'assessment'"
              class="h-4 w-4 text-green-600"
            />
            <IconCopy v-else class="h-4 w-4" />
          </button>
        </div>
        <p
          v-if="displaySession.assessment"
          class="text-sm leading-relaxed whitespace-pre-wrap text-gray-800"
        >
          {{ displaySession.assessment }}
        </p>
        <p v-else class="text-sm text-gray-500 italic">No assessment notes</p>
      </div>

      <!-- Plan -->
      <div class="soap-field group">
        <div class="mb-1.5 flex items-center justify-between">
          <label
            class="block text-xs font-semibold tracking-wide text-gray-700 uppercase"
          >
            P: Plan
          </label>
          <button
            v-if="displaySession.plan"
            @click="copyField('plan', displaySession.plan)"
            class="rounded p-1 text-gray-500 opacity-100 transition-opacity duration-150 hover:text-gray-700 focus:opacity-100 focus:ring-2 focus:ring-blue-500 focus:outline-none md:opacity-0 md:group-hover:opacity-100"
            :title="copiedField === 'plan' ? 'Copied!' : 'Copy to clipboard'"
            type="button"
          >
            <IconCheck v-if="copiedField === 'plan'" class="h-4 w-4 text-green-600" />
            <IconCopy v-else class="h-4 w-4" />
          </button>
        </div>
        <p
          v-if="displaySession.plan"
          class="text-sm leading-relaxed whitespace-pre-wrap text-gray-800"
        >
          {{ displaySession.plan }}
        </p>
        <p v-else class="text-sm text-gray-500 italic">No plan notes</p>
      </div>

      <!-- Link to Full Session -->
      <div class="border-t border-gray-300 pt-2">
        <a
          :href="`/sessions/${displaySession.id}`"
          target="_blank"
          rel="noopener noreferrer"
          class="inline-flex items-center text-sm text-blue-600 hover:text-blue-700 focus:underline focus:outline-none"
        >
          Open full session
          <svg
            class="ml-1 h-4 w-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
            />
          </svg>
        </a>
      </div>

      <!-- View History Button -->
      <button
        @click="showHistory"
        class="w-full rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:outline-none"
        type="button"
      >
        View All Sessions
      </button>
    </div>

    <!-- View Mode: History -->
    <div v-else-if="viewMode === 'history'" class="h-full">
      <PreviousSessionHistory
        :client-id="clientId"
        :current-session-id="currentSessionId || ''"
        @select-session="loadHistoricalSession"
        @back="showSummary"
      />
    </div>
  </div>
</template>

<style scoped>
/* Smooth transitions for drawer */
.transition-all {
  transition-property: all;
  transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
  transition-duration: 300ms;
}
</style>
