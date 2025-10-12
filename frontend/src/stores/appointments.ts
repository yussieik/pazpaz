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

  const hasAppointments = computed(() => appointments.value.length > 0)

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

      if (startDate && endDate) {
        loadedRange.value = {
          startDate: new Date(startDate),
          endDate: new Date(endDate),
        }
      }
    } catch (err: unknown) {
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
   * Delete an appointment with optional reason and session note handling
   * @param appointmentId - The ID of the appointment to delete
   * @param options - Optional deletion options
   * @param options.reason - Optional reason for appointment deletion (for audit trail)
   * @param options.session_note_action - What to do with session notes ('delete' | 'keep')
   * @param options.deletion_reason - Optional reason for session note deletion
   */
  async function deleteAppointment(
    appointmentId: string,
    options?: {
      reason?: string
      session_note_action?: 'delete' | 'keep'
      deletion_reason?: string
    }
  ) {
    loading.value = true
    error.value = null

    try {
      const payload: {
        reason?: string
        session_note_action?: 'delete' | 'keep'
        deletion_reason?: string
      } = {}

      if (options?.reason) payload.reason = options.reason
      if (options?.session_note_action)
        payload.session_note_action = options.session_note_action
      if (options?.deletion_reason) payload.deletion_reason = options.deletion_reason

      await apiClient.delete(`/appointments/${appointmentId}`, {
        data: Object.keys(payload).length > 0 ? payload : undefined,
      })

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
   * Update appointment status only
   * Used for marking appointments as completed, no-show, etc.
   */
  async function updateAppointmentStatus(appointmentId: string, newStatus: string) {
    const appointment = appointments.value.find((a) => a.id === appointmentId)
    if (!appointment) {
      throw new Error('Appointment not found')
    }

    const oldStatus = appointment.status

    try {
      appointment.status = newStatus as AppointmentListItem['status']

      const response = await apiClient.put<AppointmentListItem>(
        `/appointments/${appointmentId}`,
        {
          status: newStatus,
        }
      )

      const index = appointments.value.findIndex((a) => a.id === appointmentId)
      if (index !== -1) {
        appointments.value[index] = response.data
      }

      await fetchAppointments()
    } catch (err) {
      appointment.status = oldStatus

      let errorMessage = 'Failed to update appointment status'
      if (err && typeof err === 'object') {
        if ('response' in err) {
          const axiosError = err as {
            response?: { data?: { detail?: string } }
          }
          errorMessage = axiosError.response?.data?.detail || errorMessage
        } else if ('message' in err) {
          errorMessage = (err as Error).message
        }
      }

      console.error('Error updating appointment status:', err)
      throw new Error(errorMessage)
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
    if (!loadedRange.value) {
      await fetchAppointments(visibleStart.toISOString(), visibleEnd.toISOString())
      return appointments.value
    }

    const isFullyCovered =
      visibleStart >= loadedRange.value.startDate &&
      visibleEnd <= loadedRange.value.endDate

    if (!isFullyCovered) {
      await fetchAppointments(visibleStart.toISOString(), visibleEnd.toISOString())
      return appointments.value
    }

    return appointments.value
  }

  return {
    appointments,
    loading,
    error,
    total,
    loadedRange,
    hasAppointments,
    fetchAppointments,
    ensureAppointmentsLoaded,
    createAppointment,
    updateAppointment,
    updateAppointmentStatus,
    deleteAppointment,
    clearAppointments,
  }
})
