/**
 * Cross-Tab Authentication Communication
 *
 * Uses BroadcastChannel API to enable communication between tabs.
 * When user authenticates in one tab, other tabs can respond automatically.
 *
 * Use case: Auto-close login tab when authentication succeeds in magic link tab
 */

import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

const CHANNEL_NAME = 'pazpaz_auth'

export interface AuthMessage {
  type: 'AUTH_SUCCESS' | 'AUTH_LOGOUT'
  timestamp: number
  userId?: string
}

export function useCrossTabAuth() {
  const router = useRouter()
  let channel: BroadcastChannel | null = null

  /**
   * Broadcast authentication success to all tabs
   */
  function notifyAuthSuccess(userId?: string) {
    if (!channel) {
      console.debug('[CrossTabAuth] Cannot broadcast: channel not initialized')
      return
    }

    const message: AuthMessage = {
      type: 'AUTH_SUCCESS',
      timestamp: Date.now(),
      userId,
    }

    channel.postMessage(message)
    console.debug('[CrossTabAuth] Broadcasted AUTH_SUCCESS to all tabs')
  }

  /**
   * Broadcast logout to all tabs
   */
  function notifyLogout() {
    if (!channel) return

    const message: AuthMessage = {
      type: 'AUTH_LOGOUT',
      timestamp: Date.now(),
    }

    channel.postMessage(message)
    console.debug('[CrossTabAuth] Broadcasted AUTH_LOGOUT', message)
  }

  /**
   * Handle incoming messages from other tabs
   */
  function handleMessage(event: MessageEvent<AuthMessage>) {
    const { type } = event.data

    console.debug('[CrossTabAuth] Received message from another tab:', type)

    if (type === 'AUTH_SUCCESS') {
      // Another tab authenticated successfully
      const currentPath = window.location.pathname

      // If this is the login page, close it or redirect
      if (currentPath === '/login') {
        console.debug('[CrossTabAuth] Login tab detected, attempting to close')

        // Try to close the window (only works if opened by script)
        window.close()

        // If window.close() didn't work (window not opened by script),
        // redirect to home after a brief delay
        setTimeout(() => {
          // Check if window is still open
          if (!window.closed) {
            console.debug('[CrossTabAuth] Cannot close window, redirecting to home')
            router.push('/')
          }
        }, 500)
      }
    } else if (type === 'AUTH_LOGOUT') {
      // Another tab logged out
      // Could redirect to login, clear local state, etc.
      console.debug('[CrossTabAuth] Logout detected in another tab')
    }
  }

  /**
   * Initialize BroadcastChannel on mount
   */
  onMounted(() => {
    // Check if BroadcastChannel is supported
    if (typeof BroadcastChannel === 'undefined') {
      console.warn('[CrossTabAuth] BroadcastChannel API not supported in this browser')
      return
    }

    try {
      channel = new BroadcastChannel(CHANNEL_NAME)
      channel.addEventListener('message', handleMessage)
      console.debug('[CrossTabAuth] Channel initialized')
    } catch (error) {
      console.error('[CrossTabAuth] Failed to initialize channel', error)
    }
  })

  /**
   * Cleanup on unmount
   */
  onUnmounted(() => {
    if (channel) {
      channel.removeEventListener('message', handleMessage)
      channel.close()
      channel = null
      console.debug('[CrossTabAuth] Channel closed')
    }
  })

  return {
    notifyAuthSuccess,
    notifyLogout,
  }
}
