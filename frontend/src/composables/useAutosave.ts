import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import type { AxiosError } from 'axios'
import { useSecureOfflineBackup } from './useSecureOfflineBackup'

/**
 * Composable for auto-saving content with debounced updates
 *
 * Provides:
 * - Debounced save on content changes (5-second default)
 * - Save status indicators (saving, saved, error)
 * - Last saved timestamp
 * - Force save option (bypass debounce)
 * - Start/stop controls for lifecycle management
 *
 * Usage:
 *   const { isSaving, lastSavedAt, saveError, save, forceSave, start, stop } = useAutosave(
 *     async (data) => { await apiClient.patch(`/sessions/${id}/draft`, data) },
 *     { debounceMs: 5000 }
 *   )
 *
 *   // Trigger autosave (debounced)
 *   save({ subjective: 'Updated text' })
 *
 *   // Force immediate save (e.g., before finalize)
 *   await forceSave({ subjective: 'Final text' })
 */

export interface AutosaveOptions {
  /**
   * Debounce delay in milliseconds
   * @default 5000 (5 seconds)
   */
  debounceMs?: number

  /**
   * Callback invoked on successful save
   */
  onSuccess?: () => void

  /**
   * Callback invoked on save error
   */
  onError?: (error: Error) => void

  /**
   * Enable autosave on initialization
   * @default true
   */
  autoStart?: boolean

  /**
   * Session ID for encrypted localStorage backup
   * Required for offline support
   */
  sessionId?: string

  /**
   * Session version for optimistic locking
   * Used to detect conflicts when syncing offline changes
   */
  version?: number
}

export interface AutosaveState {
  /** Whether a save operation is currently in progress */
  isSaving: boolean

  /** Timestamp of last successful save */
  lastSavedAt: Date | null

  /** Error message from last failed save, or null if no error */
  saveError: string | null

  /** Whether autosave is currently active */
  isActive: boolean
}

export function useAutosave<T = Record<string, unknown>>(
  /**
   * Save function to be called with the data to save
   * Should return a Promise that resolves when save is complete
   */
  saveFn: (data: T) => Promise<void>,
  options: AutosaveOptions = {}
) {
  const {
    debounceMs = 5000,
    onSuccess,
    onError,
    autoStart = true,
    sessionId,
    version,
  } = options

  // State
  const isSaving = ref(false)
  const lastSavedAt = ref<Date | null>(null)
  const saveError = ref<string | null>(null)
  const isActive = ref(autoStart)
  const isOnline = ref(navigator.onLine)

  // Initialize offline backup if session ID provided
  const { backupDraft, syncToServer } = useSecureOfflineBackup()

  /**
   * Network status event handlers
   * Auto-sync when coming back online
   */
  const handleOnline = () => {
    isOnline.value = true
    console.info('[Autosave] Network connection restored')

    // Auto-sync when coming back online
    if (sessionId) {
      syncToServer(sessionId).then((synced) => {
        if (synced) {
          console.info('[Autosave] Auto-synced offline changes to server')
        }
      })
    }
  }

  const handleOffline = () => {
    isOnline.value = false
    console.warn('[Autosave] Network connection lost - changes will be saved locally')
  }

  // Setup network status listeners
  onMounted(() => {
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('online', handleOnline)
    window.removeEventListener('offline', handleOffline)
  })

  /**
   * Perform the actual save operation
   */
  async function performSave(data: T): Promise<void> {
    if (!isActive.value) {
      console.warn('Autosave is stopped, skipping save operation')
      return
    }

    isSaving.value = true
    saveError.value = null

    try {
      // Always backup to encrypted localStorage first (even when online)
      // This provides a safety net in case the network request fails
      if (sessionId && version !== undefined) {
        // Cast to SessionDraft type for backup
        await backupDraft(
          sessionId,
          data as {
            subjective: string | null
            objective: string | null
            assessment: string | null
            plan: string | null
            session_date: string
            duration_minutes: number | null
          },
          version
        )
      }

      // Try to save to server if online
      if (isOnline.value) {
        await saveFn(data)
        lastSavedAt.value = new Date()

        // Clear localStorage after successful server save
        if (sessionId) {
          localStorage.removeItem(`session_${sessionId}_backup`)
        }

        if (onSuccess) {
          onSuccess()
        }
      } else {
        // Offline: backup exists, show offline indicator
        console.info('[Autosave] Offline - changes saved to encrypted localStorage')
      }
    } catch (error) {
      console.error('Autosave failed:', error)

      // Extract error message
      const axiosError = error as AxiosError<{ detail?: string }>
      let errorMessage = 'Failed to save changes'

      if (axiosError.response) {
        switch (axiosError.response.status) {
          case 404:
            errorMessage = 'Session not found'
            break
          case 422:
            errorMessage = axiosError.response.data?.detail || 'Validation error'
            break
          case 429:
            errorMessage = 'Too many save requests. Please wait a moment.'
            break
          case 403:
            errorMessage = 'You do not have permission to edit this session'
            break
          default:
            errorMessage = axiosError.response.data?.detail || errorMessage
        }
      } else if (axiosError.request) {
        errorMessage = 'Network error. Please check your connection.'
        // Mark as offline
        isOnline.value = false
      }

      saveError.value = errorMessage

      if (onError) {
        onError(error as Error)
      }

      // Don't throw error - we have a local backup
      if (!isOnline.value) {
        console.info(
          '[Autosave] Network error caught - changes preserved in local backup'
        )
      } else {
        throw error
      }
    } finally {
      isSaving.value = false
    }
  }

  /**
   * Debounced save function (5-second delay by default)
   * Used for automatic saves during typing
   */
  const debouncedSave = useDebounceFn(async (data: T) => {
    try {
      await performSave(data)
    } catch (error) {
      // Error is already handled in performSave (sets saveError.value)
      // Catch here to prevent unhandled promise rejection
      console.debug('Autosave error caught in debouncedSave:', error)
    }
  }, debounceMs)

  /**
   * Save data with debounce (default autosave behavior)
   *
   * @param data - Data to save
   */
  function save(data: T): void {
    if (!isActive.value) {
      return
    }
    debouncedSave(data)
  }

  /**
   * Force immediate save, bypassing debounce
   * Useful for explicit save actions (e.g., clicking "Finalize")
   *
   * @param data - Data to save
   * @returns Promise that resolves when save is complete
   */
  async function forceSave(data: T): Promise<void> {
    // Note: useDebounceFn doesn't provide explicit cancel method
    // Calling performSave directly bypasses the debounce
    await performSave(data)
  }

  /**
   * Start autosave (enable automatic saves)
   */
  function start(): void {
    isActive.value = true
  }

  /**
   * Stop autosave (disable automatic saves)
   * Useful when navigating away or unmounting component
   */
  function stop(): void {
    isActive.value = false
    // Note: useDebounceFn doesn't provide explicit cancel method
    // The isActive flag prevents further saves
  }

  /**
   * Clear any save errors
   */
  function clearError(): void {
    saveError.value = null
  }

  return {
    // State
    isSaving,
    lastSavedAt,
    saveError,
    isActive,
    isOnline, // NEW: Network status for offline indicator

    // Methods
    save,
    forceSave,
    start,
    stop,
    clearError,
  }
}
