import { ref, computed, type Ref } from 'vue'
import apiClient from '@/api/client'
import type { AxiosError } from 'axios'

/**
 * Google Calendar Integration Composable
 *
 * Manages Google Calendar OAuth integration state and operations.
 *
 * Features:
 * - Check connection status
 * - Initiate OAuth flow (popup-based)
 * - Disconnect integration
 * - Update sync settings (auto_sync, include_client_names)
 *
 * OAuth Flow:
 * 1. Call connect() to get authorization URL
 * 2. Open URL in popup window (600x700px)
 * 3. User authorizes in Google
 * 4. Backend handles callback and redirects to /settings?gcal=success
 * 5. Poll for status changes while popup is open
 * 6. Show success/error feedback
 *
 * @example
 * const {
 *   isConnected,
 *   settings,
 *   connect,
 *   disconnect,
 *   fetchStatus
 * } = useGoogleCalendarIntegration()
 *
 * await fetchStatus() // Check current status
 * if (!isConnected.value) {
 *   await connect() // Open OAuth popup
 * }
 */

interface GoogleCalendarSettings {
  auto_sync_enabled: boolean
  include_client_names: boolean
  notify_clients: boolean
}

interface GoogleCalendarStatus {
  connected: boolean
  enabled: boolean
  sync_client_names: boolean
  notify_clients: boolean
  last_sync_at: string | null
}

export function useGoogleCalendarIntegration() {
  // State
  const status: Ref<GoogleCalendarStatus | null> = ref(null)
  const isLoading: Ref<boolean> = ref(false)
  const error: Ref<string | null> = ref(null)

  // Computed
  const isConnected = computed(() => status.value?.connected ?? false)
  const lastSyncTime = computed(() => status.value?.last_sync_at ?? null)
  const settings = computed<GoogleCalendarSettings>(() => ({
    auto_sync_enabled: status.value?.enabled ?? false,
    include_client_names: status.value?.sync_client_names ?? false,
    notify_clients: status.value?.notify_clients ?? false,
  }))

  /**
   * Fetch current Google Calendar connection status
   *
   * @throws Error if API call fails
   */
  async function fetchStatus(): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      const response = await apiClient.get<GoogleCalendarStatus>(
        '/integrations/google-calendar/status'
      )
      status.value = response.data
    } catch (err) {
      const axiosError = err as AxiosError
      error.value = 'Failed to fetch connection status'
      console.error('[GoogleCalendar] Failed to fetch status:', axiosError)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Initiate Google Calendar OAuth flow
   *
   * Returns the authorization URL for opening in a popup.
   * Does NOT open the popup itself - that's handled by the component.
   *
   * @returns Authorization URL to open in popup
   * @throws Error if API call fails
   */
  async function connect(): Promise<string> {
    isLoading.value = true
    error.value = null

    try {
      const response = await apiClient.post<{ authorization_url: string }>(
        '/integrations/google-calendar/authorize',
        {},
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      )
      return response.data.authorization_url
    } catch (err) {
      const axiosError = err as AxiosError
      error.value = 'Failed to start authorization'
      console.error('[GoogleCalendar] Failed to get auth URL:', axiosError)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Disconnect Google Calendar integration
   *
   * Idempotent - safe to call even if not connected.
   * Clears all stored tokens and disables sync.
   *
   * @throws Error if API call fails
   */
  async function disconnect(): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      await apiClient.delete('/integrations/google-calendar')
      // Update local state immediately for responsive UI
      status.value = {
        connected: false,
        last_sync_at: null,
        enabled: false,
        sync_client_names: false,
        notify_clients: false,
      }
    } catch (err) {
      const axiosError = err as AxiosError
      error.value = 'Failed to disconnect'
      console.error('[GoogleCalendar] Failed to disconnect:', axiosError)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Update Google Calendar sync settings
   *
   * @param newSettings - Partial settings to update
   * @throws Error if API call fails
   */
  async function updateSettings(
    newSettings: Partial<GoogleCalendarSettings>
  ): Promise<void> {
    isLoading.value = true
    error.value = null

    try {
      // Map frontend field names to backend field names
      const backendSettings: Record<string, boolean> = {}

      if (newSettings.auto_sync_enabled !== undefined) {
        backendSettings.enabled = newSettings.auto_sync_enabled
      }

      if (newSettings.include_client_names !== undefined) {
        backendSettings.sync_client_names = newSettings.include_client_names
      }

      if (newSettings.notify_clients !== undefined) {
        backendSettings.notify_clients = newSettings.notify_clients
      }

      // Call backend PATCH endpoint
      await apiClient.patch('/integrations/google-calendar/settings', backendSettings)

      // Refresh status to get updated settings
      await fetchStatus()
    } catch (err) {
      const axiosError = err as AxiosError
      error.value = 'Failed to update settings'
      console.error('[GoogleCalendar] Failed to update settings:', axiosError)
      throw err
    } finally {
      isLoading.value = false
    }
  }

  return {
    // State
    status,
    isLoading,
    error,

    // Computed
    isConnected,
    lastSyncTime,
    settings,

    // Methods
    fetchStatus,
    connect,
    disconnect,
    updateSettings,
  }
}
