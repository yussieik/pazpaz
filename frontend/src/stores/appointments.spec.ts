import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAppointmentsStore } from './appointments'
import apiClient from '@/api/client'

// Mock the API client
vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

const mockAppointments = [
  {
    id: '1',
    title: 'Morning Session',
    start_time: '2025-09-30T09:00:00Z',
    end_time: '2025-09-30T10:00:00Z',
    client_id: 'client-1',
    status: 'scheduled',
    notes: null,
    created_at: '2025-09-29T10:00:00Z',
    updated_at: '2025-09-29T10:00:00Z',
  },
  {
    id: '2',
    title: 'Afternoon Session',
    start_time: '2025-09-30T14:00:00Z',
    end_time: '2025-09-30T15:00:00Z',
    client_id: 'client-2',
    status: 'scheduled',
    notes: 'Follow-up session',
    created_at: '2025-09-29T11:00:00Z',
    updated_at: '2025-09-29T11:00:00Z',
  },
]

describe('Appointments Store', () => {
  let store: ReturnType<typeof useAppointmentsStore>

  beforeEach(() => {
    // Create a fresh pinia instance for each test
    setActivePinia(createPinia())
    store = useAppointmentsStore()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('Initial State', () => {
    it('should have empty appointments array', () => {
      expect(store.appointments).toEqual([])
    })

    it('should have loading set to false', () => {
      expect(store.loading).toBe(false)
    })

    it('should have null error', () => {
      expect(store.error).toBeNull()
    })

    it('should have total set to 0', () => {
      expect(store.total).toBe(0)
    })

    it('should have hasAppointments computed as false', () => {
      expect(store.hasAppointments).toBe(false)
    })
  })

  describe('fetchAppointments', () => {
    it('should fetch appointments successfully', async () => {
      const mockResponse = {
        data: {
          items: mockAppointments,
          total: 2,
          page: 1,
          page_size: 50,
        },
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse)

      await store.fetchAppointments()

      expect(apiClient.get).toHaveBeenCalledWith('/appointments', {
        params: {
          page: 1,
          page_size: 50,
        },
      })

      expect(store.appointments).toEqual(mockAppointments)
      expect(store.total).toBe(2)
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('should fetch appointments with date range filtering', async () => {
      const mockResponse = {
        data: {
          items: [mockAppointments[0]],
          total: 1,
          page: 1,
          page_size: 50,
        },
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse)

      await store.fetchAppointments('2025-09-30', '2025-09-30')

      expect(apiClient.get).toHaveBeenCalledWith('/appointments', {
        params: {
          page: 1,
          page_size: 50,
          start_date: '2025-09-30',
          end_date: '2025-09-30',
        },
      })

      expect(store.appointments).toEqual([mockAppointments[0]])
      expect(store.total).toBe(1)
    })

    it('should fetch appointments with custom pagination', async () => {
      const mockResponse = {
        data: {
          items: mockAppointments,
          total: 100,
          page: 2,
          page_size: 25,
        },
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse)

      await store.fetchAppointments(undefined, undefined, 2, 25)

      expect(apiClient.get).toHaveBeenCalledWith('/appointments', {
        params: {
          page: 2,
          page_size: 25,
        },
      })

      expect(store.total).toBe(100)
    })

    it('should set loading state during fetch', async () => {
      const mockResponse = {
        data: {
          items: mockAppointments,
          total: 2,
          page: 1,
          page_size: 50,
        },
      }

      vi.mocked(apiClient.get).mockImplementation(
        () =>
          new Promise((resolve) => {
            // Check loading state while promise is pending
            expect(store.loading).toBe(true)
            setTimeout(() => resolve(mockResponse), 10)
          })
      )

      await store.fetchAppointments()

      expect(store.loading).toBe(false)
    })

    it('should handle fetch errors', async () => {
      const errorMessage = 'Network error'
      vi.mocked(apiClient.get).mockRejectedValueOnce(new Error(errorMessage))

      await store.fetchAppointments()

      expect(store.error).toBe(errorMessage)
      expect(store.loading).toBe(false)
      expect(store.appointments).toEqual([])
    })

    it('should handle non-Error exceptions', async () => {
      vi.mocked(apiClient.get).mockRejectedValueOnce('String error')

      await store.fetchAppointments()

      expect(store.error).toBe('Failed to fetch appointments')
      expect(store.loading).toBe(false)
    })
  })

  describe('createAppointment', () => {
    const newAppointment = {
      title: 'New Session',
      start_time: '2025-10-01T10:00:00Z',
      end_time: '2025-10-01T11:00:00Z',
      client_id: 'client-3',
      status: 'scheduled' as const,
    }

    it('should create appointment successfully', async () => {
      const createdAppointment = {
        id: '3',
        ...newAppointment,
        notes: null,
        created_at: '2025-09-30T10:00:00Z',
        updated_at: '2025-09-30T10:00:00Z',
      }

      vi.mocked(apiClient.post).mockResolvedValueOnce({
        data: createdAppointment,
      })

      const result = await store.createAppointment(newAppointment)

      expect(apiClient.post).toHaveBeenCalledWith('/appointments', newAppointment)
      expect(result).toEqual(createdAppointment)
      expect(store.appointments).toContainEqual(createdAppointment)
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('should add new appointment to local state (optimistic update)', async () => {
      const createdAppointment = {
        id: '3',
        ...newAppointment,
        notes: null,
        created_at: '2025-09-30T10:00:00Z',
        updated_at: '2025-09-30T10:00:00Z',
      }

      // Pre-populate with existing appointments
      store.appointments = [...mockAppointments]

      vi.mocked(apiClient.post).mockResolvedValueOnce({
        data: createdAppointment,
      })

      await store.createAppointment(newAppointment)

      expect(store.appointments.length).toBe(3)
      expect(store.appointments[2]).toEqual(createdAppointment)
    })

    it('should handle creation errors', async () => {
      const errorMessage = 'Validation failed'
      vi.mocked(apiClient.post).mockRejectedValueOnce(new Error(errorMessage))

      await expect(store.createAppointment(newAppointment)).rejects.toThrow()

      expect(store.error).toBe(errorMessage)
      expect(store.loading).toBe(false)
      expect(store.appointments).toEqual([])
    })

    it('should set loading state during creation', async () => {
      const createdAppointment = {
        id: '3',
        ...newAppointment,
        notes: null,
        created_at: '2025-09-30T10:00:00Z',
        updated_at: '2025-09-30T10:00:00Z',
      }

      vi.mocked(apiClient.post).mockImplementation(
        () =>
          new Promise((resolve) => {
            expect(store.loading).toBe(true)
            setTimeout(() => resolve({ data: createdAppointment }), 10)
          })
      )

      await store.createAppointment(newAppointment)

      expect(store.loading).toBe(false)
    })
  })

  describe('updateAppointment', () => {
    const updates = {
      title: 'Updated Session',
      notes: 'Updated notes',
    }

    beforeEach(() => {
      // Pre-populate store with appointments
      store.appointments = [...mockAppointments]
    })

    it('should update appointment successfully', async () => {
      const updatedAppointment = {
        ...mockAppointments[0],
        ...updates,
        updated_at: '2025-09-30T12:00:00Z',
      }

      vi.mocked(apiClient.patch).mockResolvedValueOnce({
        data: updatedAppointment,
      })

      const result = await store.updateAppointment('1', updates)

      expect(apiClient.patch).toHaveBeenCalledWith('/appointments/1', updates)
      expect(result).toEqual(updatedAppointment)
      expect(store.appointments[0]).toEqual(updatedAppointment)
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('should update local state correctly', async () => {
      const updatedAppointment = {
        ...mockAppointments[1],
        ...updates,
        updated_at: '2025-09-30T12:00:00Z',
      }

      vi.mocked(apiClient.patch).mockResolvedValueOnce({
        data: updatedAppointment,
      })

      await store.updateAppointment('2', updates)

      expect(store.appointments[1].title).toBe('Updated Session')
      expect(store.appointments[1].notes).toBe('Updated notes')
      // First appointment should remain unchanged
      expect(store.appointments[0]).toEqual(mockAppointments[0])
    })

    it('should handle non-existent appointment ID gracefully', async () => {
      const updatedAppointment = {
        ...mockAppointments[0],
        ...updates,
      }

      vi.mocked(apiClient.patch).mockResolvedValueOnce({
        data: updatedAppointment,
      })

      await store.updateAppointment('non-existent-id', updates)

      // Should complete without error, but not modify local state
      expect(store.appointments).toEqual(mockAppointments)
    })

    it('should handle update errors', async () => {
      const errorMessage = 'Update failed'
      vi.mocked(apiClient.patch).mockRejectedValueOnce(new Error(errorMessage))

      await expect(store.updateAppointment('1', updates)).rejects.toThrow()

      expect(store.error).toBe(errorMessage)
      expect(store.loading).toBe(false)
      // Original data should remain unchanged on error
      expect(store.appointments).toEqual(mockAppointments)
    })
  })

  describe('deleteAppointment', () => {
    beforeEach(() => {
      // Pre-populate store with appointments
      store.appointments = [...mockAppointments]
    })

    it('should delete appointment successfully', async () => {
      vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: null })

      await store.deleteAppointment('1')

      expect(apiClient.delete).toHaveBeenCalledWith('/appointments/1')
      expect(store.appointments.length).toBe(1)
      expect(store.appointments[0].id).toBe('2')
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('should remove appointment from local state', async () => {
      vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: null })

      const initialLength = store.appointments.length

      await store.deleteAppointment('2')

      expect(store.appointments.length).toBe(initialLength - 1)
      expect(store.appointments.find((a) => a.id === '2')).toBeUndefined()
    })

    it('should handle deletion errors', async () => {
      const errorMessage = 'Delete failed'
      vi.mocked(apiClient.delete).mockRejectedValueOnce(new Error(errorMessage))

      await expect(store.deleteAppointment('1')).rejects.toThrow()

      expect(store.error).toBe(errorMessage)
      expect(store.loading).toBe(false)
      // Original data should remain unchanged on error
      expect(store.appointments).toEqual(mockAppointments)
    })

    it('should handle non-existent appointment ID', async () => {
      vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: null })

      await store.deleteAppointment('non-existent-id')

      // Should complete without error, appointments unchanged
      expect(store.appointments).toEqual(mockAppointments)
    })
  })

  describe('clearAppointments', () => {
    it('should clear appointments and reset total', () => {
      // Set some data
      store.appointments = [...mockAppointments]
      store.total = 2

      store.clearAppointments()

      expect(store.appointments).toEqual([])
      expect(store.total).toBe(0)
    })
  })

  describe('Computed Properties', () => {
    it('hasAppointments should return true when appointments exist', () => {
      store.appointments = [...mockAppointments]
      expect(store.hasAppointments).toBe(true)
    })

    it('hasAppointments should return false when no appointments', () => {
      store.appointments = []
      expect(store.hasAppointments).toBe(false)
    })
  })

  describe('Error Handling', () => {
    it('should clear previous errors on new request', async () => {
      // Set an error
      store.error = 'Previous error'

      const mockResponse = {
        data: {
          items: mockAppointments,
          total: 2,
          page: 1,
          page_size: 50,
        },
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse)

      await store.fetchAppointments()

      expect(store.error).toBeNull()
    })
  })
})
