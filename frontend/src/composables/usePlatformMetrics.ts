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
   * GET /api/v1/platform-admin/activity?limit=50
   *
   * Error responses:
   * - 401: Not authenticated
   * - 403: Not platform admin
   * - 422: Invalid limit parameter
   */
  async function fetchActivity(limit = 50): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await apiClient.get<{
        activities: Array<{
          type: string
          timestamp: string
          description: string
          metadata?: Record<string, unknown>
        }>
      }>('/platform-admin/activity', {
        params: { limit },
      })

      // Transform API response to Activity format
      activity.value = response.data.activities.map((item, index) => ({
        id: String(index + 1),
        type: item.type,
        timestamp: formatTimestamp(item.timestamp),
        description: item.description,
        metadata: item.metadata,
      }))
    } catch (err) {
      const axiosError = err as AxiosError<{ detail?: string }>
      error.value = axiosError.response?.data?.detail || 'Failed to load activity'
      console.error('Failed to fetch activity:', err)
    } finally {
      loading.value = false
    }
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

    // Methods
    fetchMetrics,
    fetchActivity,
  }
}
