/**
 * Cross-Tab Synchronization Utility
 *
 * Coordinates logout and authentication state across multiple browser tabs/windows
 * using the BroadcastChannel API.
 *
 * Features:
 * - Broadcasts logout events to all tabs
 * - Listens for logout events from other tabs
 * - Prevents zombie sessions where one tab stays logged in after logout
 * - Supports session extension broadcasting
 *
 * Usage:
 * ```ts
 * const channel = createAuthChannel()
 * channel.postLogout()
 * channel.onLogout(() => {
 *   // Handle logout in this tab
 * })
 * channel.close() // Cleanup on unmount
 * ```
 */

/**
 * Message types for cross-tab authentication events
 */
export interface AuthMessage {
  type: 'logout' | 'login' | 'session_extended'
  timestamp: number
  userId?: string
  workspaceId?: string
  tabId: string // Unique identifier for the originating tab
}

/**
 * Callback type for handling authentication messages
 */
type AuthMessageHandler = (message: AuthMessage) => void

/**
 * AuthChannel interface for cross-tab communication
 */
export interface AuthChannel {
  /**
   * Post a logout message to all other tabs
   */
  postLogout: (userId?: string, workspaceId?: string) => void

  /**
   * Post a login message to all other tabs
   */
  postLogin: (userId?: string, workspaceId?: string) => void

  /**
   * Post a session extended message to all other tabs
   */
  postSessionExtended: (userId?: string, workspaceId?: string) => void

  /**
   * Register a handler for logout messages from other tabs
   */
  onLogout: (handler: AuthMessageHandler) => void

  /**
   * Register a handler for login messages from other tabs
   */
  onLogin: (handler: AuthMessageHandler) => void

  /**
   * Register a handler for session extended messages from other tabs
   */
  onSessionExtended: (handler: AuthMessageHandler) => void

  /**
   * Close the BroadcastChannel and cleanup
   */
  close: () => void

  /**
   * Check if BroadcastChannel is supported
   */
  isSupported: boolean
}

/**
 * Generate a unique tab ID for this session
 */
function generateTabId(): string {
  return `tab_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`
}

/**
 * Create an authentication broadcast channel for cross-tab synchronization
 *
 * @returns AuthChannel instance or a no-op fallback if BroadcastChannel is not supported
 */
export function createAuthChannel(): AuthChannel {
  // Check if BroadcastChannel is supported
  const isSupported = typeof BroadcastChannel !== 'undefined'

  if (!isSupported) {
    // Return no-op fallback for older browsers
    console.warn('[CrossTabSync] BroadcastChannel not supported. Cross-tab sync disabled.')
    return {
      postLogout: () => {},
      postLogin: () => {},
      postSessionExtended: () => {},
      onLogout: () => {},
      onLogin: () => {},
      onSessionExtended: () => {},
      close: () => {},
      isSupported: false,
    }
  }

  // Create the BroadcastChannel
  const channel = new BroadcastChannel('pazpaz_auth')
  const tabId = generateTabId()

  // Message handlers
  const logoutHandlers: AuthMessageHandler[] = []
  const loginHandlers: AuthMessageHandler[] = []
  const sessionExtendedHandlers: AuthMessageHandler[] = []

  /**
   * Handle incoming messages from other tabs
   */
  function handleMessage(event: MessageEvent<AuthMessage>) {
    const message = event.data

    // Ignore messages from this tab (prevent echo)
    if (message.tabId === tabId) {
      return
    }

    // Validate message structure
    if (!message.type || !message.timestamp) {
      console.warn('[CrossTabSync] Invalid message received:', message)
      return
    }

    // Route to appropriate handlers
    switch (message.type) {
      case 'logout':
        logoutHandlers.forEach((handler) => handler(message))
        break
      case 'login':
        loginHandlers.forEach((handler) => handler(message))
        break
      case 'session_extended':
        sessionExtendedHandlers.forEach((handler) => handler(message))
        break
      default:
        console.warn('[CrossTabSync] Unknown message type:', message.type)
    }
  }

  // Listen for messages
  channel.addEventListener('message', handleMessage)

  return {
    postLogout(userId?: string, workspaceId?: string) {
      const message: AuthMessage = {
        type: 'logout',
        timestamp: Date.now(),
        userId,
        workspaceId,
        tabId,
      }
      channel.postMessage(message)
      console.info('[CrossTabSync] Posted logout message', message)
    },

    postLogin(userId?: string, workspaceId?: string) {
      const message: AuthMessage = {
        type: 'login',
        timestamp: Date.now(),
        userId,
        workspaceId,
        tabId,
      }
      channel.postMessage(message)
      console.info('[CrossTabSync] Posted login message', message)
    },

    postSessionExtended(userId?: string, workspaceId?: string) {
      const message: AuthMessage = {
        type: 'session_extended',
        timestamp: Date.now(),
        userId,
        workspaceId,
        tabId,
      }
      channel.postMessage(message)
      console.info('[CrossTabSync] Posted session extended message', message)
    },

    onLogout(handler: AuthMessageHandler) {
      logoutHandlers.push(handler)
    },

    onLogin(handler: AuthMessageHandler) {
      loginHandlers.push(handler)
    },

    onSessionExtended(handler: AuthMessageHandler) {
      sessionExtendedHandlers.push(handler)
    },

    close() {
      channel.removeEventListener('message', handleMessage)
      channel.close()
      console.info('[CrossTabSync] Channel closed')
    },

    isSupported: true,
  }
}
