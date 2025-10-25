import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthSessionStore } from '@/stores/authSession'
import { useAuth } from '@/composables/useAuth'
import apiClient from '@/api/client'

/**
 * Session Expiration Composable
 *
 * Provides proactive session expiration warnings at two thresholds:
 * - 5 minutes remaining: Subtle banner notification
 * - 1 minute remaining: Prominent modal warning
 *
 * Features:
 * - Interval-based checking (every 10 seconds)
 * - Auto-logout when session expires
 * - Session extension via API call
 * - Cleanup on unmount
 *
 * Usage:
 *   const sessionExpiration = useSessionExpiration()
 *   // Use in template:
 *   // sessionExpiration.showBanner
 *   // sessionExpiration.showModal
 *   // sessionExpiration.extendSession()
 */

const FIVE_MINUTES_IN_SECONDS = 5 * 60
const ONE_MINUTE_IN_SECONDS = 1 * 60
const CHECK_INTERVAL_MS = 10 * 1000 // Check every 10 seconds

export function useSessionExpiration() {
  const router = useRouter()
  const authSessionStore = useAuthSessionStore()
  const { logout } = useAuth()

  // State
  const showBanner = ref(false)
  const showModal = ref(false)
  const timeRemaining = ref<number | null>(null)
  const isExtending = ref(false)

  let checkInterval: ReturnType<typeof setInterval> | null = null

  /**
   * Check session expiration status
   * Called every 10 seconds
   */
  function checkSessionExpiration() {
    const remaining = authSessionStore.getTimeRemaining()

    if (remaining === null) {
      // No session expiration set
      showBanner.value = false
      showModal.value = false
      timeRemaining.value = null
      return
    }

    timeRemaining.value = remaining

    // Session has expired - auto logout
    if (authSessionStore.isSessionExpired()) {
      console.debug('[SessionExpiration] Session expired, logging out')
      handleExpiredSession()
      return
    }

    // 1 minute remaining - show modal
    if (remaining <= ONE_MINUTE_IN_SECONDS) {
      showModal.value = true
      showBanner.value = false
      console.debug('[SessionExpiration] Showing 1-minute warning modal')
      return
    }

    // 5 minutes remaining - show banner
    if (remaining <= FIVE_MINUTES_IN_SECONDS) {
      showBanner.value = true
      showModal.value = false
      console.debug('[SessionExpiration] Showing 5-minute warning banner')
      return
    }

    // More than 5 minutes remaining - hide warnings
    showBanner.value = false
    showModal.value = false
  }

  /**
   * Extend session by calling backend API
   * Updates sessionExpiresAt in store
   */
  async function extendSession(): Promise<boolean> {
    if (isExtending.value) {
      return false
    }

    isExtending.value = true

    try {
      // Call extend-session endpoint
      await apiClient.post('/auth/extend-session')

      // Update session expiration (backend returns new expiration in response)
      // For now, add 15 minutes from current time
      const newExpiry = new Date(Date.now() + 15 * 60 * 1000)
      authSessionStore.setSessionExpiry(newExpiry)

      // Hide warnings
      showBanner.value = false
      showModal.value = false

      console.debug('[SessionExpiration] Session extended successfully')
      return true
    } catch (error) {
      console.error('[SessionExpiration] Failed to extend session:', error)

      // If extension fails, logout
      await handleExpiredSession()
      return false
    } finally {
      isExtending.value = false
    }
  }

  /**
   * Dismiss banner (5-minute warning only)
   * Modal cannot be dismissed - user must extend or logout
   */
  function dismissBanner() {
    showBanner.value = false
    console.debug('[SessionExpiration] Banner dismissed by user')
  }

  /**
   * Handle expired session - logout and redirect
   */
  async function handleExpiredSession() {
    // Clear interval to prevent further checks
    if (checkInterval) {
      clearInterval(checkInterval)
      checkInterval = null
    }

    // Hide warnings
    showBanner.value = false
    showModal.value = false

    // Logout and redirect to login with message
    await logout()
    router.push({
      path: '/login',
      query: {
        message: 'session_expired',
      },
    })
  }

  /**
   * Logout immediately (user clicks "Logout Now" in modal)
   */
  async function logoutNow() {
    await handleExpiredSession()
  }

  /**
   * Initialize interval-based checking
   */
  onMounted(() => {
    // Start checking session expiration every 10 seconds
    checkInterval = setInterval(checkSessionExpiration, CHECK_INTERVAL_MS)
    console.debug('[SessionExpiration] Started session expiration monitoring')

    // Run initial check immediately
    checkSessionExpiration()
  })

  /**
   * Cleanup on unmount
   */
  onUnmounted(() => {
    if (checkInterval) {
      clearInterval(checkInterval)
      checkInterval = null
      console.debug('[SessionExpiration] Stopped session expiration monitoring')
    }
  })

  return {
    // State
    showBanner,
    showModal,
    timeRemaining,
    isExtending,

    // Actions
    extendSession,
    dismissBanner,
    logoutNow,
  }
}
