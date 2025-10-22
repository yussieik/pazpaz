import { ref } from 'vue'
import { useRouter } from 'vue-router'
import apiClient from '@/api/client'
import { clearAllDrafts } from '@/utils/draftStorage'
import { createAuthChannel } from '@/utils/crossTabSync'

/**
 * Authentication Composable
 *
 * Provides logout functionality with proper error handling and navigation.
 * Supports cross-tab logout coordination via BroadcastChannel.
 */

const isLoggingOut = ref(false)

// Create auth channel for cross-tab synchronization
// This is created once and shared across all useAuth instances
let authChannel: ReturnType<typeof createAuthChannel> | null = null

function getAuthChannel() {
  if (!authChannel) {
    authChannel = createAuthChannel()
  }
  return authChannel
}

export function useAuth() {
  const router = useRouter()

  /**
   * Logout user by calling backend logout endpoint and redirecting to login
   *
   * Backend will:
   * - Blacklist JWT token in Redis
   * - Clear HttpOnly access_token cookie
   * - Clear csrf_token cookie
   * - Delete CSRF token from Redis
   * - Log audit event
   *
   * Frontend will:
   * - Clear localStorage (including encrypted backups)
   * - Clear sessionStorage
   * - Clear IndexedDB
   * - Reset all Pinia stores
   * - Show loading state during logout
   * - Handle errors gracefully
   * - Redirect to login page on success or error
   *
   * SECURITY H-2: Comprehensive client-side storage cleanup prevents PHI leakage
   */
  async function logout() {
    if (isLoggingOut.value) return

    isLoggingOut.value = true

    try {
      // Mark this tab as initiating logout to prevent "another tab" message
      // This flag is checked before showing cross-tab logout toast
      sessionStorage.setItem('__logout_initiated', 'true')

      // Broadcast logout event to other tabs BEFORE API call
      // This ensures immediate cross-tab logout even if API fails
      const channel = getAuthChannel()
      if (channel.isSupported) {
        channel.postLogout()
      }

      // Call backend logout endpoint
      // Cookies are automatically sent via credentials: 'include' in apiClient
      await apiClient.post('/auth/logout')
    } catch (error) {
      // Log error but still clear client-side storage
      // Even if backend logout fails, we must clear local data
      console.error('Logout error:', error)
    } finally {
      // CRITICAL SECURITY H-2: Clear ALL client-side storage
      // This prevents PHI leakage on shared computers (HIPAA compliance)
      await clearAllClientSideStorage()

      // Redirect to login page
      router.push('/login')
      isLoggingOut.value = false
    }
  }

  /**
   * Clear all client-side storage for HIPAA compliance
   *
   * SECURITY H-2: Prevents PHI leakage when user logs out on shared computer
   *
   * Clears:
   * - localStorage (encrypted session backups, settings, etc.)
   * - sessionStorage (temporary data)
   * - IndexedDB SOAP note drafts (HIPAA-critical: prevents draft note leakage)
   * - IndexedDB (all databases: draft notes, offline data)
   * - All Pinia stores (appointments, clients, auth state)
   */
  async function clearAllClientSideStorage() {
    try {
      // 1. Clear localStorage
      try {
        const localStorageKeysCount = localStorage.length
        localStorage.clear()
        console.info(`[Auth] Cleared localStorage (${localStorageKeysCount} keys)`)
      } catch (error) {
        console.error('[Auth] Failed to clear localStorage:', error)
      }

      // 2. Clear sessionStorage
      try {
        const sessionStorageKeysCount = sessionStorage.length
        sessionStorage.clear()
        console.info(`[Auth] Cleared sessionStorage (${sessionStorageKeysCount} keys)`)
      } catch (error) {
        console.error('[Auth] Failed to clear sessionStorage:', error)
      }

      // 3. Clear SOAP note drafts from IndexedDB (HIPAA-critical)
      try {
        const draftsCleared = await clearAllDrafts()
        if (draftsCleared) {
          console.info('[Auth] Cleared SOAP note drafts from IndexedDB')
        }
      } catch (error) {
        console.error('[Auth] Failed to clear SOAP note drafts:', error)
      }

      // 4. Clear IndexedDB (all databases)
      try {
        if ('indexedDB' in window) {
          const databases = await window.indexedDB.databases()
          const deletePromises = databases
            .filter((db) => db.name) // Only delete databases with names
            .map((db) => {
              return new Promise<void>((resolve, reject) => {
                const deleteRequest = window.indexedDB.deleteDatabase(db.name!)
                deleteRequest.onsuccess = () => {
                  console.info(`[Auth] Deleted IndexedDB: ${db.name}`)
                  resolve()
                }
                deleteRequest.onerror = () => {
                  console.error(`[Auth] Failed to delete IndexedDB: ${db.name}`)
                  reject(deleteRequest.error)
                }
                deleteRequest.onblocked = () => {
                  console.warn(`[Auth] IndexedDB deletion blocked: ${db.name}`)
                  // Resolve anyway, don't block logout
                  resolve()
                }
              })
            })

          await Promise.allSettled(deletePromises)
          console.info(`[Auth] Cleared IndexedDB (${databases.length} databases)`)
        }
      } catch (error) {
        console.error('[Auth] Failed to clear IndexedDB:', error)
      }

      // 5. Reset all Pinia stores
      try {
        // Import stores dynamically to avoid circular dependencies
        const { useAuthStore } = await import('@/stores/auth')
        const { useAppointmentsStore } = await import('@/stores/appointments')
        const { useClientsStore } = await import('@/stores/clients')

        // Reset auth store
        const authStore = useAuthStore()
        authStore.clearUser()

        // Reset appointments store
        const appointmentsStore = useAppointmentsStore()
        appointmentsStore.clearAppointments()

        // Reset clients store
        const clientsStore = useClientsStore()
        clientsStore.clearClients()

        console.info('[Auth] Reset all Pinia stores')
      } catch (error) {
        console.error('[Auth] Failed to reset Pinia stores:', error)
      }

      console.info('[Auth] Client-side storage cleanup complete')
    } catch (error) {
      console.error('[Auth] Client-side storage cleanup failed:', error)
      // Don't throw - logout should still succeed
    }
  }

  return {
    logout,
    isLoggingOut,
  }
}
