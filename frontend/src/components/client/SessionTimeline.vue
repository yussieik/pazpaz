<script setup lang="ts">
/**
 * SessionTimeline Component
 *
 * Displays a chronological timeline of treatment history combining:
 * - Session notes (SOAP documentation) with draft/finalized status
 * - Completed appointments without session notes (with option to create)
 *
 * Features:
 * - Chronological order (most recent first)
 * - SOAP preview for sessions
 * - Create session note from appointment
 * - Navigation to session detail view
 * - Empty state for new clients
 * - Loading and error states
 *
 * Usage:
 *   <SessionTimeline :client-id="clientId" />
 */

import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { format } from 'date-fns'
import { useDebounceFn } from '@vueuse/core'
import { useI18n } from '@/composables/useI18n'
import apiClient from '@/api/client'
import type { AxiosError } from 'axios'
import type { SessionResponse } from '@/types/sessions'
import SessionCard from '@/components/sessions/SessionCard.vue'
import AttachmentBadge from '@/components/sessions/AttachmentBadge.vue'
import ImagePreviewModal from '@/components/sessions/ImagePreviewModal.vue'
import IconDocument from '@/components/icons/IconDocument.vue'
import { smartTruncate } from '@/utils/textFormatters'
import { getDurationMinutes } from '@/utils/calendar/dateFormatters'
import type { AttachmentResponse } from '@/types/attachments'
import { isImageType } from '@/types/attachments'

const { t } = useI18n()

interface Props {
  clientId: string
}

const props = defineProps<Props>()

interface Emits {
  (e: 'session-deleted'): void
  (e: 'trigger-badge-pulse'): void
}

const emit = defineEmits<Emits>()
const router = useRouter()

// Appointment data interface
interface AppointmentItem {
  id: string
  client_id: string
  scheduled_start: string
  scheduled_end: string
  location_type: 'clinic' | 'home' | 'online'
  notes: string | null
  status: 'scheduled' | 'attended' | 'cancelled' | 'no_show'
  service_name?: string | null
}

// Year/Month grouping interfaces
interface YearGroup {
  year: number
  label: string
  sessionCount: number
  monthGroups: MonthGroup[]
  appointmentGroups?: MonthGroup[] // For appointments without sessions
  expanded: boolean
}

interface MonthGroup {
  label: string
  monthKey: string
  count: number
  sessions: SessionResponse[]
  appointments?: AppointmentItem[] // For appointments without sessions
  expanded: boolean
}

// State
const sessions = ref<SessionResponse[]>([])
const appointments = ref<AppointmentItem[]>([])
const sessionAppointments = ref<Map<string, AppointmentItem>>(new Map())
const loading = ref(true)
const error = ref<string | null>(null)

// Pagination state
const currentPage = ref(1)
const totalCount = ref(0)
const loadingMore = ref(false)

const PAGE_SIZE_INITIAL = 20
const PAGE_SIZE_MORE = 30

// Search state
const searchQuery = ref('')
const searchResults = ref<SessionResponse[]>([])
const searchResultsTotal = ref(0)
const searchLoading = ref(false)
const searchError = ref<string | null>(null)

// Year/Month grouping state
const expandedYears = ref<Set<number>>(new Set([new Date().getFullYear()]))
const expandedMonths = ref<Map<string, boolean>>(new Map([['recent-sessions', true]]))

// Jump-to-date state
const showDatePicker = ref(false)
const selectedMonth = ref('')

// Attachment preview state
const showAttachmentPreview = ref(false)
const previewSessionId = ref<string | null>(null)
const sessionAttachments = ref<AttachmentResponse[]>([])
const previewImageIndex = ref(0)

// Computed properties
const hasMoreSessions = computed(() => sessions.value.length < totalCount.value)
const remainingCount = computed(() => totalCount.value - sessions.value.length)

const shouldUseBackendSearch = computed(() => totalCount.value > 100)

const searchResultsInfo = computed(() => {
  if (!searchQuery.value || !shouldUseBackendSearch.value) return null

  return {
    showing: searchResults.value.length,
    total: searchResultsTotal.value,
    hasMore: searchResults.value.length < searchResultsTotal.value,
  }
})

const isEmpty = computed(
  () => sessions.value.length === 0 && appointments.value.length === 0
)

// Fetch data
onMounted(async () => {
  // IMPORTANT: Must fetch sessions FIRST before appointments
  // fetchAppointments() depends on sessions.value to filter out appointments with existing sessions
  await fetchSessions()
  await fetchAppointments()
})

async function fetchSessions() {
  try {
    loading.value = true

    // Add pagination parameters
    const response = await apiClient.get('/sessions', {
      params: {
        client_id: props.clientId,
        page: currentPage.value,
        page_size: currentPage.value === 1 ? PAGE_SIZE_INITIAL : PAGE_SIZE_MORE,
      },
    })

    const fetchedSessions = response.data.items || []

    // First page: replace; subsequent pages: append
    if (currentPage.value === 1) {
      sessions.value = fetchedSessions
    } else {
      sessions.value.push(...fetchedSessions)
    }

    // Store total count
    totalCount.value = response.data.total || 0

    // Fetch appointment details for sessions that have appointment_id
    const appointmentIds = fetchedSessions
      .map((s: SessionResponse) => s.appointment_id)
      .filter(Boolean) as string[]

    if (appointmentIds.length > 0) {
      // Fetch appointments in parallel
      const appointmentPromises = appointmentIds.map((id) =>
        apiClient.get(`/appointments/${id}`).catch(() => null)
      )
      const appointmentResponses = await Promise.all(appointmentPromises)

      // Build map of session_id -> appointment
      fetchedSessions.forEach((session: SessionResponse, index: number) => {
        if (session.appointment_id && appointmentResponses[index]?.data) {
          sessionAppointments.value.set(session.id, appointmentResponses[index].data)
        }
      })
    }
  } catch (err) {
    console.error('Failed to fetch sessions:', err)
    const axiosError = err as AxiosError<{ detail?: string }>
    error.value = axiosError.response?.data?.detail || 'Failed to load session history'
  } finally {
    loading.value = false
  }
}

async function fetchAppointments() {
  try {
    // Fetch attended appointments for this client
    const response = await apiClient.get(
      `/appointments?client_id=${props.clientId}&status=attended`
    )

    // Filter out appointments that already have sessions
    const sessionAppointmentIds = new Set(
      sessions.value.map((s) => s.appointment_id).filter(Boolean)
    )

    const filteredAppointments = (response.data.items || []).filter(
      (appt: AppointmentItem) => !sessionAppointmentIds.has(appt.id)
    )
    appointments.value = filteredAppointments
  } catch (err) {
    console.error('Failed to fetch appointments:', err)
    // Don't set error - appointments are supplementary
  }
}

async function loadMoreSessions() {
  if (loadingMore.value || !hasMoreSessions.value) return

  try {
    loadingMore.value = true
    currentPage.value++
    await fetchSessions()
  } catch (error) {
    console.error('Failed to load more sessions:', error)
    currentPage.value-- // Revert page increment on error
  } finally {
    loadingMore.value = false
  }
}

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
        sessions.length > 0 && sessions[0]
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

// Year-based timeline grouping
const yearGroups = computed((): YearGroup[] => {
  // Use search results if searching with backend
  let sessionsToGroup = sessions.value
  if (
    searchQuery.value &&
    shouldUseBackendSearch.value &&
    searchResults.value.length > 0
  ) {
    sessionsToGroup = searchResults.value
  }

  const groups: YearGroup[] = []

  // Group all sessions by year
  const sessionsByYear = new Map<number, SessionResponse[]>()
  sessionsToGroup.forEach((session) => {
    const year = new Date(session.session_date).getFullYear()
    if (!sessionsByYear.has(year)) {
      sessionsByYear.set(year, [])
    }
    sessionsByYear.get(year)!.push(session)
  })

  // Convert to YearGroup structure (sorted descending: 2025, 2024, 2023...)
  Array.from(sessionsByYear.entries())
    .sort(([yearA], [yearB]) => yearB - yearA)
    .forEach(([year, yearSessions], index) => {
      const monthGroups: MonthGroup[] = []

      // Special handling for most recent year (first in sorted list): "Recent Sessions" + months
      if (index === 0) {
        const recent = yearSessions.slice(0, 10)
        if (recent.length > 0) {
          monthGroups.push({
            label: t('clients.detailView.history.recentSessions'),
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
        label: String(year),
        sessionCount: yearSessions.length,
        monthGroups,
        expanded: expandedYears.value.has(year),
      })
    })

  return groups
})

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

// Backend search
async function performBackendSearch(query: string) {
  if (!query || query.length === 0) {
    searchResults.value = []
    searchResultsTotal.value = 0
    searchError.value = null
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
        search: query,
        page: 1,
        page_size: 50,
      },
    })

    searchResults.value = response.data.items
    searchResultsTotal.value = response.data.total
  } catch (error) {
    console.error('Backend search failed:', error)
    searchError.value = 'Search failed. Showing loaded sessions only.'
    searchResults.value = []
    searchResultsTotal.value = 0
  } finally {
    searchLoading.value = false
  }
}

const debouncedBackendSearch = useDebounceFn(performBackendSearch, 300)

async function loadAllSearchResults() {
  if (!searchQuery.value || searchLoading.value || searchResultsTotal.value > 500)
    return

  try {
    searchLoading.value = true
    const response = await apiClient.get<{
      items: SessionResponse[]
      total: number
    }>('/sessions', {
      params: {
        client_id: props.clientId,
        search: searchQuery.value,
        page: 1,
        page_size: searchResultsTotal.value,
      },
    })

    searchResults.value = response.data.items
  } catch (error) {
    console.error('Failed to load all search results:', error)
    searchError.value = 'Failed to load all results.'
  } finally {
    searchLoading.value = false
  }
}

// Jump-to-date functionality
async function jumpToMonth(monthKey: string) {
  if (!monthKey) return

  const [yearStr] = monthKey.split('-')
  const year = parseInt(yearStr || '0', 10)

  expandedYears.value.add(year)
  expandedMonths.value.set(monthKey, true)

  showDatePicker.value = false

  await nextTick()

  const monthElement = document.querySelector(`[data-month-key="${monthKey}"]`)
  if (monthElement) {
    monthElement.scrollIntoView({ behavior: 'smooth', block: 'start' })

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
  if (sessions.value.length === 0) {
    const fiveYearsAgo = new Date()
    fiveYearsAgo.setFullYear(fiveYearsAgo.getFullYear() - 5)
    return `${fiveYearsAgo.getFullYear()}-01`
  }

  const earliestSession = sessions.value[sessions.value.length - 1]
  if (!earliestSession) {
    const fiveYearsAgo = new Date()
    fiveYearsAgo.setFullYear(fiveYearsAgo.getFullYear() - 5)
    return `${fiveYearsAgo.getFullYear()}-01`
  }

  const date = new Date(earliestSession.session_date)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
}

// Watch search query and trigger backend search when appropriate
watch(searchQuery, (newQuery) => {
  if (shouldUseBackendSearch.value && newQuery) {
    debouncedBackendSearch(newQuery)
  } else if (!newQuery) {
    searchResults.value = []
    searchResultsTotal.value = 0
    searchError.value = null
  }
})

// Actions
function viewSession(sessionId: string) {
  router.push({
    path: `/sessions/${sessionId}`,
    state: {
      from: 'client-history',
      clientId: props.clientId,
      returnTo: 'client-detail',
    },
  })
}

async function createSession(appointmentId: string) {
  try {
    const appointment = appointments.value.find((a) => a.id === appointmentId)
    if (!appointment) return

    const response = await apiClient.post('/sessions', {
      client_id: props.clientId,
      appointment_id: appointmentId,
      session_date: appointment.scheduled_start,
      duration_minutes: getDurationMinutes(
        appointment.scheduled_start,
        appointment.scheduled_end
      ),
      is_draft: true,
    })

    router.push({
      path: `/sessions/${response.data.id}`,
      state: {
        from: 'client-history',
        clientId: props.clientId,
        returnTo: 'client-detail',
      },
    })
  } catch (err) {
    console.error('Failed to create session:', err)
    alert('Failed to create session note. Please try again.')
  }
}

function formatDate(date: string): string {
  return format(new Date(date), 'MMM d, yyyy • h:mm a')
}

/**
 * Handle session deletion from SessionCard
 * Remove from local array and notify parent
 */
function handleSessionDeleted(sessionId: string) {
  // Remove from local sessions array (optimistic update)
  sessions.value = sessions.value.filter((s) => s.id !== sessionId)

  // Notify parent to refresh DeletedNotesSection
  emit('session-deleted')

  // Trigger badge pulse if Deleted Notes section is collapsed
  emit('trigger-badge-pulse')
}

/**
 * Handle view session from SessionCard
 */
function handleViewSession(sessionId: string) {
  viewSession(sessionId)
}

/**
 * Handle click on attachment badge - show preview or navigate to session
 */
async function handleAttachmentBadgeClick(sessionId: string) {
  try {
    // Fetch attachments for this session
    const response = await apiClient.get(`/sessions/${sessionId}/attachments`)
    sessionAttachments.value = response.data.items || []

    // Filter to images only for preview
    const images = sessionAttachments.value.filter((a) => isImageType(a.file_type))

    if (images.length > 0) {
      // Has images - show preview modal
      previewSessionId.value = sessionId
      previewImageIndex.value = 0
      showAttachmentPreview.value = true
    } else {
      // No images (only PDFs) - navigate to session detail
      router.push({
        path: `/sessions/${sessionId}`,
        hash: '#attachments',
        state: {
          from: 'client-history',
          clientId: props.clientId,
          returnTo: 'client-detail',
        },
      })
    }
  } catch (error) {
    console.error('Failed to load attachments:', error)
    // Fallback: navigate to session
    router.push({
      path: `/sessions/${sessionId}`,
      hash: '#attachments',
      state: {
        from: 'client-history',
        clientId: props.clientId,
        returnTo: 'client-detail',
      },
    })
  }
}

/**
 * Handle download from preview modal
 */
async function handleDownloadFromPreview(attachment: AttachmentResponse) {
  if (!attachment.session_id) return

  try {
    const response = await apiClient.get(
      `/sessions/${attachment.session_id}/attachments/${attachment.id}/download`
    )
    const downloadUrl = response.data.download_url

    const newTab = window.open(downloadUrl, '_blank')
    if (!newTab) {
      throw new Error('Popup blocked. Please allow popups for this site.')
    }
  } catch (error) {
    console.error('Download error:', error)
    alert('Failed to download file')
  }
}

/**
 * Update preview index
 */
function updatePreviewIndex(index: number) {
  previewImageIndex.value = index
}

/**
 * Refresh the timeline by fetching both sessions and appointments
 * Exposed to parent components for manual refresh triggers
 * IMPORTANT: Must fetch sessions FIRST before appointments (fetchAppointments depends on sessions.value)
 */
async function refresh() {
  await fetchSessions()
  await fetchAppointments()
}

// Expose refresh method to parent components
defineExpose({
  refresh,
})
</script>

<template>
  <div class="session-timeline">
    <!-- Loading State -->
    <div v-if="loading" class="flex items-center justify-center py-12">
      <div
        class="h-8 w-8 animate-spin rounded-full border-b-2 border-emerald-600"
      ></div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="rounded-md bg-red-50 p-4">
      <p class="text-sm text-red-800">{{ error }}</p>
    </div>

    <!-- Empty State -->
    <div v-else-if="isEmpty" class="py-12 text-center">
      <IconDocument size="lg" class="mx-auto text-slate-400" />
      <h3 class="mt-2 text-sm font-medium text-slate-900">
        {{ t('sessions.timeline.emptyStateTitle') }}
      </h3>
      <p class="mt-1 text-sm text-slate-500">
        {{ t('sessions.timeline.emptyStateDescription') }}
      </p>
    </div>

    <!-- Header with Jump to Date -->
    <div
      v-if="!isEmpty && !loading && !error"
      class="mb-4 flex items-center justify-end"
    >
      <!-- Jump to Date Button -->
      <button
        v-if="totalCount > 20"
        type="button"
        @click="showDatePicker = true"
        class="inline-flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
      >
        <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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

    <!-- Search Input -->
    <div v-if="!isEmpty && !loading && totalCount > 20" class="mb-4">
      <div class="relative">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search session notes..."
          class="w-full rounded-lg border border-gray-300 bg-white py-2 pr-4 pl-10 text-sm focus:border-blue-500 focus:ring-2 focus:ring-blue-500 focus:outline-none"
        />
        <svg
          class="absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2 text-gray-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
          />
        </svg>
      </div>
    </div>

    <!-- Search Results Info Banner -->
    <div
      v-if="searchQuery && shouldUseBackendSearch && searchResultsInfo"
      class="mb-3 rounded-lg border bg-blue-50 p-3"
      :class="{
        'border-blue-200': !searchError,
        'border-red-200 bg-red-50': searchError,
      }"
    >
      <!-- Loading State -->
      <div v-if="searchLoading" class="flex items-center gap-2 text-sm text-gray-700">
        <svg class="h-4 w-4 animate-spin text-blue-600" fill="none" viewBox="0 0 24 24">
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
        {{ searchError }}
      </div>

      <!-- Results State -->
      <div v-else class="flex items-center justify-between">
        <div class="flex items-center gap-2 text-sm text-gray-700">
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
          <span>
            Showing <strong>{{ searchResultsInfo.showing }}</strong> of
            <strong>{{ searchResultsInfo.total }}</strong> matching sessions
          </span>
        </div>

        <button
          v-if="searchResultsInfo.hasMore && searchResultsInfo.total <= 500"
          type="button"
          @click="loadAllSearchResults"
          :disabled="searchLoading"
          class="text-sm font-medium text-blue-600 hover:text-blue-700 focus:underline focus:outline-none disabled:cursor-not-allowed disabled:text-gray-400"
        >
          Load All Results
        </button>
      </div>
    </div>

    <!-- Year Groups -->
    <div v-if="!isEmpty && !loading && !error" class="space-y-4">
      <div v-for="yearGroup in yearGroups" :key="yearGroup.year" class="space-y-3">
        <!-- Year Header (sticky, prominent) -->
        <div
          class="sticky top-0 z-10 rounded-lg border-b-2 border-gray-300 bg-gray-100/95 p-3 shadow-sm backdrop-blur-sm"
        >
          <button
            type="button"
            @click="toggleYear(yearGroup.year)"
            class="flex w-full items-center gap-3 text-left transition-colors hover:text-gray-900 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-inset"
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
            <!-- Month Header (sticky below year header) -->
            <button
              type="button"
              @click="toggleMonth(monthGroup.monthKey)"
              :data-month-key="monthGroup.monthKey"
              class="sticky top-[52px] z-[9] flex w-full items-center gap-2 rounded-lg border border-gray-200 bg-white/95 p-3 text-left shadow-sm backdrop-blur-sm transition-colors hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-inset"
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
            <TransitionGroup
              v-if="monthGroup.expanded"
              name="session-list"
              tag="div"
              class="mt-2 ml-6 space-y-3"
            >
              <SessionCard
                v-for="session in monthGroup.sessions"
                :key="`session-${session.id}`"
                :session="session"
                class="transition-all"
                @deleted="handleSessionDeleted"
                @view="handleViewSession"
              >
                <template #content>
                  <div class="flex items-start gap-3">
                    <!-- Icon -->
                    <div class="flex-shrink-0">
                      <div
                        class="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100"
                      >
                        <svg
                          class="h-5 w-5 text-blue-600"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            stroke-width="2"
                            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                          />
                        </svg>
                      </div>
                    </div>

                    <!-- Content -->
                    <div class="min-w-0 flex-1">
                      <div class="mb-1.5 flex items-center justify-between gap-2 pe-12">
                        <!-- pe-12 reserves 48px for trash icon on end side -->

                        <!-- Left Side: Status and Date -->
                        <div class="flex min-w-0 flex-1 items-center gap-2">
                          <!-- Status Badge -->
                          <span
                            :class="[
                              'inline-flex flex-shrink-0 items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium',
                              session.is_draft
                                ? 'bg-amber-100 text-amber-800'
                                : 'bg-green-100 text-green-800',
                            ]"
                          >
                            <span
                              class="h-1.5 w-1.5 rounded-full"
                              :class="
                                session.is_draft ? 'bg-amber-500' : 'bg-green-500'
                              "
                            ></span>
                            {{
                              session.is_draft
                                ? t('clients.detailView.history.statusDraft')
                                : t('clients.detailView.history.statusFinalized')
                            }}
                          </span>

                          <!-- Date and Time -->
                          <h4 class="truncate text-sm font-medium text-slate-900">
                            {{ formatDate(session.session_date) }}
                          </h4>
                        </div>

                        <!-- Right Side: Attachment Badge -->
                        <AttachmentBadge
                          v-if="session.attachment_count > 0"
                          :count="session.attachment_count"
                          size="sm"
                          @click="handleAttachmentBadgeClick(session.id)"
                        />
                      </div>

                      <!-- Appointment Context (if appointment exists) -->
                      <p
                        v-if="sessionAppointments.get(session.id)"
                        class="mt-1 text-xs text-slate-500"
                      >
                        {{
                          getDurationMinutes(
                            sessionAppointments.get(session.id)!.scheduled_start,
                            sessionAppointments.get(session.id)!.scheduled_end
                          )
                        }}
                        {{ t('clients.detailView.history.minutes') }} •
                        {{
                          sessionAppointments.get(session.id)!.location_type ===
                          'clinic'
                            ? t('clients.detailView.history.locationClinic')
                            : sessionAppointments.get(session.id)!.location_type ===
                                'home'
                              ? t('clients.detailView.history.locationHome')
                              : t('clients.detailView.history.locationTelehealth')
                        }}
                      </p>

                      <!-- SOAP Preview -->
                      <div class="mt-2 space-y-1 text-sm">
                        <p
                          v-if="session.subjective"
                          class="line-clamp-2 text-slate-700"
                        >
                          <strong class="font-medium">S:</strong>
                          {{ smartTruncate(session.subjective, 100) }}
                        </p>
                        <p v-if="session.objective" class="line-clamp-2 text-slate-700">
                          <strong class="font-medium">O:</strong>
                          {{ smartTruncate(session.objective, 100) }}
                        </p>
                        <p
                          v-if="session.assessment"
                          class="line-clamp-2 text-slate-700"
                        >
                          <strong class="font-medium">A:</strong>
                          {{ smartTruncate(session.assessment, 100) }}
                        </p>
                        <p v-if="session.plan" class="line-clamp-2 text-slate-700">
                          <strong class="font-medium">P:</strong>
                          {{ smartTruncate(session.plan, 100) }}
                        </p>
                      </div>
                    </div>
                  </div>
                </template>
              </SessionCard>
            </TransitionGroup>
          </div>
        </div>
      </div>

      <!-- Appointments without sessions (shown after all year groups) -->
      <div
        v-if="appointments.length > 0"
        class="space-y-3 border-t border-slate-200 pt-4"
      >
        <h3 class="text-sm font-semibold text-slate-700">
          Appointments Without Sessions
        </h3>
        <TransitionGroup name="session-list" tag="div" class="space-y-3">
          <div
            v-for="appt in appointments"
            :key="`appointment-${appt.id}`"
            class="rounded-lg border border-slate-200 bg-slate-50 p-3.5 transition-colors hover:border-slate-300 hover:bg-slate-100"
          >
            <div class="flex items-start gap-3">
              <!-- Icon -->
              <div class="flex-shrink-0">
                <div
                  class="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100"
                >
                  <svg
                    class="h-5 w-5 text-slate-600"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                    />
                  </svg>
                </div>
              </div>

              <!-- Content -->
              <div class="min-w-0 flex-1">
                <h4 class="text-sm font-medium text-slate-900">
                  {{ formatDate(appt.scheduled_start) }}
                </h4>
                <p class="mt-1 text-sm text-slate-600">
                  {{ getDurationMinutes(appt.scheduled_start, appt.scheduled_end) }}
                  minutes •
                  {{ appt.service_name || 'Appointment' }}
                </p>
                <p v-if="appt.notes" class="mt-1 line-clamp-1 text-sm text-slate-500">
                  {{ smartTruncate(appt.notes, 100) }}
                </p>

                <!-- Action Button -->
                <button
                  @click="createSession(appt.id)"
                  class="mt-2 text-sm font-medium text-blue-600 hover:text-blue-800"
                >
                  Create Session Note →
                </button>
              </div>
            </div>
          </div>
        </TransitionGroup>
      </div>
    </div>

    <!-- Load More Button -->
    <div v-if="hasMoreSessions && !loading && !error" class="mt-6">
      <button
        type="button"
        @click="loadMoreSessions"
        :disabled="loadingMore"
        class="w-full rounded-lg border-2 border-dashed border-slate-300 bg-white px-4 py-3 text-sm font-medium text-slate-700 transition-colors hover:border-blue-400 hover:bg-blue-50 hover:text-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
      >
        <span v-if="!loadingMore" class="flex items-center justify-center gap-2">
          <svg class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M19 9l-7 7-7-7"
            />
          </svg>
          Load More Sessions ({{ remainingCount }} older)
        </span>
        <span v-else class="flex items-center justify-center gap-2">
          <svg class="h-5 w-5 animate-spin" fill="none" viewBox="0 0 24 24">
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
          Loading...
        </span>
      </button>
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
                class="flex-1 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
              >
                Cancel
              </button>
              <button
                type="button"
                @click="jumpToMonth(selectedMonth)"
                :disabled="!selectedMonth"
                class="flex-1 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:bg-gray-300"
              >
                Jump
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <!-- Attachment Preview Modal -->
    <ImagePreviewModal
      v-if="previewSessionId && sessionAttachments.length > 0"
      :open="showAttachmentPreview"
      :attachments="sessionAttachments.filter((a) => isImageType(a.file_type))"
      :current-index="previewImageIndex"
      :session-id="previewSessionId"
      @close="showAttachmentPreview = false"
      @download="handleDownloadFromPreview"
      @update:current-index="updatePreviewIndex"
    />
  </div>
</template>

<style scoped>
/* Line clamp utility for text truncation */
.line-clamp-1 {
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 1;
}

.line-clamp-2 {
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

/* Session card deletion animation */
.session-list-leave-active {
  transition: all 0.3s ease-in-out;
}

.session-list-leave-to {
  opacity: 0;
  transform: translateX(20px);
  max-height: 0;
  margin-bottom: 0;
  padding-top: 0;
  padding-bottom: 0;
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
