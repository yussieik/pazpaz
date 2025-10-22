/**
 * Notification Settings Composable
 *
 * Provides reactive state and immediate save functionality for notification settings.
 * Handles loading, saving, validation, and error states.
 */

import { ref, watch } from 'vue'
import { getNotificationSettings, updateNotificationSettings } from '@/api/notification-settings'
import type { NotificationSettings } from '@/types/notification-settings'
import { useToast } from './useToast'

/**
 * Composable for managing notification settings
 *
 * Features:
 * - Immediate save on any change
 * - Loading and saving states
 * - Error handling with toast notifications
 * - Optimistic updates (UI updates immediately)
 *
 * @example
 * const { settings, isLoading, isSaving, error, loadSettings } = useNotificationSettings()
 * await loadSettings()
 * settings.value.email_enabled = true // Saves immediately
 */
export function useNotificationSettings() {
  const { showError } = useToast()

  // State
  const settings = ref<NotificationSettings | null>(null)
  const isLoading = ref(false)
  const isSaving = ref(false)
  const error = ref<string | null>(null)

  // Flag to prevent saving during initial load
  let isInitialLoad = true

  /**
   * Load notification settings from API
   */
  async function loadSettings() {
    isLoading.value = true
    error.value = null

    try {
      const data = await getNotificationSettings()
      // Temporarily disable watch during initial load
      isInitialLoad = true
      settings.value = data
      // Re-enable watch after initial load completes
      // Use nextTick to ensure the watch doesn't trigger on this assignment
      setTimeout(() => {
        isInitialLoad = false
      }, 0)
    } catch (err: unknown) {
      const apiError = err as { response?: { data?: { detail?: string } }; requestId?: string }
      const message = apiError.response?.data?.detail || 'Failed to load notification settings'
      error.value = message
      showError(message, apiError.requestId)
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Save notification settings to API
   */
  async function saveSettings() {
    if (!settings.value) return

    isSaving.value = true
    error.value = null

    try {
      const updated = await updateNotificationSettings(settings.value)
      // Update local state with server response (in case server modified values)
      settings.value = updated
    } catch (err: unknown) {
      const apiError = err as { response?: { data?: { detail?: string } }; requestId?: string }
      const message = apiError.response?.data?.detail || 'Failed to save notification settings'
      error.value = message
      showError(message, apiError.requestId)
    } finally {
      isSaving.value = false
    }
  }

  /**
   * Watch settings for changes and trigger immediate save
   * Deep watch ensures nested property changes are detected
   * No debounce - saves immediately when a setting changes
   * Skips initial load to prevent unnecessary API calls
   */
  watch(
    settings,
    (newSettings) => {
      // Skip save during initial load
      if (newSettings && !isInitialLoad) {
        // Save immediately without debounce
        saveSettings()
      }
    },
    { deep: true }
  )

  return {
    // State
    settings,
    isLoading,
    isSaving,
    error,

    // Actions
    loadSettings,
  }
}
