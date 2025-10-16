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

import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
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

// Backend search state
const searchResults = ref<SessionResponse[]>([])
const searchResultsTotal = ref(0)
const searchLoading = ref(false)
const searchError = ref<string | null>(null)

// Pagination config
const initialPageSize = 10 // Load 10 recent sessions first
const subsequentPageSize = 20 // Load 20 when "Load More" clicked

// Year/Month grouping interfaces
interface YearGroup {
  year: number
  label: string
  sessionCount: number
  monthGroups: MonthGroup[]
  expanded: boolean
}

interface MonthGroup {
  label: string // "October 2025"
  monthKey: string // "2025-10" for unique identification
  count: number
  sessions: SessionResponse[]
  expanded: boolean
}

// Track expanded state for years and months
// Initialize with current year, but will auto-expand most recent year with sessions
const expandedYears = ref<Set<number>>(new Set([new Date().getFullYear()]))
const expandedMonths = ref<Map<string, boolean>>(new Map([['recent-sessions', true]]))

// Jump-to-date state
const showDatePicker = ref(false)
const selectedMonth = ref('')

// Backend search detection (switch to backend search when >100 sessions)
const shouldUseBackendSearch = computed(() => {
  return totalCount.value > 100
})

// Search results info for display banner
const searchResultsInfo = computed(() => {
  if (!searchQuery.value || !shouldUseBackendSearch.value) return null

  return {
    showing: searchResults.value.length,
    total: searchResultsTotal.value,
    hasMore: searchResults.value.length < searchResultsTotal.value,
  }
})

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
    if (shouldUseBackendSearch.value && searchResults.value.length > 0) {
      // Use backend search results (takes priority)
      filtered = searchResults.value

      // Apply status filter to backend results
      if (activeFilter.value === 'finalized') {
        filtered = filtered.filter((s) => !s.is_draft)
      } else if (activeFilter.value === 'drafts') {
        filtered = filtered.filter((s) => s.is_draft)
      }
    } else {
      // Client-side search (for <100 sessions or when backend fails)
      const query = searchQuery.value.toLowerCase()
      filtered = filtered.filter(
        (s) =>
          s.subjective?.toLowerCase().includes(query) ||
          s.objective?.toLowerCase().includes(query) ||
          s.assessment?.toLowerCase().includes(query) ||
          s.plan?.toLowerCase().includes(query)
      )
    }
  }

  return filtered
})

// Year-based timeline grouping
const yearGroups = computed((): YearGroup[] => {
  const groups: YearGroup[] = []
  const currentYear = new Date().getFullYear()

  // Group all filtered sessions by year
  const sessionsByYear = new Map<number, SessionResponse[]>()
  filteredSessions.value.forEach((session) => {
    const year = new Date(session.session_date).getFullYear()
    if (!sessionsByYear.has(year)) {
      sessionsByYear.set(year, [])
    }
    sessionsByYear.get(year)!.push(session)
  })

  // Convert to YearGroup structure (sorted descending: 2025, 2024, 2023...)
  const sortedYears = Array.from(sessionsByYear.entries()).sort(
    ([yearA], [yearB]) => yearB - yearA
  )

  sortedYears.forEach(([year, yearSessions], index) => {
    const monthGroups: MonthGroup[] = []

    // Note: Don't auto-expand here as it causes reactivity issues
    // Instead, we'll expand the most recent year on initial load

    // Special handling for most recent year (first in sorted list): "Recent Sessions" + months
    if (index === 0) {
      const recent = yearSessions.slice(0, 10)
      if (recent.length > 0) {
        monthGroups.push({
          label: 'Recent Sessions',
          monthKey: 'recent-sessions',
          count: recent.length,
          sessions: recent,
          expanded: expandedMonths.value.get('recent-sessions') ?? true,
        })
      }

      // Remaining sessions from most recent year grouped by month
      if (yearSessions.length > 10) {
        const older = yearSessions.slice(10)
        monthGroups.push(...groupSessionsByMonth(older))
      }
    } else {
      // Previous years: all sessions grouped by month
      monthGroups.push(...groupSessionsByMonth(yearSessions))
    }

    groups.push({
      year,
      label: year === currentYear ? `${year} (Current Year)` : String(year),
      sessionCount: yearSessions.length,
      monthGroups,
      expanded: expandedYears.value.has(year),
    })
  })

  return groups
})

// Helper function for month grouping
function groupSessionsByMonth(sessions: SessionResponse[]): MonthGroup[] {
  const grouped = new Map<string, SessionResponse[]>()

  sessions.forEach((session) => {
    const date = new Date(session.session_date)
    const monthKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`

    if (!grouped.has(monthKey)) {
      grouped.set(monthKey, [])
    }
    grouped.get(monthKey)!.push(session)
  })

  // Sort descending (most recent first)
  return Array.from(grouped.entries())
    .sort(([keyA], [keyB]) => keyB.localeCompare(keyA))
    .map(([monthKey, sessions]) => ({
      label:
        sessions.length > 0
          ? new Date(sessions[0].session_date).toLocaleDateString('en-US', {
              month: 'long',
              year: 'numeric',
            })
          : '',
      monthKey,
      count: sessions.length,
      sessions,
      expanded: expandedMonths.value.get(monthKey) ?? false,
    }))
}

// Toggle functions for years and months
function toggleYear(year: number) {
  if (expandedYears.value.has(year)) {
    expandedYears.value.delete(year)
  } else {
    expandedYears.value.add(year)
  }
}

function toggleMonth(monthKey: string) {
  const current = expandedMonths.value.get(monthKey) ?? false
  expandedMonths.value.set(monthKey, !current)
}

// Jump-to-date functionality
async function jumpToMonth(monthKey: string) {
  if (!monthKey) return

  // Parse year from input (format: "2025-10")
  const [yearStr] = monthKey.split('-')
  const year = parseInt(yearStr, 10)

  // Expand the year
  expandedYears.value.add(year)

  // Expand the specific month
  expandedMonths.value.set(monthKey, true)

  // Close date picker
  showDatePicker.value = false

  // Wait for DOM update
  await nextTick()

  // Scroll to the month group
  const monthElement = document.querySelector(`[data-month-key="${monthKey}"]`)
  if (monthElement) {
    monthElement.scrollIntoView({ behavior: 'smooth', block: 'start' })

    // Briefly highlight the month group
    monthElement.classList.add('ring-2', 'ring-blue-500', 'ring-offset-2')
    setTimeout(() => {
      monthElement.classList.remove('ring-2', 'ring-blue-500', 'ring-offset-2')
    }, 2000)
  }
}

function getCurrentMonth(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function getMinMonth(): string {
  // Get earliest session date, or default to 5 years ago
  if (sessions.value.length === 0) {
    const fiveYearsAgo = new Date()
    fiveYearsAgo.setFullYear(fiveYearsAgo.getFullYear() - 5)
    return `${fiveYearsAgo.getFullYear()}-01`
  }

  const earliestSession = sessions.value[sessions.value.length - 1]
  const date = new Date(earliestSession.session_date)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
}

/**
 * Perform backend search via API
 * Debounced to avoid excessive API calls
 */
async function performBackendSearch(query: string) {
  if (!query || query.length === 0) {
    // Clear search results
    searchResults.value = []
    searchResultsTotal.value = 0
    searchError.value = null
    return
  }

  try {
    searchLoading.value = true
    searchError.value = null

    console.log('[PreviousSessionHistory] Backend search:', {
      query,
      clientId: props.clientId,
    })

    const response = await apiClient.get<{
      items: SessionResponse[]
      total: number
      page: number
      page_size: number
    }>('/sessions', {
      params: {
        client_id: props.clientId,
        search: query,
        page: 1,
        page_size: 50, // Initial load: 50 results
      },
    })

    searchResults.value = response.data.items
    searchResultsTotal.value = response.data.total

    console.log('[PreviousSessionHistory] Backend search results:', {
      showing: searchResults.value.length,
      total: searchResultsTotal.value,
    })
  } catch (error) {
    console.error('[PreviousSessionHistory] Backend search failed:', error)
    searchError.value = 'Search failed. Showing loaded sessions only.'

    // Fallback: Clear backend results, let client-side search work
    searchResults.value = []
    searchResultsTotal.value = 0
  } finally {
    searchLoading.value = false
  }
}

// Debounced version (300ms)
const debouncedBackendSearch = useDebounceFn(performBackendSearch, 300)

/**
 * Load all matching search results (when user clicks "Load All")
 */
async function loadAllSearchResults() {
  if (!searchQuery.value || searchLoading.value) return

  if (searchResultsTotal.value > 500) {
    // Safety check: Don't load more than 500 results at once
    searchError.value = 'Too many results. Please refine your search.'
    return
  }

  try {
    searchLoading.value = true
    searchError.value = null

    const response = await apiClient.get<{
      items: SessionResponse[]
      total: number
    }>('/sessions', {
      params: {
        client_id: props.clientId,
        search: searchQuery.value,
        page: 1,
        page_size: searchResultsTotal.value, // Load all
      },
    })

    searchResults.value = response.data.items

    console.log('[PreviousSessionHistory] Loaded all search results:', {
      count: searchResults.value.length,
    })
  } catch (error) {
    console.error('[PreviousSessionHistory] Failed to load all results:', error)
    searchError.value = 'Failed to load all results.'
  } finally {
    searchLoading.value = false
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

    // Auto-expand the most recent year
    if (sessions.value.length > 0 && sessions.value[0]) {
      const mostRecentYear = new Date(sessions.value[0].session_date).getFullYear()
      if (!expandedYears.value.has(mostRecentYear)) {
        expandedYears.value.add(mostRecentYear)
      }
    }
  } catch (err) {
    console.error('Failed to load session history:', err)
    error.value = 'Failed to load session history'
  } finally {
    loading.value = false
  }
})

// Watch search query and trigger backend search when appropriate
watch(searchQuery, (newQuery) => {
  if (shouldUseBackendSearch.value && newQuery) {
    // Use backend search (debounced)
    debouncedBackendSearch(newQuery)
  } else if (!newQuery) {
    // Clear search
    searchResults.value = []
    searchResultsTotal.value = 0
    searchError.value = null
  }
  // For client-side search (<100 sessions), filteredSessions computed handles it
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
      <!-- Jump to Date Button -->
      <button
        v-if="totalCount > 20"
        type="button"
        @click="showDatePicker = true"
        class="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:outline-none"
        aria-label="Jump to specific date"
      >
        <svg
          class="h-4 w-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
          />
        </svg>
        Jump to...
      </button>
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

        <!-- Search Results Info Banner (Backend Search) -->
        <div
          v-if="searchQuery && shouldUseBackendSearch && searchResultsInfo"
          class="mt-2 rounded-lg border bg-blue-50 p-3"
          :class="{
            'border-blue-200': !searchError,
            'border-red-200 bg-red-50': searchError,
          }"
        >
          <!-- Loading State -->
          <div
            v-if="searchLoading"
            class="flex items-center gap-2 text-sm text-gray-700"
          >
            <svg
              class="h-4 w-4 animate-spin text-blue-600"
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
            <span>Searching...</span>
          </div>

          <!-- Error State -->
          <div v-else-if="searchError" class="text-sm text-red-700">
            <p class="font-medium">{{ searchError }}</p>
          </div>

          <!-- Results State -->
          <div v-else class="flex items-center justify-between">
            <div class="flex items-center gap-2 text-sm">
              <svg
                class="h-4 w-4 text-blue-600"
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
              <span class="text-gray-700">
                Showing <strong>{{ searchResultsInfo.showing }}</strong> of
                <strong>{{ searchResultsInfo.total }}</strong> matching sessions
              </span>
            </div>

            <!-- Load All Button (if more results available) -->
            <button
              v-if="searchResultsInfo.hasMore && searchResultsInfo.total <= 500"
              type="button"
              @click="loadAllSearchResults"
              :disabled="searchLoading"
              class="text-sm font-medium text-blue-600 hover:text-blue-700 focus:underline focus:outline-none disabled:cursor-not-allowed disabled:text-gray-400"
            >
              Load All Results
            </button>

            <!-- Warning (too many results) -->
            <span
              v-else-if="searchResultsInfo.hasMore && searchResultsInfo.total > 500"
              class="text-xs text-amber-700"
            >
              Refine search to see more
            </span>
          </div>
        </div>

        <!-- Search Scope Warning (Client-side search with partial data) -->
        <div
          v-if="searchQuery && !shouldUseBackendSearch && !allSessionsLoaded"
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

    <!-- Timeline Groups (Year → Month → Sessions) -->
    <div v-else class="flex-1 space-y-3 overflow-y-auto">
      <!-- Year Groups -->
      <div v-for="yearGroup in yearGroups" :key="yearGroup.year" class="space-y-3">
        <!-- Year Header (sticky, prominent) -->
        <div
          class="sticky top-0 z-10 rounded-lg border-b-2 border-gray-300 bg-gray-100 p-3 shadow-sm"
        >
          <button
            type="button"
            @click="toggleYear(yearGroup.year)"
            class="flex w-full items-center gap-3 text-left transition-colors hover:text-gray-900 focus:ring-2 focus:ring-blue-500 focus:outline-none focus:ring-inset"
            :aria-expanded="yearGroup.expanded"
            :aria-label="`${yearGroup.label}, ${yearGroup.sessionCount} sessions. ${yearGroup.expanded ? 'Collapse' : 'Expand'} year group.`"
          >
            <!-- Chevron Icon -->
            <svg
              class="h-5 w-5 flex-shrink-0 text-gray-600 transition-transform"
              :class="yearGroup.expanded ? 'rotate-90' : ''"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 5l7 7-7 7"
              />
            </svg>

            <!-- Year Label -->
            <span class="text-base font-semibold text-gray-900">
              {{ yearGroup.label }}
            </span>

            <!-- Session Count -->
            <span class="text-sm text-gray-600">({{ yearGroup.sessionCount }})</span>
          </button>
        </div>

        <!-- Month Groups (indented, only shown when year expanded) -->
        <div v-if="yearGroup.expanded" class="ml-6 space-y-2">
          <div v-for="monthGroup in yearGroup.monthGroups" :key="monthGroup.monthKey">
            <!-- Month Header -->
            <button
              type="button"
              @click="toggleMonth(monthGroup.monthKey)"
              :data-month-key="monthGroup.monthKey"
              class="flex w-full items-center gap-2 rounded-lg border border-gray-200 bg-white p-3 text-left transition-colors hover:bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:outline-none focus:ring-inset"
              :aria-expanded="monthGroup.expanded"
              :aria-label="`${monthGroup.label}, ${monthGroup.count} sessions. ${monthGroup.expanded ? 'Collapse' : 'Expand'} month.`"
            >
              <!-- Smaller Chevron -->
              <svg
                class="h-4 w-4 flex-shrink-0 text-gray-500 transition-transform"
                :class="monthGroup.expanded ? 'rotate-90' : ''"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                aria-hidden="true"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M9 5l7 7-7 7"
                />
              </svg>

              <!-- Month Label -->
              <span class="text-sm font-medium text-gray-800">
                {{ monthGroup.label }}
              </span>

              <!-- Session Count -->
              <span class="text-xs text-gray-500">({{ monthGroup.count }})</span>
            </button>

            <!-- Sessions (further indented, only shown when month expanded) -->
            <div v-if="monthGroup.expanded" class="mt-2 ml-6 space-y-2">
              <button
                v-for="session in monthGroup.sessions"
                :key="session.id"
                type="button"
                @click="emit('select-session', session.id)"
                class="w-full rounded-lg border border-gray-200 bg-white p-3 text-left transition-all hover:border-gray-300 hover:bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:outline-none focus:ring-inset"
                :aria-label="`Session from ${formatLongDate(session.session_date)}. ${session.is_draft ? 'Draft' : 'Finalized'}. ${getPreview(session)}`"
              >
                <!-- Session Card Content -->
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

    <!-- Jump to Date Modal -->
    <Teleport to="body">
      <Transition name="modal">
        <div
          v-if="showDatePicker"
          class="fixed inset-0 z-50 flex items-center justify-center bg-black/20 p-4"
          @click.self="showDatePicker = false"
        >
          <div
            class="w-full max-w-sm rounded-lg border border-gray-200 bg-white p-6 shadow-xl"
            role="dialog"
            aria-modal="true"
            aria-labelledby="date-picker-title"
          >
            <h3 id="date-picker-title" class="mb-4 text-lg font-semibold text-gray-900">
              Jump to Date
            </h3>

            <label
              for="month-picker"
              class="mb-2 block text-sm font-medium text-gray-700"
            >
              Select Month
            </label>
            <input
              id="month-picker"
              v-model="selectedMonth"
              type="month"
              class="mb-4 w-full rounded-lg border-gray-300 text-sm focus:border-blue-500 focus:ring-blue-500"
              :min="getMinMonth()"
              :max="getCurrentMonth()"
            />

            <div class="flex gap-2">
              <button
                type="button"
                @click="showDatePicker = false"
                class="flex-1 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              >
                Cancel
              </button>
              <button
                type="button"
                @click="jumpToMonth(selectedMonth)"
                :disabled="!selectedMonth"
                class="flex-1 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-gray-300"
              >
                Jump
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
.line-clamp-1 {
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 1;
}

/* Modal transitions */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active > div,
.modal-leave-active > div {
  transition: transform 0.3s ease;
}

.modal-enter-from > div,
.modal-leave-to > div {
  transform: scale(0.95);
}
</style>
