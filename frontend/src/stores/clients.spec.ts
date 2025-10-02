import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useClientsStore } from './clients'
import apiClient from '@/api/client'

// Mock the API client
vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

const mockClients = [
  {
    id: 'client-1',
    workspace_id: 'workspace-1',
    first_name: 'John',
    last_name: 'Doe',
    full_name: 'John Doe',
    email: 'john.doe@example.com',
    phone: '+1234567890',
    date_of_birth: '1990-01-15',
    address: '123 Main St',
    emergency_contact_name: 'Jane Doe',
    emergency_contact_phone: '+1234567891',
    medical_history: 'No known allergies',
    notes: 'Prefers morning appointments',
    created_at: '2025-09-01T10:00:00Z',
    updated_at: '2025-09-01T10:00:00Z',
    appointment_count: 5,
    last_appointment: '2025-09-25T14:00:00Z',
    next_appointment: '2025-10-05T10:00:00Z',
  },
  {
    id: 'client-2',
    workspace_id: 'workspace-1',
    first_name: 'Jane',
    last_name: 'Smith',
    full_name: 'Jane Smith',
    email: 'jane.smith@example.com',
    phone: '+1234567892',
    date_of_birth: '1985-05-20',
    address: '456 Oak Ave',
    emergency_contact_name: null,
    emergency_contact_phone: null,
    medical_history: null,
    notes: null,
    created_at: '2025-09-02T11:00:00Z',
    updated_at: '2025-09-02T11:00:00Z',
    appointment_count: 2,
    last_appointment: '2025-09-20T15:00:00Z',
    next_appointment: null,
  },
]

describe('Clients Store', () => {
  let store: ReturnType<typeof useClientsStore>

  beforeEach(() => {
    // Create a fresh pinia instance for each test
    setActivePinia(createPinia())
    store = useClientsStore()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('Initial State', () => {
    it('should have empty clients array', () => {
      expect(store.clients).toEqual([])
    })

    it('should have null currentClient', () => {
      expect(store.currentClient).toBeNull()
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

    it('should have hasClients computed as false', () => {
      expect(store.hasClients).toBe(false)
    })
  })

  describe('fetchClients', () => {
    it('should fetch clients successfully', async () => {
      const mockResponse = {
        data: {
          items: mockClients,
          total: mockClients.length,
          page: 1,
          page_size: 50,
        },
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse)

      await store.fetchClients()

      expect(apiClient.get).toHaveBeenCalledWith('/clients', {
        params: { page: 1, page_size: 50 },
      })
      expect(store.clients).toEqual(mockClients)
      expect(store.total).toBe(mockClients.length)
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('should handle fetch error', async () => {
      const errorMessage = 'Network error'
      vi.mocked(apiClient.get).mockRejectedValueOnce(new Error(errorMessage))

      await store.fetchClients()

      expect(store.clients).toEqual([])
      expect(store.loading).toBe(false)
      expect(store.error).toBe(errorMessage)
    })

    it('should set loading state correctly', async () => {
      const mockResponse = {
        data: {
          items: mockClients,
          total: mockClients.length,
          page: 1,
          page_size: 50,
        },
      }

      let resolvePromise: (value: unknown) => void
      const promise = new Promise((resolve) => {
        resolvePromise = resolve as (value: unknown) => void
      })
      vi.mocked(apiClient.get).mockReturnValueOnce(promise)

      const fetchPromise = store.fetchClients()
      expect(store.loading).toBe(true)

      resolvePromise!(mockResponse)
      await fetchPromise

      expect(store.loading).toBe(false)
    })
  })

  describe('fetchClient', () => {
    it('should fetch a single client successfully', async () => {
      const mockClient = mockClients[0]
      const mockResponse = {
        data: mockClient,
      }

      vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse)

      const result = await store.fetchClient('client-1')

      expect(apiClient.get).toHaveBeenCalledWith('/clients/client-1')
      expect(store.currentClient).toEqual(mockClient)
      expect(result).toEqual(mockClient)
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('should handle 404 error', async () => {
      const error = {
        response: {
          status: 404,
          data: { detail: 'Client not found' },
        },
      }
      vi.mocked(apiClient.get).mockRejectedValueOnce(error)

      await expect(store.fetchClient('nonexistent')).rejects.toEqual(error)

      expect(store.error).toBe('Client not found')
      expect(store.currentClient).toBeNull()
      expect(store.loading).toBe(false)
    })
  })

  describe('createClient', () => {
    it('should create a new client successfully', async () => {
      const newClientData = {
        first_name: 'Bob',
        last_name: 'Johnson',
        email: 'bob.johnson@example.com',
        phone: '+1234567893',
      }

      const mockResponse = {
        data: {
          ...newClientData,
          id: 'client-3',
          workspace_id: 'workspace-1',
          full_name: 'Bob Johnson',
          date_of_birth: null,
          address: null,
          emergency_contact_name: null,
          emergency_contact_phone: null,
          medical_history: null,
          notes: null,
          created_at: '2025-10-02T10:00:00Z',
          updated_at: '2025-10-02T10:00:00Z',
        },
      }

      vi.mocked(apiClient.post).mockResolvedValueOnce(mockResponse)

      const result = await store.createClient(newClientData)

      expect(apiClient.post).toHaveBeenCalledWith('/clients', newClientData)
      expect(store.clients).toHaveLength(1)
      expect(store.clients[0]).toEqual(mockResponse.data)
      expect(result).toEqual(mockResponse.data)
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('should handle creation error', async () => {
      const newClientData = {
        first_name: 'Bob',
        last_name: 'Johnson',
      }

      const errorMessage = 'Validation error'
      vi.mocked(apiClient.post).mockRejectedValueOnce(new Error(errorMessage))

      await expect(store.createClient(newClientData)).rejects.toThrow(errorMessage)

      expect(store.clients).toHaveLength(0)
      expect(store.error).toBe(errorMessage)
      expect(store.loading).toBe(false)
    })
  })

  describe('updateClient', () => {
    it('should update a client successfully', async () => {
      // First, add a client to the store
      store.clients = [mockClients[0]]

      const updates = {
        phone: '+9999999999',
        notes: 'Updated notes',
      }

      const mockResponse = {
        data: {
          ...mockClients[0],
          ...updates,
          updated_at: '2025-10-02T12:00:00Z',
        },
      }

      vi.mocked(apiClient.put).mockResolvedValueOnce(mockResponse)

      const result = await store.updateClient('client-1', updates)

      expect(apiClient.put).toHaveBeenCalledWith('/clients/client-1', updates)
      expect(store.clients[0].phone).toBe('+9999999999')
      expect(store.clients[0].notes).toBe('Updated notes')
      expect(result).toEqual(mockResponse.data)
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('should handle update error', async () => {
      const errorMessage = 'Update failed'
      vi.mocked(apiClient.put).mockRejectedValueOnce(new Error(errorMessage))

      await expect(store.updateClient('client-1', { notes: 'test' })).rejects.toThrow(
        errorMessage
      )

      expect(store.error).toBe(errorMessage)
      expect(store.loading).toBe(false)
    })
  })

  describe('deleteClient', () => {
    it('should delete a client successfully', async () => {
      // First, add clients to the store
      store.clients = [...mockClients]

      vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: null })

      await store.deleteClient('client-1')

      expect(apiClient.delete).toHaveBeenCalledWith('/clients/client-1')
      expect(store.clients).toHaveLength(1)
      expect(store.clients[0].id).toBe('client-2')
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('should clear currentClient if it is being deleted', async () => {
      store.currentClient = mockClients[0]

      vi.mocked(apiClient.delete).mockResolvedValueOnce({ data: null })

      await store.deleteClient('client-1')

      expect(store.currentClient).toBeNull()
    })

    it('should handle delete error', async () => {
      const errorMessage = 'Delete failed'
      vi.mocked(apiClient.delete).mockRejectedValueOnce(new Error(errorMessage))

      await expect(store.deleteClient('client-1')).rejects.toThrow(errorMessage)

      expect(store.error).toBe(errorMessage)
      expect(store.loading).toBe(false)
    })
  })

  describe('clearClients', () => {
    it('should clear all clients and reset state', () => {
      store.clients = [...mockClients]
      store.currentClient = mockClients[0]
      store.total = 2

      store.clearClients()

      expect(store.clients).toEqual([])
      expect(store.currentClient).toBeNull()
      expect(store.total).toBe(0)
    })
  })

  describe('hasClients computed', () => {
    it('should return true when clients exist', () => {
      store.clients = [...mockClients]
      expect(store.hasClients).toBe(true)
    })

    it('should return false when clients array is empty', () => {
      store.clients = []
      expect(store.hasClients).toBe(false)
    })
  })
})
