import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '@/api/client'
import type { paths } from '@/api/schema'
import type { ClientCreate, ClientUpdate } from '@/types/client'

/**
 * Clients Store
 *
 * Manages client state and API interactions.
 * Provides methods for CRUD operations on clients.
 */

// Type definitions from OpenAPI schema
type ClientResponse =
  paths['/api/v1/clients']['get']['responses']['200']['content']['application/json']
type ClientListItem = ClientResponse['items'][0]
type ClientDetailResponse =
  paths['/api/v1/clients/{client_id}']['get']['responses']['200']['content']['application/json']

export const useClientsStore = defineStore('clients', () => {
  // State
  const clients = ref<ClientListItem[]>([])
  const currentClient = ref<ClientDetailResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const total = ref(0)

  // Getters
  const hasClients = computed(() => clients.value.length > 0)

  // Actions

  /**
   * Fetch all clients with optional pagination
   */
  async function fetchClients(page: number = 1, pageSize: number = 50) {
    loading.value = true
    error.value = null

    try {
      const params: Record<string, string | number> = {
        page,
        page_size: pageSize,
      }

      const response = await apiClient.get<ClientResponse>('/clients', {
        params,
      })

      clients.value = response.data.items
      total.value = response.data.total
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
          error.value = 'Failed to fetch clients'
        }
      } else if (err && typeof err === 'object' && 'message' in err) {
        error.value = String((err as { message: unknown }).message)
      } else {
        error.value = 'Failed to fetch clients'
      }
      console.error('Error fetching clients:', err)
    } finally {
      loading.value = false
    }
  }

  /**
   * Fetch a single client by ID
   */
  async function fetchClient(clientId: string) {
    loading.value = true
    error.value = null

    try {
      const response = await apiClient.get<ClientDetailResponse>(`/clients/${clientId}`)

      currentClient.value = response.data
      return response.data
    } catch (err: unknown) {
      // Handle Axios errors with detailed error messages
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosError = err as {
          response?: { status: number; data?: { detail?: string } }
        }
        if (axiosError.response?.status === 404) {
          error.value = 'Client not found'
        } else if (axiosError.response?.status === 401) {
          error.value = 'Authentication required. Please log in.'
        } else if (axiosError.response?.data?.detail) {
          error.value = axiosError.response.data.detail
        } else if ('message' in err) {
          error.value = String((err as { message: unknown }).message)
        } else {
          error.value = 'Failed to fetch client'
        }
      } else if (err && typeof err === 'object' && 'message' in err) {
        error.value = String((err as { message: unknown }).message)
      } else {
        error.value = 'Failed to fetch client'
      }
      console.error('Error fetching client:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Create a new client
   */
  async function createClient(clientData: ClientCreate) {
    loading.value = true
    error.value = null

    try {
      const response = await apiClient.post<ClientDetailResponse>(
        '/clients',
        clientData
      )

      // Add new client to local state (optimistic update)
      // Cast to ClientListItem since it has the same structure
      clients.value.push(response.data as unknown as ClientListItem)

      return response.data
    } catch (err) {
      if (err && typeof err === 'object' && 'message' in err) {
        error.value = (err as Error).message
      } else {
        error.value = 'Failed to create client'
      }
      console.error('Error creating client:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Update an existing client
   */
  async function updateClient(clientId: string, updates: ClientUpdate) {
    loading.value = true
    error.value = null

    try {
      const response = await apiClient.put<ClientDetailResponse>(
        `/clients/${clientId}`,
        updates
      )

      // Update local state
      const index = clients.value.findIndex((c) => c.id === clientId)
      if (index !== -1) {
        clients.value[index] = response.data as unknown as ClientListItem
      }

      // Update current client if it's the one being edited
      if (currentClient.value?.id === clientId) {
        currentClient.value = response.data
      }

      return response.data
    } catch (err) {
      if (err && typeof err === 'object' && 'message' in err) {
        error.value = (err as Error).message
      } else {
        error.value = 'Failed to update client'
      }
      console.error('Error updating client:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Delete a client
   */
  async function deleteClient(clientId: string) {
    loading.value = true
    error.value = null

    try {
      await apiClient.delete(`/clients/${clientId}`)

      // Remove from local state
      clients.value = clients.value.filter((c) => c.id !== clientId)

      // Clear current client if it's the one being deleted
      if (currentClient.value?.id === clientId) {
        currentClient.value = null
      }
    } catch (err) {
      if (err && typeof err === 'object' && 'message' in err) {
        error.value = (err as Error).message
      } else {
        error.value = 'Failed to delete client'
      }
      console.error('Error deleting client:', err)
      throw err
    } finally {
      loading.value = false
    }
  }

  /**
   * Clear clients from state
   */
  function clearClients() {
    clients.value = []
    currentClient.value = null
    total.value = 0
  }

  return {
    // State
    clients,
    currentClient,
    loading,
    error,
    total,
    // Getters
    hasClients,
    // Actions
    fetchClients,
    fetchClient,
    createClient,
    updateClient,
    deleteClient,
    clearClients,
  }
})
