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

import { computed, watch } from 'vue'
import { useLocalStorage } from '@vueuse/core'
import { usePreviousSession } from '@/composables/usePreviousSession'
import { formatLongDate, formatRelativeDate } from '@/utils/calendar/dateFormatters'

interface Props {
  clientId: string
  currentSessionId?: string // Optional: ID of current session being edited (to exclude from results)
  forceMobileView?: boolean // Optional: Force mobile content layout (for modal)
}

const props = withDefaults(defineProps<Props>(), {
  forceMobileView: false
})

// Composable - start in loading state to prevent initial glitch
const { loading, session, error, notFound, fetchLatestFinalized } = usePreviousSession(true)

// Collapse state (persisted in localStorage)
const collapsed = useLocalStorage('previousSessionPanel.collapsed', true)

// Start loading immediately when component is created (not onMounted)
// This prevents layout shift by ensuring loading state is active from the start
if (props.clientId) {
  fetchLatestFinalized(props.clientId)
}

// Computed
const shouldShow = computed(() => {
  // Hide if the returned session is the same as current session (happens for first session)
  if (session.value && props.currentSessionId && session.value.id === props.currentSessionId) {
    return false
  }

  // Show if loading, has session, has error, or no previous sessions (for empty state)
  return loading.value || session.value !== null || error.value !== null || notFound.value
})

const sessionDate = computed(() => {
  if (!session.value?.session_date) return ''
  return formatLongDate(session.value.session_date)
})

const relativeDate = computed(() => {
  if (!session.value?.session_date) return ''
  return formatRelativeDate(session.value.session_date)
})

const sessionLink = computed(() => {
  if (!session.value?.id) return ''
  return `/sessions/${session.value.id}`
})

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
    }
  }
)
</script>

<template>
  <!-- Desktop Sidebar (only shown when not in modal mode) -->
  <aside
    v-if="!forceMobileView && shouldShow"
    class="hidden lg:block w-[320px] bg-gray-50 border-l border-gray-200 overflow-y-auto sticky top-0 h-screen flex-shrink-0"
  >
    <div class="p-4">
      <!-- Panel Header -->
      <div class="flex items-center justify-between mb-4 pb-3 border-b border-gray-300">
        <div>
          <h3 class="text-sm font-semibold text-gray-900">Previous Session</h3>
          <span v-if="session" class="text-xs text-gray-600">
            {{ sessionDate }} ({{ relativeDate }})
          </span>
        </div>
        <button
          @click="toggleCollapse"
          class="text-gray-500 hover:text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-500 rounded p-1"
          aria-label="Toggle previous session panel"
        >
          <!-- When expanded: show down chevron (collapse) -->
          <svg
            v-if="!collapsed"
            class="w-5 h-5"
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
          <svg v-else class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
          <div class="h-4 bg-gray-300 rounded w-1/4 mb-2"></div>
          <div class="h-16 bg-gray-300 rounded"></div>
        </div>
        <div class="animate-pulse">
          <div class="h-4 bg-gray-300 rounded w-1/4 mb-2"></div>
          <div class="h-16 bg-gray-300 rounded"></div>
        </div>
        <div class="animate-pulse">
          <div class="h-4 bg-gray-300 rounded w-1/4 mb-2"></div>
          <div class="h-16 bg-gray-300 rounded"></div>
        </div>
        <div class="animate-pulse">
          <div class="h-4 bg-gray-300 rounded w-1/4 mb-2"></div>
          <div class="h-16 bg-gray-300 rounded"></div>
        </div>
      </div>

      <!-- Error State -->
      <div v-else-if="error" class="rounded-lg border border-red-200 bg-red-50 p-3">
        <p class="text-sm text-red-800">{{ error }}</p>
      </div>

      <!-- Empty State (no previous sessions) -->
      <div v-else-if="notFound && !collapsed" class="flex flex-col items-center justify-center py-8 px-4 text-center">
        <svg class="w-16 h-16 text-gray-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
        <h4 class="text-sm font-semibold text-gray-900 mb-2">No Previous Sessions Yet</h4>
        <p class="text-xs text-gray-600 max-w-xs">
          Previous SOAP notes will appear here to help with treatment continuity.
        </p>
      </div>

      <!-- SOAP Fields (Reordered: Plan → Assessment → Subjective → Objective) -->
      <div v-else-if="session && !collapsed" class="space-y-4">
        <!-- Plan (Most important for treatment continuity) -->
        <div class="soap-field">
          <label class="block text-xs font-semibold text-gray-700 mb-1.5">P: Plan</label>
          <p
            v-if="session.plan"
            class="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap max-h-32 overflow-y-auto"
          >
            {{ session.plan }}
          </p>
          <p v-else class="text-sm text-gray-500 italic">No plan notes</p>
        </div>

        <!-- Assessment -->
        <div class="soap-field">
          <label class="block text-xs font-semibold text-gray-700 mb-1.5">
            A: Assessment
          </label>
          <p
            v-if="session.assessment"
            class="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap max-h-32 overflow-y-auto"
          >
            {{ session.assessment }}
          </p>
          <p v-else class="text-sm text-gray-500 italic">No assessment notes</p>
        </div>

        <!-- Subjective -->
        <div class="soap-field">
          <label class="block text-xs font-semibold text-gray-700 mb-1.5">
            S: Subjective
          </label>
          <p
            v-if="session.subjective"
            class="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap max-h-32 overflow-y-auto"
          >
            {{ session.subjective }}
          </p>
          <p v-else class="text-sm text-gray-500 italic">No subjective notes</p>
        </div>

        <!-- Objective -->
        <div class="soap-field">
          <label class="block text-xs font-semibold text-gray-700 mb-1.5">
            O: Objective
          </label>
          <p
            v-if="session.objective"
            class="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap max-h-32 overflow-y-auto"
          >
            {{ session.objective }}
          </p>
          <p v-else class="text-sm text-gray-500 italic">No objective notes</p>
        </div>

        <!-- Link to Full Session -->
        <div class="pt-2 border-t border-gray-300">
          <a
            :href="sessionLink"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center text-sm text-blue-600 hover:text-blue-700 focus:underline focus:outline-none"
          >
            Open full session
            <svg class="ml-1 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
              />
            </svg>
          </a>
        </div>
      </div>

      <!-- Collapsed State Message -->
      <div v-else-if="session && collapsed" class="text-sm text-gray-600">
        <p>Previous session hidden. Click to expand.</p>
      </div>
    </div>
  </aside>

  <!-- Mobile Modal Content (no wrappers, just content for modal) -->
  <div v-if="forceMobileView" class="space-y-4">
    <!-- Session Date -->
    <div v-if="session" class="pb-3 border-b border-gray-300">
      <span class="text-sm text-gray-900">{{ sessionDate }}</span>
      <span class="text-xs text-gray-600 ml-1">({{ relativeDate }})</span>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="space-y-4">
      <div class="animate-pulse">
        <div class="h-4 bg-gray-300 rounded w-1/4 mb-2"></div>
        <div class="h-16 bg-gray-300 rounded"></div>
      </div>
      <div class="animate-pulse">
        <div class="h-4 bg-gray-300 rounded w-1/4 mb-2"></div>
        <div class="h-16 bg-gray-300 rounded"></div>
      </div>
      <div class="animate-pulse">
        <div class="h-4 bg-gray-300 rounded w-1/4 mb-2"></div>
        <div class="h-16 bg-gray-300 rounded"></div>
      </div>
      <div class="animate-pulse">
        <div class="h-4 bg-gray-300 rounded w-1/4 mb-2"></div>
        <div class="h-16 bg-gray-300 rounded"></div>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="rounded-lg border border-red-200 bg-red-50 p-3">
      <p class="text-sm text-red-800">{{ error }}</p>
    </div>

    <!-- Empty State -->
    <div v-else-if="notFound" class="flex flex-col items-center justify-center py-8 text-center">
      <svg class="w-16 h-16 text-gray-400 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>
      <h4 class="text-sm font-semibold text-gray-900 mb-2">No Previous Sessions Yet</h4>
      <p class="text-xs text-gray-600 max-w-xs">
        Previous SOAP notes will appear here to help with treatment continuity.
      </p>
    </div>

    <!-- SOAP Fields (Reordered: Plan → Assessment → Subjective → Objective) -->
    <div v-else-if="session" class="space-y-4">
      <!-- Plan -->
      <div class="soap-field">
        <label class="block text-xs font-semibold text-gray-700 mb-1.5">P: Plan</label>
        <p
          v-if="session.plan"
          class="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap"
        >
          {{ session.plan }}
        </p>
        <p v-else class="text-sm text-gray-500 italic">No plan notes</p>
      </div>

      <!-- Assessment -->
      <div class="soap-field">
        <label class="block text-xs font-semibold text-gray-700 mb-1.5">
          A: Assessment
        </label>
        <p
          v-if="session.assessment"
          class="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap"
        >
          {{ session.assessment }}
        </p>
        <p v-else class="text-sm text-gray-500 italic">No assessment notes</p>
      </div>

      <!-- Subjective -->
      <div class="soap-field">
        <label class="block text-xs font-semibold text-gray-700 mb-1.5">
          S: Subjective
        </label>
        <p
          v-if="session.subjective"
          class="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap"
        >
          {{ session.subjective }}
        </p>
        <p v-else class="text-sm text-gray-500 italic">No subjective notes</p>
      </div>

      <!-- Objective -->
      <div class="soap-field">
        <label class="block text-xs font-semibold text-gray-700 mb-1.5">
          O: Objective
        </label>
        <p
          v-if="session.objective"
          class="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap"
        >
          {{ session.objective }}
        </p>
        <p v-else class="text-sm text-gray-500 italic">No objective notes</p>
      </div>

      <!-- Link to Full Session -->
      <div class="pt-2 border-t border-gray-300">
        <a
          :href="sessionLink"
          target="_blank"
          rel="noopener noreferrer"
          class="inline-flex items-center text-sm text-blue-600 hover:text-blue-700 focus:underline focus:outline-none"
        >
          Open full session
          <svg class="ml-1 w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
            />
          </svg>
        </a>
      </div>
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
