import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import apiClient from '@/api/client'

/**
 * Authentication Store
 *
 * Manages user authentication state and provides logout functionality.
 * Ensures encrypted session backups are cleared on logout for HIPAA compliance.
 * Handles 401 Unauthorized responses with automatic logout.
 *
 * Usage:
 *   const authStore = useAuthStore()
 *   await authStore.initializeAuth()  // Check authentication on app load
 *   await authStore.logout()          // Manual logout
 */

export interface User {
  id: string
  email: string
  workspace_id: string
  role: string
  is_platform_admin: boolean
}

/**
 * Clear all encrypted session backups from localStorage
 * HIPAA COMPLIANCE: Prevents PHI leakage on shared computers
 *
 * NOTE: This function is defined here to avoid circular dependency
 * (auth store -> useSecureOfflineBackup -> auth store)
 */
function clearAllBackups(): void {
  const keys = Object.keys(localStorage)
  let cleared = 0

  for (const key of keys) {
    if (key.startsWith('session_') && key.endsWith('_backup')) {
      localStorage.removeItem(key)
      cleared++
    }
  }

  if (cleared > 0) {
    console.debug(`[SecureBackup] Cleared ${cleared} backup(s) on logout`)
  }
}

export const useAuthStore = defineStore('auth', () => {
  // Auth state
  const user = ref<User | null>(null)

  // Computed property for authentication status
  const isAuthenticated = computed(() => user.value !== null)

  /**
   * Initialize authentication state
   * Call on app mount to check if user has valid session
   */
  async function initializeAuth(): Promise<void> {
    try {
      const response = await apiClient.get('/auth/me')
      user.value = response.data
      console.debug('[Auth] User authenticated:', user.value?.id)
    } catch (error) {
      // Not authenticated or session expired
      if ((error as { response?: { status?: number } }).response?.status === 401) {
        console.debug('[Auth] No active session')
      } else {
        console.error('[Auth] Failed to check authentication:', error)
      }
      user.value = null
    }
  }

  /**
   * Logout user and clear all encrypted session backups
   * HIPAA COMPLIANCE: Prevents PHI leakage on shared computers
   *
   * This method:
   * 1. Calls backend logout endpoint to invalidate JWT
   * 2. Clears encrypted session backups from localStorage
   * 3. Clears auth state
   * 4. Does NOT redirect (caller handles redirect)
   */
  async function logout(): Promise<void> {
    console.debug('[Auth] Logging out...')

    try {
      // Call backend logout endpoint (invalidates JWT)
      await apiClient.post('/auth/logout')
    } catch (error) {
      // Logout anyway, even if backend call fails
      console.error('[Auth] Logout API call failed (continuing anyway):', error)
    } finally {
      // Clear all frontend state
      user.value = null

      // Clear encrypted session backups from localStorage
      try {
        clearAllBackups()
        console.debug('[Auth] Cleared encrypted backups')
      } catch (error) {
        console.error('[Auth] Failed to clear backups:', error)
      }

      // Clear any cached data in other stores
      // (Add here if you have other stores that need clearing)

      console.debug('[Auth] Logout complete')
    }
  }

  /**
   * Set authenticated user
   * Called after successful login/verification
   */
  function setUser(userData: User): void {
    user.value = userData
  }

  /**
   * Clear user state
   * Used internally or for testing
   */
  function clearUser(): void {
    user.value = null
  }

  return {
    // State
    user,
    isAuthenticated,

    // Actions
    initializeAuth,
    logout,
    setUser,
    clearUser,
  }
})
