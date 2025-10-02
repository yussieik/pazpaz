import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAppointmentsStore } from '@/stores/appointments'
import apiClient from '@/api/client'
import type { AxiosError } from 'axios'

/**
 * Integration Tests: Frontend-Backend Connectivity
 *
 * These tests validate the complete flow from store actions through
 * the API client to mocked backend responses, ensuring type safety
 * and correct data flow.
 */

vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('Appointments Integration Tests', () => {
  let store: ReturnType<typeof useAppointmentsStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useAppointmentsStore()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('Fetch Appointments Flow', () => {
    it('should complete full fetch cycle with backend response', async () => {
      const mockBackendResponse = {
        data: {
          items: [
            {
              id: '123e4567-e89b-12d3-a456-426614174000',
              title: 'Physiotherapy Session',
              start_time: '2025-10-01T10:00:00Z',
              end_time: '2025-10-01T11:00:00Z',
              client_id: '123e4567-e89b-12d3-a456-426614174001',
              status: 'scheduled',
              notes: null,
              created_at: '2025-09-30T08:00:00Z',
              updated_at: '2025-09-30T08:00:00Z',
            },
          ],
          total: 1,
          page: 1,
          page_size: 50,
        },
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(mockBackendResponse)

      // Initial state
      expect(store.loading).toBe(false)
      expect(store.appointments.length).toBe(0)

      // Execute
      const fetchPromise = store.fetchAppointments('2025-10-01', '2025-10-07')

      // During loading
      expect(store.loading).toBe(true)

      await fetchPromise

      // After completion
      expect(store.loading).toBe(false)
      expect(store.appointments.length).toBe(1)
      expect(store.appointments[0].title).toBe('Physiotherapy Session')
      expect(store.total).toBe(1)
      expect(store.error).toBeNull()
    })

    it('should handle backend pagination correctly', async () => {
      const page1Response = {
        data: {
          items: Array.from({ length: 25 }, (_, i) => ({
            id: `id-${i}`,
            title: `Appointment ${i}`,
            start_time: '2025-10-01T10:00:00Z',
            end_time: '2025-10-01T11:00:00Z',
            client_id: 'client-1',
            status: 'scheduled',
            notes: null,
            created_at: '2025-09-30T08:00:00Z',
            updated_at: '2025-09-30T08:00:00Z',
          })),
          total: 100,
          page: 1,
          page_size: 25,
        },
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(page1Response)

      await store.fetchAppointments(undefined, undefined, 1, 25)

      expect(apiClient.get).toHaveBeenCalledWith('/appointments', {
        params: {
          page: 1,
          page_size: 25,
        },
      })

      expect(store.appointments.length).toBe(25)
      expect(store.total).toBe(100)
    })

    it('should handle empty results from backend', async () => {
      const emptyResponse = {
        data: {
          items: [],
          total: 0,
          page: 1,
          page_size: 50,
        },
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(emptyResponse)

      await store.fetchAppointments()

      expect(store.appointments.length).toBe(0)
      expect(store.total).toBe(0)
      expect(store.hasAppointments).toBe(false)
    })

    it('should handle network errors gracefully', async () => {
      const networkError = new Error('Network Error')
      vi.mocked(apiClient.get).mockRejectedValueOnce(networkError)

      await store.fetchAppointments()

      expect(store.error).toBe('Network Error')
      expect(store.appointments.length).toBe(0)
      expect(store.loading).toBe(false)
    })

    it('should handle 401 authentication errors', async () => {
      const authError = {
        response: {
          status: 401,
          data: { detail: 'Authentication required' },
        },
        message: 'Request failed with status code 401',
      } as AxiosError

      vi.mocked(apiClient.get).mockRejectedValueOnce(authError)

      await store.fetchAppointments()

      expect(store.error).toBe('Authentication required. Please log in.')
      expect(store.loading).toBe(false)
    })

    it('should handle 422 validation errors', async () => {
      const validationError = {
        response: {
          status: 422,
          data: {
            detail: [
              {
                loc: ['query', 'start_date'],
                msg: 'Invalid date format',
                type: 'value_error',
              },
            ],
          },
        },
        message: 'Request failed with status code 422',
      } as AxiosError

      vi.mocked(apiClient.get).mockRejectedValueOnce(validationError)

      await store.fetchAppointments('invalid-date', '2025-10-07')

      // The store assigns validation error detail array directly
      expect(store.error).toBeDefined()
      expect(Array.isArray(store.error)).toBe(true)
      expect((store.error as Array<{ msg: string }>)[0].msg).toBe('Invalid date format')
    })
  })

  describe('Create Appointment Flow', () => {
    it('should complete full creation cycle', async () => {
      const newAppointment = {
        title: 'New Massage Session',
        start_time: '2025-10-05T14:00:00Z',
        end_time: '2025-10-05T15:00:00Z',
        client_id: '123e4567-e89b-12d3-a456-426614174002',
        status: 'scheduled' as const,
      }

      const backendResponse = {
        data: {
          id: '123e4567-e89b-12d3-a456-426614174003',
          ...newAppointment,
          notes: null,
          created_at: '2025-10-01T10:00:00Z',
          updated_at: '2025-10-01T10:00:00Z',
        },
      }

      vi.mocked(apiClient.post).mockResolvedValueOnce(backendResponse)

      const result = await store.createAppointment(newAppointment)

      expect(result.id).toBe('123e4567-e89b-12d3-a456-426614174003')
      expect(store.appointments).toContainEqual(backendResponse.data)
      expect(store.error).toBeNull()
    })

    it('should handle validation errors from backend', async () => {
      const invalidAppointment = {
        title: '',
        start_time: '2025-10-05T14:00:00Z',
        end_time: '2025-10-05T13:00:00Z', // End before start
        client_id: 'invalid-uuid',
        status: 'scheduled' as const,
      }

      const validationError = {
        response: {
          status: 422,
          data: {
            detail: [
              {
                loc: ['body', 'title'],
                msg: 'field required',
                type: 'value_error.missing',
              },
              {
                loc: ['body', 'end_time'],
                msg: 'end_time must be after start_time',
                type: 'value_error',
              },
            ],
          },
        },
        message: 'Validation failed',
      } as AxiosError

      vi.mocked(apiClient.post).mockRejectedValueOnce(validationError)

      await expect(store.createAppointment(invalidAppointment)).rejects.toThrow()

      expect(store.error).toBe('Validation failed')
      expect(store.appointments.length).toBe(0)
    })
  })

  describe('Update Appointment Flow', () => {
    beforeEach(async () => {
      // Setup initial state with an appointment
      const initialFetch = {
        data: {
          items: [
            {
              id: 'appointment-1',
              title: 'Original Title',
              start_time: '2025-10-01T10:00:00Z',
              end_time: '2025-10-01T11:00:00Z',
              client_id: 'client-1',
              status: 'scheduled',
              notes: null,
              created_at: '2025-09-30T08:00:00Z',
              updated_at: '2025-09-30T08:00:00Z',
            },
          ],
          total: 1,
          page: 1,
          page_size: 50,
        },
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(initialFetch)
      await store.fetchAppointments()
    })

    it('should complete full update cycle', async () => {
      const updates = {
        title: 'Updated Title',
        notes: 'Updated notes',
      }

      const backendResponse = {
        data: {
          id: 'appointment-1',
          title: 'Updated Title',
          start_time: '2025-10-01T10:00:00Z',
          end_time: '2025-10-01T11:00:00Z',
          client_id: 'client-1',
          status: 'scheduled',
          notes: 'Updated notes',
          created_at: '2025-09-30T08:00:00Z',
          updated_at: '2025-10-01T12:00:00Z',
        },
      }

      vi.mocked(apiClient.put).mockResolvedValueOnce(backendResponse)

      const result = await store.updateAppointment('appointment-1', updates)

      expect(result.title).toBe('Updated Title')
      expect(result.notes).toBe('Updated notes')
      expect(store.appointments[0].title).toBe('Updated Title')
    })

    it('should handle 404 not found errors', async () => {
      const notFoundError = {
        response: {
          status: 404,
          data: { detail: 'Appointment not found' },
        },
        message: 'Not found',
      } as AxiosError

      vi.mocked(apiClient.put).mockRejectedValueOnce(notFoundError)

      await expect(
        store.updateAppointment('non-existent', { title: 'Test' })
      ).rejects.toThrow()

      expect(store.error).toBe('Not found')
    })
  })

  describe('Delete Appointment Flow', () => {
    beforeEach(async () => {
      // Setup initial state with appointments
      const initialFetch = {
        data: {
          items: [
            {
              id: 'appointment-1',
              title: 'To Be Deleted',
              start_time: '2025-10-01T10:00:00Z',
              end_time: '2025-10-01T11:00:00Z',
              client_id: 'client-1',
              status: 'scheduled',
              notes: null,
              created_at: '2025-09-30T08:00:00Z',
              updated_at: '2025-09-30T08:00:00Z',
            },
            {
              id: 'appointment-2',
              title: 'To Be Kept',
              start_time: '2025-10-02T10:00:00Z',
              end_time: '2025-10-02T11:00:00Z',
              client_id: 'client-2',
              status: 'scheduled',
              notes: null,
              created_at: '2025-09-30T09:00:00Z',
              updated_at: '2025-09-30T09:00:00Z',
            },
          ],
          total: 2,
          page: 1,
          page_size: 50,
        },
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(initialFetch)
      await store.fetchAppointments()
    })

    it('should complete full deletion cycle', async () => {
      vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: null })

      expect(store.appointments.length).toBe(2)

      await store.deleteAppointment('appointment-1')

      expect(store.appointments.length).toBe(1)
      expect(store.appointments[0].id).toBe('appointment-2')
      expect(store.error).toBeNull()
    })

    it('should handle deletion errors', async () => {
      const deleteError = {
        response: {
          status: 500,
          data: { detail: 'Internal server error' },
        },
        message: 'Server error',
      } as AxiosError

      vi.mocked(apiClient.delete).mockRejectedValueOnce(deleteError)

      const initialCount = store.appointments.length

      await expect(store.deleteAppointment('appointment-1')).rejects.toThrow()

      expect(store.error).toBe('Server error')
      expect(store.appointments.length).toBe(initialCount) // No change on error
    })
  })

  describe('Type Safety Validation', () => {
    it('should ensure response data matches OpenAPI schema types', async () => {
      const typeSafeResponse = {
        data: {
          items: [
            {
              id: '123e4567-e89b-12d3-a456-426614174000',
              title: 'Type Safe Appointment',
              start_time: '2025-10-01T10:00:00Z',
              end_time: '2025-10-01T11:00:00Z',
              client_id: '123e4567-e89b-12d3-a456-426614174001',
              status: 'scheduled' as const,
              notes: null,
              created_at: '2025-09-30T08:00:00Z',
              updated_at: '2025-09-30T08:00:00Z',
            },
          ],
          total: 1,
          page: 1,
          page_size: 50,
        },
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(typeSafeResponse)

      await store.fetchAppointments()

      const appointment = store.appointments[0]

      // Verify all required fields exist
      expect(appointment).toHaveProperty('id')
      expect(appointment).toHaveProperty('title')
      expect(appointment).toHaveProperty('start_time')
      expect(appointment).toHaveProperty('end_time')
      expect(appointment).toHaveProperty('client_id')
      expect(appointment).toHaveProperty('status')
      expect(appointment).toHaveProperty('created_at')
      expect(appointment).toHaveProperty('updated_at')

      // Verify types
      expect(typeof appointment.id).toBe('string')
      expect(typeof appointment.title).toBe('string')
      expect(typeof appointment.start_time).toBe('string')
      expect(typeof appointment.end_time).toBe('string')
    })
  })

  describe('Performance and Optimization', () => {
    it('should handle large result sets efficiently', async () => {
      const largeResultSet = {
        data: {
          items: Array.from({ length: 100 }, (_, i) => ({
            id: `id-${i}`,
            title: `Appointment ${i}`,
            start_time: '2025-10-01T10:00:00Z',
            end_time: '2025-10-01T11:00:00Z',
            client_id: 'client-1',
            status: 'scheduled',
            notes: null,
            created_at: '2025-09-30T08:00:00Z',
            updated_at: '2025-09-30T08:00:00Z',
          })),
          total: 100,
          page: 1,
          page_size: 100,
        },
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(largeResultSet)

      const startTime = performance.now()
      await store.fetchAppointments()
      const endTime = performance.now()

      expect(store.appointments.length).toBe(100)
      expect(endTime - startTime).toBeLessThan(100) // Should complete in under 100ms
    })
  })
})
