import { ref, type Ref } from 'vue'
import apiClient from '@/api/client'
import type { Activity } from '@/components/platform-admin/ActivityItem.vue'
import type { AxiosError } from 'axios'

export interface PlatformMetrics {
  totalWorkspaces: number
  activeUsers: number
  pendingInvitations: number
  blacklistedUsers: number
}

export interface ActivityResponse {
  activities: Array<{
    type: string
    timestamp: string
    description: string
    metadata?: Record<string, unknown>
  }>
  total_count: number
  has_more: boolean
  displayed_count: number
}

/**
 * Composable for platform metrics and activity tracking
 *
 * Provides:
 * - GET /api/v1/platform-admin/metrics - Platform-wide metrics
 * - GET /api/v1/platform-admin/activity - Recent platform activity
 *
 * @returns Platform metrics state and methods
 */
export function usePlatformMetrics() {
  const metrics: Ref<PlatformMetrics> = ref({
    totalWorkspaces: 0,
    activeUsers: 0,
    pendingInvitations: 0,
    blacklistedUsers: 0,
  })

  const activity: Ref<Activity[]> = ref([])

  const loading = ref(false)
  const error = ref<string | null>(null)

  // Pagination state
  const totalCount = ref(0)
  const hasMore = ref(false)
  const displayedCount = ref(0)
  const offset = ref(0)
  const limit = 20 // Default page size

  /**
   * Fetch platform metrics from backend
   *
   * GET /api/v1/platform-admin/metrics
   *
   * Error responses:
   * - 401: Not authenticated
   * - 403: Not platform admin
   */
  async function fetchMetrics(): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await apiClient.get<{
        total_workspaces: number
        active_users: number
        pending_invitations: number
        blacklisted_users: number
      }>('/platform-admin/metrics')

      metrics.value = {
        totalWorkspaces: response.data.total_workspaces,
        activeUsers: response.data.active_users,
        pendingInvitations: response.data.pending_invitations,
        blacklistedUsers: response.data.blacklisted_users,
      }
    } catch (err) {
      const axiosError = err as AxiosError<{ detail?: string }>
      error.value = axiosError.response?.data?.detail || 'Failed to load metrics'
      console.error('Failed to fetch metrics:', err)
    } finally {
      loading.value = false
    }
  }

  /**
   * Fetch recent platform activity from backend
   *
   * GET /api/v1/platform-admin/activity?limit=20&offset=0
   *
   * Supports pagination with offset-based loading.
   * Default limit is 20 events per page.
   * 90-day retention filter applied automatically by backend.
   *
   * Error responses:
   * - 401: Not authenticated
   * - 403: Not platform admin
   * - 422: Invalid limit/offset parameters
   *
   * @param reset - If true, resets pagination and replaces activities. If false, appends to existing list.
   */
  async function fetchActivity(reset = true): Promise<void> {
    loading.value = true
    error.value = null

    try {
      // Reset offset if starting fresh
      if (reset) {
        offset.value = 0
      }

      const response = await apiClient.get<ActivityResponse>('/platform-admin/activity', {
        params: {
          limit,
          offset: offset.value,
        },
      })

      // Transform API response to Activity format
      const newActivities = response.data.activities.map((item, index) => ({
        id: `${offset.value + index + 1}`,
        type: item.type,
        timestamp: formatTimestamp(item.timestamp),
        description: item.description,
        metadata: item.metadata,
      }))

      // Replace or append activities based on reset flag
      if (reset) {
        activity.value = newActivities
      } else {
        activity.value = [...activity.value, ...newActivities]
      }

      // Update pagination metadata
      totalCount.value = response.data.total_count
      hasMore.value = response.data.has_more
      displayedCount.value = activity.value.length
    } catch (err) {
      const axiosError = err as AxiosError<{ detail?: string }>
      error.value = axiosError.response?.data?.detail || 'Failed to load activity'
      console.error('Failed to fetch activity:', err)
    } finally {
      loading.value = false
    }
  }

  /**
   * Load more activities (next page)
   *
   * Increments offset by limit and appends next batch of activities.
   * Updates displayedCount and hasMore based on backend response.
   */
  async function loadMore(): Promise<void> {
    if (!hasMore.value || loading.value) return

    offset.value += limit
    await fetchActivity(false) // false = append mode
  }

  /**
   * Format ISO timestamp to relative time (e.g., "2 minutes ago")
   */
  function formatTimestamp(isoTimestamp: string): string {
    const now = new Date()
    const timestamp = new Date(isoTimestamp)
    const diffMs = now.getTime() - timestamp.getTime()
    const diffSeconds = Math.floor(diffMs / 1000)
    const diffMinutes = Math.floor(diffSeconds / 60)
    const diffHours = Math.floor(diffMinutes / 60)
    const diffDays = Math.floor(diffHours / 24)

    if (diffSeconds < 60) {
      return 'just now'
    } else if (diffMinutes < 60) {
      return `${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''} ago`
    } else if (diffHours < 24) {
      return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`
    } else if (diffDays < 30) {
      return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`
    } else {
      return timestamp.toLocaleDateString()
    }
  }

  return {
    // State
    metrics,
    activity,
    loading,
    error,

    // Pagination state
    totalCount,
    hasMore,
    displayedCount,

    // Methods
    fetchMetrics,
    fetchActivity,
    loadMore,
  }
}
