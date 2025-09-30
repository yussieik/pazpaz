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

export const useAppointmentsStore = defineStore('appointments', () => {
  // State
  const appointments = ref<AppointmentListItem[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const total = ref(0)

  // Getters
  const hasAppointments = computed(() => appointments.value.length > 0)

  // Actions

  /**
   * Fetch appointments with optional date range filtering
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
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch appointments'
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
      error.value = err instanceof Error ? err.message : 'Failed to create appointment'
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
    updates: Partial<AppointmentCreate>
  ) {
    loading.value = true
    error.value = null

    try {
      const response = await apiClient.patch<AppointmentListItem>(
        `/appointments/${appointmentId}`,
        updates
      )

      // Update local state
      const index = appointments.value.findIndex((a) => a.id === appointmentId)
      if (index !== -1) {
        appointments.value[index] = response.data
      }

      return response.data
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to update appointment'
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
      error.value = err instanceof Error ? err.message : 'Failed to delete appointment'
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
  }

  return {
    // State
    appointments,
    loading,
    error,
    total,
    // Getters
    hasAppointments,
    // Actions
    fetchAppointments,
    createAppointment,
    updateAppointment,
    deleteAppointment,
    clearAppointments,
  }
})
