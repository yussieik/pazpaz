import { ref } from 'vue'
import apiClient from '@/api/client'
import type { AxiosError } from 'axios'
import type { SessionResponse } from '@/types/sessions'

/**
 * Composable for fetching the latest finalized session for a client
 *
 * Used by PreviousSessionPanel to show context from the previous session
 * when creating or editing a new session note.
 *
 * @param startLoading - If true, start in loading state (prevents initial glitch)
 * @returns {Object} - Previous session query utilities
 */
export function usePreviousSession(startLoading = false) {
  const loading = ref(startLoading)
  const session = ref<SessionResponse | null>(null)
  const error = ref<string | null>(null)
  const notFound = ref(false)

  /**
   * Fetch latest finalized session by client ID
   * @param clientId - The client ID to query
   * @returns Promise<SessionResponse | null>
   */
  async function fetchLatestFinalized(
    clientId: string
  ): Promise<SessionResponse | null> {
    loading.value = true
    error.value = null
    session.value = null
    notFound.value = false

    try {
      const response = await apiClient.get<SessionResponse>(
        `/sessions/clients/${clientId}/latest-finalized`
      )

      session.value = response.data
      return session.value
    } catch (err) {
      const axiosError = err as AxiosError<{ detail?: string }>

      if (axiosError.response?.status === 404) {
        // No previous finalized sessions - this is expected for first session
        notFound.value = true
        return null
      } else if (axiosError.response?.status === 403) {
        error.value = 'Client not in workspace'
      } else {
        error.value =
          axiosError.response?.data?.detail || 'Failed to fetch previous session'
      }

      return null
    } finally {
      loading.value = false
    }
  }

  /**
   * Reset state
   */
  function reset() {
    loading.value = false
    session.value = null
    error.value = null
    notFound.value = false
  }

  return {
    loading,
    session,
    error,
    notFound,
    fetchLatestFinalized,
    reset,
  }
}
