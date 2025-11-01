import { ref } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import apiClient from '@/api/client'
import type { Client, ClientCreate, ClientListItem } from '@/types/client'

/**
 * Composable for client search and recent clients functionality
 *
 * Provides:
 * - Debounced search (300ms)
 * - Recent clients fetching (last 30 days)
 * - Client creation
 *
 * Usage:
 *   const { searchClients, recentClients, createClient, ... } = useClientSearch()
 */
export function useClientSearch() {
  const searchResults = ref<Client[]>([])
  const recentClients = ref<Client[]>([])
  const isSearching = ref(false)
  const isLoadingRecent = ref(false)
  const isCreating = ref(false)
  const error = ref<string | null>(null)

  /**
   * Fetch recent clients (last 30 days, max 3)
   * Used to show most relevant clients at the top of the dropdown
   */
  async function fetchRecentClients() {
    isLoadingRecent.value = true
    error.value = null

    try {
      // TODO: Update API endpoint to support recent=true filter when backend implements it
      // For now, fetch all clients and filter/sort client-side
      const response = await apiClient.get<{ items: Client[]; total: number }>(
        '/clients?page=1&page_size=100'
      )

      // Sort by most recent last_appointment (if available) or created_at
      const sorted = response.data.items.sort((a, b) => {
        const aList = a as ClientListItem
        const bList = b as ClientListItem
        const aDate = (aList.last_appointment ?? a.created_at) as string
        const bDate = (bList.last_appointment ?? b.created_at) as string
        return new Date(bDate).getTime() - new Date(aDate).getTime()
      })

      // Take top 3
      recentClients.value = sorted.slice(0, 3)
    } catch (err) {
      console.error('Failed to fetch recent clients:', err)
      error.value = 'Failed to load recent clients'
      recentClients.value = []
    } finally {
      isLoadingRecent.value = false
    }
  }

  /**
   * Search clients by name
   * Debounced by 300ms to reduce API calls while typing
   */
  const debouncedSearch = useDebounceFn(async (query: string) => {
    if (!query.trim()) {
      searchResults.value = []
      return
    }

    isSearching.value = true
    error.value = null

    try {
      // TODO: Update API endpoint to support search parameter when backend implements it
      // For now, fetch all clients and filter client-side
      const response = await apiClient.get<{ items: Client[]; total: number }>(
        '/clients?page=1&page_size=100'
      )

      // Filter by name (case-insensitive)
      const lowerQuery = query.toLowerCase()
      searchResults.value = response.data.items.filter(
        (client) =>
          client.first_name.toLowerCase().includes(lowerQuery) ||
          client.last_name.toLowerCase().includes(lowerQuery) ||
          client.full_name.toLowerCase().includes(lowerQuery)
      )
    } catch (err) {
      console.error('Client search failed:', err)
      error.value = 'Search failed. Please try again.'
      searchResults.value = []
    } finally {
      isSearching.value = false
    }
  }, 300)

  /**
   * Public search function that wraps the debounced search
   */
  function searchClients(query: string) {
    debouncedSearch(query)
  }

  /**
   * Create a new client
   */
  async function createClient(clientData: ClientCreate): Promise<Client | null> {
    isCreating.value = true
    error.value = null

    try {
      const response = await apiClient.post<Client>('/clients', clientData)
      return response.data
    } catch (err) {
      console.error('Failed to create client:', err)
      error.value =
        (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ||
        'Failed to create client'
      return null
    } finally {
      isCreating.value = false
    }
  }

  /**
   * Clear search results
   */
  function clearSearch() {
    searchResults.value = []
  }

  return {
    // State
    searchResults,
    recentClients,
    isSearching,
    isLoadingRecent,
    isCreating,
    error,

    // Methods
    searchClients,
    fetchRecentClients,
    createClient,
    clearSearch,
  }
}
