import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useSecureOfflineBackup } from '@/composables/useSecureOfflineBackup'
import apiClient from '@/api/client'

/**
 * Authentication Store
 *
 * Manages user authentication state and provides logout functionality.
 * Ensures encrypted session backups are cleared on logout for HIPAA compliance.
 *
 * Usage:
 *   const authStore = useAuthStore()
 *   authStore.logout()
 */

export interface User {
  id: string
  email: string
  workspace_id: string
  role: string
}

export const useAuthStore = defineStore('auth', () => {
  const { clearAllBackups } = useSecureOfflineBackup()

  // Auth state
  const user = ref<User | null>(null)
  const isAuthenticated = ref(false)

  /**
   * Logout user and clear all encrypted session backups
   * HIPAA COMPLIANCE: Prevents PHI leakage on shared computers
   */
  async function logout() {
    try {
      // 1. Call backend logout endpoint (blacklist JWT)
      await apiClient.post('/auth/logout')
    } catch (error) {
      console.error('Logout API call failed:', error)
      // Continue with client-side cleanup even if server logout fails
    }

    // 2. Clear all encrypted session backups from localStorage
    clearAllBackups()

    // 3. Clear auth state
    user.value = null
    isAuthenticated.value = false

    // 4. Redirect to login
    // Note: Adjust this path based on your routing setup
    window.location.href = '/login'
  }

  /**
   * Set authenticated user
   */
  function setUser(userData: User) {
    user.value = userData
    isAuthenticated.value = true
  }

  /**
   * Clear user state (used during logout)
   */
  function clearUser() {
    user.value = null
    isAuthenticated.value = false
  }

  return {
    // State
    user,
    isAuthenticated,

    // Actions
    logout,
    setUser,
    clearUser,
  }
})
