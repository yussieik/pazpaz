/**
 * Auth Session Store
 *
 * Manages session state and unsaved changes tracking
 * Used for logout confirmation and session expiration warnings
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getUnsavedDraftDescriptions } from '@/utils/draftStorage'

export const useAuthSessionStore = defineStore('authSession', () => {
  // Session expiration tracking
  const sessionExpiresAt = ref<Date | null>(null)

  // Unsaved changes tracking (for logout confirmation)
  const unsavedItems = ref<Map<string, string>>(new Map())

  // Computed: Do we have any unsaved changes?
  const hasUnsavedChanges = computed(() => unsavedItems.value.size > 0)

  // Computed: Array of unsaved item descriptions
  const unsavedItemDescriptions = computed(() => Array.from(unsavedItems.value.values()))

  /**
   * Track an unsaved change
   *
   * @param key - Unique identifier (e.g., session_id)
   * @param description - Human-readable description (e.g., "John Doe (Session at 10:00 AM)")
   */
  function trackUnsavedChange(key: string, description: string) {
    unsavedItems.value.set(key, description)
    console.info(`[AuthSession] Tracking unsaved change: ${description}`)
  }

  /**
   * Clear a specific unsaved change (when saved)
   *
   * @param key - Unique identifier to clear
   */
  function clearUnsavedChange(key: string) {
    const description = unsavedItems.value.get(key)
    if (description) {
      unsavedItems.value.delete(key)
      console.info(`[AuthSession] Cleared unsaved change: ${description}`)
    }
  }

  /**
   * Clear all unsaved changes (on logout)
   */
  function clearAllUnsavedChanges() {
    const count = unsavedItems.value.size
    unsavedItems.value.clear()
    if (count > 0) {
      console.info(`[AuthSession] Cleared ${count} unsaved changes`)
    }
  }

  /**
   * Set session expiration time
   *
   * @param expiresAt - Date when session expires
   */
  function setSessionExpiry(expiresAt: Date) {
    sessionExpiresAt.value = expiresAt
    console.info(`[AuthSession] Session expires at: ${expiresAt.toLocaleTimeString()}`)
  }

  /**
   * Get time remaining until session expires (in seconds)
   *
   * @returns Seconds until expiration, or null if no expiry set
   */
  function getTimeRemaining(): number | null {
    if (!sessionExpiresAt.value) {
      return null
    }

    const now = new Date()
    const diff = sessionExpiresAt.value.getTime() - now.getTime()
    return Math.max(0, Math.floor(diff / 1000))
  }

  /**
   * Check if session is expired
   *
   * @returns true if session has expired
   */
  function isSessionExpired(): boolean {
    if (!sessionExpiresAt.value) {
      return false
    }

    const now = new Date()
    return sessionExpiresAt.value <= now
  }

  /**
   * Sync unsaved changes from IndexedDB
   *
   * Called on app init to detect drafts from previous session
   */
  async function syncUnsavedChangesFromDB() {
    try {
      const draftDescriptions = await getUnsavedDraftDescriptions()
      draftDescriptions.forEach((description, index) => {
        // Use draft description as both key and value for simplicity
        trackUnsavedChange(`draft_${index}`, description)
      })

      if (draftDescriptions.length > 0) {
        console.info(`[AuthSession] Synced ${draftDescriptions.length} drafts from IndexedDB`)
      }
    } catch (error) {
      console.error('[AuthSession] Failed to sync drafts from IndexedDB:', error)
    }
  }

  /**
   * Reset all session state (on logout)
   */
  function resetSession() {
    sessionExpiresAt.value = null
    clearAllUnsavedChanges()
    console.info('[AuthSession] Session state reset')
  }

  return {
    // State
    sessionExpiresAt,
    hasUnsavedChanges,
    unsavedItemDescriptions,

    // Actions
    trackUnsavedChange,
    clearUnsavedChange,
    clearAllUnsavedChanges,
    setSessionExpiry,
    getTimeRemaining,
    isSessionExpired,
    syncUnsavedChangesFromDB,
    resetSession,
  }
})
