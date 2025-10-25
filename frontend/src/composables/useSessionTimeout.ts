import { ref, readonly, onMounted, onUnmounted, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import apiClient from '@/api/client'

/**
 * Session Timeout Management Composable
 *
 * HIPAA Compliance: §164.312(a)(2)(iii) - Automatic Logoff
 *
 * Tracks user activity and warns before session expires to prevent data loss.
 * Implements session timeout warning with "Stay logged in" functionality.
 *
 * Features:
 * - Warns user 5 minutes before session expires
 * - Live countdown timer (MM:SS format)
 * - "Stay logged in" button calls session refresh endpoint
 * - "Log out now" button for immediate logout
 * - Automatic logout after countdown expires
 * - Activity tracking (clicks, keyboard, API calls) resets timer
 * - Auto-closes modal if session refreshed by activity
 *
 * Session Parameters:
 * - JWT expiry: 15 minutes of inactivity
 * - Warning threshold: 5 minutes before expiry (at 10-minute mark)
 * - Countdown: 5 minutes (300 seconds)
 *
 * Usage:
 *   const sessionTimeout = useSessionTimeout()
 *
 *   // In template:
 *   <SessionTimeoutModal
 *     :show-warning="sessionTimeout.showWarning.value"
 *     :remaining-seconds="sessionTimeout.remainingSeconds.value"
 *     :refresh-session="sessionTimeout.refreshSession"
 *     :handle-timeout="sessionTimeout.handleTimeout"
 *   />
 */

export interface UseSessionTimeoutReturn {
  showWarning: Readonly<Ref<boolean>>
  remainingSeconds: Readonly<Ref<number>>
  refreshSession: () => Promise<void>
  handleTimeout: () => Promise<void>
  resetTimers: () => void
}

const WARNING_THRESHOLD_MS = 5 * 60 * 1000 // 5 minutes
const SESSION_TIMEOUT_MS = 15 * 60 * 1000 // 15 minutes
const WARNING_DURATION_SECONDS = 300 // 5 minutes

export function useSessionTimeout(): UseSessionTimeoutReturn {
  const authStore = useAuthStore()
  const router = useRouter()

  const showWarning = ref(false)
  const remainingSeconds = ref(0)

  let warningTimer: NodeJS.Timeout | null = null
  let expiryTimer: NodeJS.Timeout | null = null
  let countdownInterval: NodeJS.Timeout | null = null

  /**
   * Track user activity and reset inactivity timers
   * Called on clicks, keyboard events, and successful API calls
   */
  function trackActivity(): void {
    // If warning is showing and user is active, close it and reset
    if (showWarning.value) {
      showWarning.value = false
      stopCountdown()
    }

    resetTimers()
  }

  /**
   * Reset warning and expiry timers
   * Called after activity or successful session refresh
   */
  function resetTimers(): void {
    // Clear existing timers
    if (warningTimer) clearTimeout(warningTimer)
    if (expiryTimer) clearTimeout(expiryTimer)

    // Only set timers if user is authenticated
    if (!authStore.isAuthenticated) {
      return
    }

    // Set warning timer (shows modal 5 minutes before expiry)
    warningTimer = setTimeout(() => {
      showWarning.value = true
      startCountdown()
    }, SESSION_TIMEOUT_MS - WARNING_THRESHOLD_MS)

    // Set expiry timer (auto-logout after full timeout)
    expiryTimer = setTimeout(() => {
      handleTimeout()
    }, SESSION_TIMEOUT_MS)
  }

  /**
   * Start countdown timer for warning modal
   * Decrements remaining seconds every second
   */
  function startCountdown(): void {
    remainingSeconds.value = WARNING_DURATION_SECONDS
    stopCountdown() // Clear any existing countdown

    countdownInterval = setInterval(() => {
      if (remainingSeconds.value > 0) {
        remainingSeconds.value--
      }

      if (remainingSeconds.value <= 0) {
        stopCountdown()
        // Timeout will be handled by expiryTimer
      }
    }, 1000)
  }

  /**
   * Stop countdown timer
   */
  function stopCountdown(): void {
    if (countdownInterval) {
      clearInterval(countdownInterval)
      countdownInterval = null
    }
  }

  /**
   * Refresh session by calling backend endpoint
   * Called when user clicks "Stay logged in" button
   */
  async function refreshSession(): Promise<void> {
    try {
      await apiClient.post('/auth/session/refresh')

      // Close warning modal
      showWarning.value = false
      stopCountdown()

      // Reset timers to extend session
      resetTimers()

      console.debug('[SessionTimeout] Session refreshed successfully')
    } catch (error) {
      console.error('[SessionTimeout] Failed to refresh session:', error)

      // If refresh fails (e.g., 401), session already expired
      // Proceed with logout
      await handleTimeout()
    }
  }

  /**
   * Handle session timeout
   * Called when countdown expires or user clicks "Log out now"
   * Logs out user and redirects to login page with expired message
   */
  async function handleTimeout(): Promise<void> {
    console.debug('[SessionTimeout] Session expired, logging out')

    // Clear all timers
    if (warningTimer) clearTimeout(warningTimer)
    if (expiryTimer) clearTimeout(expiryTimer)
    stopCountdown()

    // Close warning modal
    showWarning.value = false

    // Save current path for redirect after login
    const currentPath = router.currentRoute.value.fullPath

    // Logout user (clears auth state and encrypted backups)
    await authStore.logout()

    // Redirect to login with session expired message
    router.push({
      path: '/login',
      query: {
        message: 'session_expired',
        redirect: currentPath,
      },
    })
  }

  /**
   * Initialize session timeout tracking on mount
   */
  onMounted(() => {
    // Only initialize if user is authenticated
    if (!authStore.isAuthenticated) {
      return
    }

    console.debug('[SessionTimeout] Initializing session timeout tracking')

    // Start timers
    resetTimers()

    // Track user activity via DOM events
    window.addEventListener('click', trackActivity, { passive: true })
    window.addEventListener('keydown', trackActivity, { passive: true })

    // Track activity via API interceptor
    // Response interceptor tracks successful API calls as activity
    const responseInterceptor = apiClient.interceptors.response.use(
      (response) => {
        // Track successful API calls as activity
        if (response.status >= 200 && response.status < 300) {
          trackActivity()
        }
        return response
      },
      (error) => {
        // Don't track errors as activity
        return Promise.reject(error)
      }
    )

    // Store interceptor ID for cleanup
    ;(window as { _sessionTimeoutInterceptor?: number })._sessionTimeoutInterceptor =
      responseInterceptor
  })

  /**
   * Cleanup on unmount
   */
  onUnmounted(() => {
    console.debug('[SessionTimeout] Cleaning up session timeout tracking')

    // Remove event listeners
    window.removeEventListener('click', trackActivity)
    window.removeEventListener('keydown', trackActivity)

    // Clear timers
    if (warningTimer) clearTimeout(warningTimer)
    if (expiryTimer) clearTimeout(expiryTimer)
    stopCountdown()

    // Remove API interceptor
    const interceptorId = (window as { _sessionTimeoutInterceptor?: number })
      ._sessionTimeoutInterceptor
    if (interceptorId !== undefined) {
      apiClient.interceptors.response.eject(interceptorId)
      delete (window as { _sessionTimeoutInterceptor?: number })
        ._sessionTimeoutInterceptor
    }
  })

  return {
    showWarning: readonly(showWarning),
    remainingSeconds: readonly(remainingSeconds),
    refreshSession,
    handleTimeout,
    resetTimers, // Exposed for testing
  }
}
