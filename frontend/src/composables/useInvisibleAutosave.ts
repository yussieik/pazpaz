import { ref, watch, computed, onUnmounted, type Ref } from 'vue'
import { useDebounceFn, useOnline } from '@vueuse/core'

/**
 * Invisible Autosave Composable - Three-Tier Architecture
 *
 * Tier 1: Instant local persistence (0ms latency) - every keystroke saves to localStorage
 * Tier 2: Debounced server sync (750ms after typing stops)
 * Tier 3: Strategic immediate syncs (field blur, navigation, browser close)
 *
 * Visual feedback: 99% invisible, only shows banners for offline/error states
 *
 * Usage:
 *   const { state, flushSync, restoreDraft } = useInvisibleAutosave(
 *     sessionId,
 *     formData,
 *     async (id, data) => { await api.save(id, data) },
 *     { debounce: 750 }
 *   )
 */

export type AutosaveState =
  | { type: 'idle' }
  | { type: 'offline'; queuedSaves: number }
  | { type: 'syncing'; attempt: number }
  | { type: 'error'; error: Error; recoverable: boolean; retryCountdown?: number }

interface AutosaveOptions {
  debounce?: number
  retryBackoff?: number[]
  onSuccess?: () => void
  onError?: (error: Error) => void
}

export function useInvisibleAutosave<T extends Record<string, unknown>>(
  id: Ref<string>,
  data: Ref<T>,
  saveFn: (id: string, data: T) => Promise<void>,
  options: AutosaveOptions = {}
) {
  const {
    debounce = 750,
    retryBackoff = [1000, 2000, 4000, 8000],
    onSuccess,
    onError,
  } = options

  const state = ref<AutosaveState>({ type: 'idle' })
  const isOnline = useOnline()
  let isSyncing = false
  const saveQueue: Array<() => Promise<void>> = []
  let retryTimeoutId: number | null = null

  // Tier 1: Instant local persistence
  const localStorageKey = computed(() => `session_${id.value}_draft`)

  watch(
    data,
    (newValue) => {
      try {
        localStorage.setItem(localStorageKey.value, JSON.stringify(newValue))
      } catch (error) {
        console.error('[Autosave] Failed to save to localStorage:', error)
      }
    },
    { deep: true, flush: 'post' }
  )

  // Tier 2: Debounced server sync
  const syncToServer = async () => {
    if (!isOnline.value) {
      state.value = { type: 'offline', queuedSaves: saveQueue.length + 1 }
      return
    }

    if (isSyncing) {
      saveQueue.push(syncToServer)
      return
    }

    isSyncing = true
    state.value = { type: 'syncing', attempt: 1 }

    try {
      await saveFn(id.value, data.value)

      // Success
      state.value = { type: 'idle' }
      localStorage.removeItem(localStorageKey.value)
      onSuccess?.()

      // Process queued saves
      isSyncing = false
      if (saveQueue.length > 0) {
        const nextSave = saveQueue.shift()
        nextSave?.()
      }
    } catch (error) {
      isSyncing = false
      await handleSyncError(error as Error)
    }
  }

  const handleSyncError = async (error: Error) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const status = (error as any).status || (error as any).response?.status
    const errorMessage = error.message || ''
    const isRecoverable =
      [500, 502, 503, 504].includes(status) ||
      errorMessage.includes('timeout') ||
      errorMessage.includes('network') ||
      errorMessage.includes('Network')

    if (!isRecoverable) {
      state.value = { type: 'error', error, recoverable: false }
      onError?.(error)
      return
    }

    // Retry with exponential backoff
    for (let i = 0; i < retryBackoff.length; i++) {
      state.value = { type: 'syncing', attempt: i + 2 }

      await sleep(retryBackoff[i] ?? 1000)

      try {
        await saveFn(id.value, data.value)
        state.value = { type: 'idle' }
        localStorage.removeItem(localStorageKey.value)
        onSuccess?.()
        return
      } catch (retryError) {
        // Continue to next retry
      }
    }

    // Exhausted retries
    state.value = { type: 'error', error, recoverable: true }
    onError?.(error)
  }

  const debouncedSync = useDebounceFn(syncToServer, debounce)

  watch(data, debouncedSync, { deep: true })

  // Tier 3: Immediate sync
  const flushSync = () => {
    // Note: useDebounceFn may not have a cancel method in all versions
    // The immediate sync will override any pending debounced sync
    return syncToServer()
  }

  // Manual retry function (for banner "Retry now" button)
  const retryNow = () => {
    if (retryTimeoutId) {
      clearTimeout(retryTimeoutId)
      retryTimeoutId = null
    }
    return syncToServer()
  }

  // Watch online status - flush when back online
  watch(isOnline, (online) => {
    if (online && state.value.type === 'offline') {
      flushSync()
    }
  })

  // Restore from localStorage
  const restoreDraft = (): T | null => {
    try {
      const draft = localStorage.getItem(localStorageKey.value)
      if (draft) {
        return JSON.parse(draft) as T
      }
    } catch (error) {
      console.error('[Autosave] Failed to restore from localStorage:', error)
    }
    return null
  }

  // Clear draft from localStorage
  const clearDraft = () => {
    try {
      localStorage.removeItem(localStorageKey.value)
    } catch (error) {
      console.error('[Autosave] Failed to clear localStorage draft:', error)
    }
  }

  // Cleanup
  onUnmounted(() => {
    // Note: useDebounceFn cleanup is handled automatically
    if (retryTimeoutId) {
      clearTimeout(retryTimeoutId)
    }
  })

  return {
    state,
    flushSync,
    retryNow,
    restoreDraft,
    clearDraft,
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
