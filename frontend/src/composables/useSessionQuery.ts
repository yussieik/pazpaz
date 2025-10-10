import { ref } from 'vue'
import apiClient from '@/api/client'
import type { SessionResponse } from '@/types/sessions'

/**
 * Composable for querying sessions by appointment ID
 *
 * Provides a reusable way to fetch session data linked to appointments
 * Used by DeleteAppointmentModal, AppointmentDetailsModal, and other components
 *
 * @returns {Object} - Session query utilities
 */
export function useSessionQuery() {
  const loading = ref(false)
  const session = ref<SessionResponse | null>(null)
  const error = ref<Error | null>(null)

  /**
   * Fetch session by appointment ID
   * @param appointmentId - The appointment ID to query
   * @returns Promise<SessionResponse | null>
   */
  async function fetchByAppointmentId(appointmentId: string): Promise<SessionResponse | null> {
    loading.value = true
    error.value = null
    session.value = null

    try {
      const response = await apiClient.get<{ items: SessionResponse[] }>(
        `/sessions?appointment_id=${appointmentId}`
      )

      if (response.data?.items && response.data.items.length > 0) {
        session.value = response.data.items[0]
        return session.value
      }

      return null
    } catch (err) {
      error.value = err instanceof Error ? err : new Error('Failed to fetch session')
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
  }

  return {
    loading,
    session,
    error,
    fetchByAppointmentId,
    reset,
  }
}
