import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '@/api/client'
import type { paths } from '@/api/schema'

/**
 * Appointments Store
 *
 * Manages appointment state and API interactions.
 * Provides methods for CRUD operations on appointments.
 */

// Type definitions from OpenAPI schema
type AppointmentResponse =
  paths['/api/v1/appointments']['get']['responses']['200']['content']['application/json']
type AppointmentListItem = AppointmentResponse['items'][0]
type AppointmentCreate =
  paths['/api/v1/appointments']['post']['requestBody']['content']['application/json']
type AppointmentUpdate =
  paths['/api/v1/appointments/{appointment_id}']['put']['requestBody']['content']['application/json']

export const useAppointmentsStore = defineStore('appointments', () => {
  // State
  const appointments = ref<AppointmentListItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const total = ref(0)

  /**
   * Track the currently loaded date range for smart fetching
   * This enables sliding window optimization:
   * - Only fetch if date is outside loaded range
   * - Prevents unnecessary API calls when navigating within loaded range
   */
  const loadedRange = ref<{ startDate: Date; endDate: Date } | null>(null)

  // Getters
  const hasAppointments = computed(() => appointments.value.length > 0)

  // Actions

  /**
   * Fetch appointments with optional date range filtering
   * Updates the loadedRange to enable smart fetching
   */
  async function fetchAppointments(
    startDate?: string,
    endDate?: string,
    page: number = 1,
    pageSize: number = 50
  ) {
    loading.value = true
    error.value = null

    try {
      const params: Record<string, string | number> = {
        page,
        page_size: pageSize,
      }

      if (startDate) params.start_date = startDate
      if (endDate) params.end_date = endDate

      const response = await apiClient.get<AppointmentResponse>('/appointments', {
        params,
      })

      appointments.value = response.data.items
      total.value = response.data.total

      // Track the loaded range for smart fetching
      if (startDate && endDate) {
        loadedRange.value = {
          startDate: new Date(startDate),
          endDate: new Date(endDate),
        }
      }
    } catch (err: unknown) {
      // Handle Axios errors with detailed error messages
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosError = err as {
          response?: { status: number; data?: { detail?: string } }
        }
        if (axiosError.response?.status === 401) {
          error.value = 'Authentication required. Please log in.'
        } else if (axiosError.response?.data?.detail) {
          error.value = axiosError.response.data.detail
        } else if ('message' in err) {
          error.value = String((err as { message: unknown }).message)
        } else {
          error.value = 'Failed to fetch appointments'
        }
      } else if (err && typeof err === 'object' && 'message' in err) {
        error.value = String((err as { message: unknown }).message)
      } else {
        error.value = 'Failed to fetch appointments'
      }
      console.error('Error fetching appointments:', err)
    } finally {
      loading.value = false
    }
  }

  /**
   * Create a new appointment
   */
  async function createAppointment(appointmentData: AppointmentCreate) {
    loading.value = true
    error.value = null

    try {
      const response = await apiClient.post<AppointmentListItem>(
        '/appointments',
        appointmentData
      )

      // Add new appointment to local state (optimistic update)
      appointments.value.push(response.data)

      return response.data
    } catch (err) {
      if (err && typeof err === 'object' && 'message' in err) {
        error.value = (err as Error).message
      } else {
        error.value = 'Failed to create appointment'
      }
      console.error('Error creating appointment:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Update an existing appointment
   */
  async function updateAppointment(
    appointmentId: string,
    updates: Partial<AppointmentUpdate>,
    options?: { allowConflict?: boolean }
  ) {
    loading.value = true
    error.value = null

    try {
      const params: Record<string, string | boolean> = {}
      if (options?.allowConflict) {
        params.allow_conflict = true
      }

      const response = await apiClient.put<AppointmentListItem>(
        `/appointments/${appointmentId}`,
        updates,
        { params }
      )

      // Update local state
      const index = appointments.value.findIndex((a) => a.id === appointmentId)
      if (index !== -1) {
        appointments.value[index] = response.data
      }

      return response.data
    } catch (err) {
      if (err && typeof err === 'object' && 'message' in err) {
        error.value = (err as Error).message
      } else {
        error.value = 'Failed to update appointment'
      }
      console.error('Error updating appointment:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Delete an appointment
   */
  async function deleteAppointment(appointmentId: string) {
    loading.value = true
    error.value = null

    try {
      await apiClient.delete(`/appointments/${appointmentId}`)

      // Remove from local state
      appointments.value = appointments.value.filter((a) => a.id !== appointmentId)
    } catch (err) {
      if (err && typeof err === 'object' && 'message' in err) {
        error.value = (err as Error).message
      } else {
        error.value = 'Failed to delete appointment'
      }
      console.error('Error deleting appointment:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Clear appointments from state
   */
  function clearAppointments() {
    appointments.value = []
    total.value = 0
    loadedRange.value = null
  }

  /**
   * Smart fetch - only fetches if visible range is not fully covered by loaded data
   *
   * This prevents unnecessary API calls when:
   * - Navigating within already-loaded date ranges
   * - Switching between calendar views that show the same data
   * - Auto-refreshing on focus/mount
   *
   * @param visibleStart - Start of the visible date range
   * @param visibleEnd - End of the visible date range
   * @returns Promise that resolves when appointments are available
   */
  async function ensureAppointmentsLoaded(
    visibleStart: Date,
    visibleEnd: Date
  ): Promise<AppointmentListItem[]> {
    // If no data loaded yet, fetch the visible range
    if (!loadedRange.value) {
      await fetchAppointments(visibleStart.toISOString(), visibleEnd.toISOString())
      return appointments.value
    }

    // Check if visible range is fully covered by loaded range
    const isFullyCovered =
      visibleStart >= loadedRange.value.startDate && visibleEnd <= loadedRange.value.endDate

    // If visible range is not fully covered, refetch
    if (!isFullyCovered) {
      await fetchAppointments(visibleStart.toISOString(), visibleEnd.toISOString())
      return appointments.value
    }

    // Data already loaded and covers visible range, no fetch needed
    return appointments.value
  }

  return {
    // State
    appointments,
    loading,
    error,
    total,
    loadedRange,
    // Getters
    hasAppointments,
    // Actions
    fetchAppointments,
    ensureAppointmentsLoaded,
    createAppointment,
    updateAppointment,
    deleteAppointment,
    clearAppointments,
  }
})
