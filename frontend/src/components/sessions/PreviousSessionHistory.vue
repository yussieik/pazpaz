<script setup lang="ts">
/**
 * PreviousSessionHistory Component
 *
 * Displays a searchable timeline of all previous sessions for a client.
 * Allows navigation to any historical session for detailed review.
 *
 * Features:
 * - Smart initial load (10 sessions) with progressive loading
 * - Timeline grouping (Recent expanded, older collapsed by month)
 * - Quick filters (All/Finalized/Drafts)
 * - Enhanced search with scope warning
 * - Loading and error states
 * - Optimized for mobile performance
 *
 * Usage:
 *   <PreviousSessionHistory
 *     :client-id="clientId"
 *     :current-session-id="sessionId"
 *     @select-session="loadHistoricalSession"
 *     @back="showSummary"
 *   />
 */

import { ref, computed, onMounted } from 'vue'
import { formatLongDate } from '@/utils/calendar/dateFormatters'
import apiClient from '@/api/client'
import type { SessionResponse } from '@/types/sessions'

interface Props {
  clientId: string
  currentSessionId: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'select-session', sessionId: string): void
  (e: 'back'): void
}>()

// State
const sessions = ref<SessionResponse[]>([])
const loading = ref(true)
const loadingMore = ref(false)
const error = ref<string | null>(null)
const currentPage = ref(1)
const totalCount = ref(0)
const searchQuery = ref('')
const activeFilter = ref<'all' | 'finalized' | 'drafts'>('all')

// Pagination config
const initialPageSize = 10 // Load 10 recent sessions first
const subsequentPageSize = 20 // Load 20 when "Load More" clicked

// Timeline group interface
interface TimelineGroup {
  label: string
  count: number
  sessions: SessionResponse[]
  expanded: boolean
}

// Track expanded state for groups (label -> expanded boolean)
const expandedGroups = ref<Map<string, boolean>>(new Map([['Recent Sessions', true]]))

// Quick filters
const filters = computed(() => [
  { label: 'All', value: 'all' as const, count: sessions.value.length },
  {
    label: 'Finalized',
    value: 'finalized' as const,
    count: sessions.value.filter((s) => !s.is_draft).length,
  },
  {
    label: 'Drafts',
    value: 'drafts' as const,
    count: sessions.value.filter((s) => s.is_draft).length,
  },
])

// Filter sessions by search query and active filter
const filteredSessions = computed(() => {
  let filtered = sessions.value

  // Apply status filter
  if (activeFilter.value === 'finalized') {
    filtered = filtered.filter((s) => !s.is_draft)
  } else if (activeFilter.value === 'drafts') {
    filtered = filtered.filter((s) => s.is_draft)
  }

  // Apply search
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.filter(
      (s) =>
        s.subjective?.toLowerCase().includes(query) ||
        s.objective?.toLowerCase().includes(query) ||
        s.assessment?.toLowerCase().includes(query) ||
        s.plan?.toLowerCase().includes(query)
    )
  }

  return filtered
})

// Timeline grouping
const timelineGroups = computed(() => {
  const groups: TimelineGroup[] = []

  // Group 1: Recent (first 10 sessions) - EXPANDED by default
  const recent = filteredSessions.value.slice(0, 10)
  if (recent.length > 0) {
    const label = 'Recent Sessions'
    groups.push({
      label,
      count: recent.length,
      sessions: recent,
      expanded: expandedGroups.value.get(label) ?? true, // Default expanded
    })
  }

  // Group 2-N: Older sessions grouped by month
  if (filteredSessions.value.length > 10) {
    const older = filteredSessions.value.slice(10)
    const monthGroups = groupByMonth(older)
    groups.push(...monthGroups)
  }

  return groups
})

function groupByMonth(sessions: SessionResponse[]): TimelineGroup[] {
  const grouped = new Map<string, SessionResponse[]>()

  sessions.forEach((session) => {
    const date = new Date(session.session_date)
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`

    if (!grouped.has(key)) {
      grouped.set(key, [])
    }
    grouped.get(key)!.push(session)
  })

  return Array.from(grouped.entries())
    .sort(([keyA], [keyB]) => keyB.localeCompare(keyA)) // Sort descending
    .map(([_, sessions]) => {
      const label = sessions[0]
        ? new Date(sessions[0].session_date).toLocaleDateString('en-US', {
            month: 'long',
            year: 'numeric',
          })
        : ''
      return {
        label,
        count: sessions.length,
        sessions,
        expanded: expandedGroups.value.get(label) ?? false, // Default collapsed
      }
    })
}

function toggleGroup(index: number) {
  const group = timelineGroups.value[index]
  if (group) {
    expandedGroups.value.set(group.label, !group.expanded)
  }
}

// Pagination
const hasMoreSessions = computed(() => sessions.value.length < totalCount.value)
const remainingCount = computed(() => totalCount.value - sessions.value.length)
const allSessionsLoaded = computed(() => sessions.value.length >= totalCount.value)

// Load more sessions
async function loadMoreSessions() {
  if (loadingMore.value || sessions.value.length >= totalCount.value) return

  try {
    loadingMore.value = true
    currentPage.value++

    const response = await apiClient.get(
      `/sessions?client_id=${props.clientId}&page=${currentPage.value}&page_size=${subsequentPageSize}`
    )

    const newSessions = (response.data.items || []).filter(
      (s: SessionResponse) => s.id !== props.currentSessionId && !s.deleted_at
    )

    sessions.value.push(...newSessions)
    sessions.value.sort(
      (a, b) => new Date(b.session_date).getTime() - new Date(a.session_date).getTime()
    )
  } finally {
    loadingMore.value = false
  }
}

// Initial load: 10 most recent sessions
onMounted(async () => {
  try {
    loading.value = true
    error.value = null

    const response = await apiClient.get(
      `/sessions?client_id=${props.clientId}&page=1&page_size=${initialPageSize}`
    )

    sessions.value = (response.data.items || [])
      .filter((s: SessionResponse) => s.id !== props.currentSessionId && !s.deleted_at)
      .sort(
        (a: SessionResponse, b: SessionResponse) =>
          new Date(b.session_date).getTime() - new Date(a.session_date).getTime()
      )

    totalCount.value = response.data.total || sessions.value.length
  } catch (err) {
    console.error('Failed to load session history:', err)
    error.value = 'Failed to load session history'
  } finally {
    loading.value = false
  }
})

function getPreview(session: SessionResponse): string {
  const content =
    session.plan || session.assessment || session.subjective || session.objective
  if (!content) return 'No content'
  return content.length > 60 ? content.substring(0, 60) + '...' : content
}
</script>

<template>
  <div class="flex h-full flex-col">
    <!-- Header -->
    <div class="mb-4 flex items-center gap-2 border-b border-gray-200 pb-3">
      <button
        @click="emit('back')"
        class="rounded p-1 text-gray-600 hover:text-gray-900 focus:ring-2 focus:ring-blue-500 focus:outline-none"
        type="button"
        aria-label="Go back"
      >
        <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M15 19l-7-7 7-7"
          />
        </svg>
      </button>
      <div class="flex-1">
        <h3 class="text-sm font-semibold text-gray-900">Treatment Context</h3>
        <p v-if="totalCount > 0" class="text-xs text-gray-600">
          {{ totalCount }} {{ totalCount === 1 ? 'session' : 'sessions' }} total
        </p>
      </div>
    </div>

    <!-- Filters & Search -->
    <div class="mb-4 space-y-3">
      <!-- Quick Filters -->
      <div class="flex gap-2 overflow-x-auto pb-1">
        <button
          v-for="filter in filters"
          :key="filter.value"
          @click="activeFilter = filter.value"
          :class="[
            'rounded-full px-3 py-1.5 text-xs font-medium whitespace-nowrap transition-colors',
            activeFilter === filter.value
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
          ]"
          type="button"
        >
          {{ filter.label }}
          <span v-if="filter.count > 0" class="ml-1 opacity-75"
            >({{ filter.count }})</span
          >
        </button>
      </div>

      <!-- Search -->
      <div class="relative">
        <input
          v-model="searchQuery"
          type="search"
          placeholder="Search sessions..."
          class="block w-full rounded-md border-gray-300 pl-10 text-sm shadow-sm focus:border-blue-500 focus:ring-blue-500"
        />
        <svg
          class="absolute top-2.5 left-3 h-5 w-5 text-gray-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>

        <!-- Search Scope Warning -->
        <div
          v-if="searchQuery && !allSessionsLoaded"
          class="mt-2 flex items-start gap-2 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-800"
        >
          <svg
            class="mt-0.5 h-4 w-4 flex-shrink-0"
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
          <span>
            Searching {{ sessions.length }} loaded sessions.
            <button
              @click="loadMoreSessions"
              class="font-medium underline hover:text-amber-900"
              type="button"
            >
              Load all {{ totalCount }}
            </button>
          </span>
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="space-y-2">
      <div
        v-for="i in 3"
        :key="i"
        class="animate-pulse rounded-lg border border-gray-200 p-3"
      >
        <div class="mb-2 flex items-center justify-between">
          <div class="h-4 w-32 rounded bg-gray-300"></div>
          <div class="h-2 w-2 rounded-full bg-gray-300"></div>
        </div>
        <div class="h-3 w-full rounded bg-gray-200"></div>
      </div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="rounded-lg bg-red-50 p-4 text-center">
      <p class="text-sm text-red-800">{{ error }}</p>
    </div>

    <!-- Empty State (No Sessions) -->
    <div
      v-else-if="sessions.length === 0"
      class="flex flex-col items-center justify-center py-12 text-center"
    >
      <svg
        class="h-16 w-16 text-gray-300"
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
      <h4 class="mt-4 text-sm font-semibold text-gray-900">No sessions found</h4>
      <p class="mt-1 max-w-xs text-xs text-gray-600">
        Session notes will appear here after completing appointments
      </p>
    </div>

    <!-- Timeline Groups -->
    <div v-else class="flex-1 space-y-3 overflow-y-auto">
      <div
        v-for="(group, index) in timelineGroups"
        :key="group.label"
        class="space-y-2"
      >
        <!-- Group Header -->
        <button
          @click="toggleGroup(index)"
          class="flex w-full items-center justify-between rounded-lg border border-gray-200 bg-white p-3 text-left transition-colors hover:bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:outline-none"
          type="button"
        >
          <div class="flex items-center gap-2">
            <svg
              class="h-4 w-4 text-gray-500 transition-transform"
              :class="group.expanded ? 'rotate-90' : ''"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 5l7 7-7 7"
              />
            </svg>
            <span class="text-sm font-medium text-gray-900">{{ group.label }}</span>
            <span class="text-xs text-gray-500">({{ group.count }})</span>
          </div>
        </button>

        <!-- Expanded Sessions -->
        <div v-if="group.expanded" class="space-y-2 pl-4">
          <button
            v-for="session in group.sessions"
            :key="session.id"
            @click="emit('select-session', session.id)"
            class="w-full rounded-lg border border-gray-200 bg-white p-3 text-left transition-all hover:border-gray-300 hover:bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            type="button"
          >
            <div class="mb-1 flex items-center justify-between">
              <p class="text-sm font-medium text-gray-900">
                {{ formatLongDate(session.session_date) }}
              </p>
              <span
                :class="[
                  'inline-flex h-2 w-2 rounded-full',
                  session.is_draft ? 'bg-blue-500' : 'bg-green-500',
                ]"
                :title="session.is_draft ? 'Draft' : 'Finalized'"
              />
            </div>
            <p class="line-clamp-1 text-xs text-gray-600">
              {{ getPreview(session) }}
            </p>
          </button>
        </div>
      </div>

      <!-- Load More Button -->
      <button
        v-if="hasMoreSessions"
        @click="loadMoreSessions"
        :disabled="loadingMore"
        class="mt-4 w-full rounded-lg border border-gray-200 py-3 text-sm font-medium text-blue-600 transition-colors hover:bg-blue-50 focus:ring-2 focus:ring-blue-500 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
        type="button"
      >
        <span v-if="!loadingMore">
          Load More Sessions ({{ remainingCount }} older)
        </span>
        <span v-else class="flex items-center justify-center gap-2">
          <svg
            class="h-4 w-4 animate-spin"
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
          Loading...
        </span>
      </button>

      <!-- End of List -->
      <div
        v-if="!hasMoreSessions && sessions.length > 10"
        class="py-4 text-center text-sm text-gray-500"
      >
        All {{ totalCount }} sessions loaded
      </div>

      <!-- No Search Results -->
      <div
        v-if="filteredSessions.length === 0 && searchQuery"
        class="flex flex-col items-center justify-center py-12 text-center"
      >
        <svg
          class="h-12 w-12 text-gray-300"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="1.5"
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
        <h4 class="mt-4 text-sm font-semibold text-gray-900">No sessions found</h4>
        <p class="mt-1 max-w-xs text-xs text-gray-600">
          Try adjusting your search terms or filter
        </p>
        <button
          @click="searchQuery = ''"
          class="mt-3 text-sm text-blue-600 hover:text-blue-700 focus:underline focus:outline-none"
          type="button"
        >
          Clear search
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.line-clamp-1 {
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 1;
}
</style>
