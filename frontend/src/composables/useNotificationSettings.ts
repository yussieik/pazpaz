/**
 * Notification Settings Composable
 *
 * Provides reactive state and auto-save functionality for notification settings.
 * Handles loading, saving, validation, and error states.
 */

import { ref, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import {
  getNotificationSettings,
  updateNotificationSettings,
} from '@/api/notification-settings'
import type { NotificationSettings } from '@/types/notification-settings'
import { useToast } from './useToast'

/**
 * Composable for managing notification settings
 *
 * Features:
 * - Auto-save with 150ms debounce (batches rapid changes)
 * - Loading and saving states
 * - Error handling with toast notifications
 * - Optimistic updates (UI updates immediately)
 *
 * @example
 * const { settings, isLoading, isSaving, error, loadSettings } = useNotificationSettings()
 * await loadSettings()
 * settings.value.email_enabled = true // Saves after 150ms
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
  // Flag to prevent saving when updating from server response
  let isUpdatingFromServer = false

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
      const apiError = err as {
        response?: { data?: { detail?: string } }
        requestId?: string
      }
      const message =
        apiError.response?.data?.detail || 'Failed to load notification settings'
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
      // Set flag to prevent watch from triggering another save
      isUpdatingFromServer = true
      settings.value = updated
      // Clear flag after Vue's reactivity system processes the update
      setTimeout(() => {
        isUpdatingFromServer = false
      }, 0)
    } catch (err: unknown) {
      const apiError = err as {
        response?: { data?: { detail?: string } }
        requestId?: string
      }
      const message =
        apiError.response?.data?.detail || 'Failed to save notification settings'
      error.value = message
      showError(message, apiError.requestId)
    } finally {
      isSaving.value = false
    }
  }

  /**
   * Debounced save function (150ms delay)
   * Short debounce to batch rapid changes (like toggling master switch)
   * while still feeling immediate to the user
   */
  const debouncedSave = useDebounceFn(async () => {
    if (!isInitialLoad && !isUpdatingFromServer) {
      await saveSettings()
    }
  }, 150)

  /**
   * Watch settings for changes and trigger debounced save
   * Deep watch ensures nested property changes are detected
   * 150ms debounce batches rapid changes while feeling immediate
   * Skips initial load and server updates to prevent unnecessary API calls
   */
  watch(
    settings,
    (newSettings) => {
      // Skip save during initial load or when updating from server
      if (newSettings && !isInitialLoad && !isUpdatingFromServer) {
        // Debounce to batch rapid changes (e.g., toggling master switch)
        debouncedSave()
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
