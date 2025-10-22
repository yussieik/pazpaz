<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { RouterView, useRouter } from 'vue-router'
import AppNavigation from '@/components/navigation/AppNavigation.vue'
import KeyboardShortcutsHelp from '@/components/calendar/KeyboardShortcutsHelp.vue'
import SessionTimeoutModal from '@/components/SessionTimeoutModal.vue'
import RateLimitBanner from '@/components/RateLimitBanner.vue'
import SessionExpirationBanner from '@/components/auth/SessionExpirationBanner.vue'
import SessionExpirationModal from '@/components/auth/SessionExpirationModal.vue'
import { useGlobalKeyboardShortcuts } from '@/composables/useGlobalKeyboardShortcuts'
import { useSessionTimeout } from '@/composables/useSessionTimeout'
import { useSessionExpiration } from '@/composables/useSessionExpiration'
import { useAuthSessionStore } from '@/stores/authSession'
import { useAuthStore } from '@/stores/auth'
import { createAuthChannel } from '@/utils/crossTabSync'
import { useToast } from '@/composables/useToast'

/**
 * Root App Component
 *
 * Provides the main application layout with persistent navigation and router outlet.
 * Handles global keyboard shortcuts and help modal.
 * Implements session timeout warning for HIPAA compliance.
 * Displays rate limit banner when API requests are throttled.
 * Coordinates logout across multiple tabs via BroadcastChannel.
 */

// Enable global shortcuts at app level
useGlobalKeyboardShortcuts()

// Session timeout tracking (HIPAA compliance)
const sessionTimeout = useSessionTimeout()

// Session expiration warnings (5-minute and 1-minute warnings)
const sessionExpiration = useSessionExpiration()
const authSessionStore = useAuthSessionStore()
const authStore = useAuthStore()

// Router and auth for cross-tab logout
const router = useRouter()
const toast = useToast()

// Global keyboard shortcuts help modal
const showKeyboardHelp = ref(false)

// Cross-tab authentication synchronization
let authChannel: ReturnType<typeof createAuthChannel> | null = null

/**
 * Handle global '?' key to show keyboard shortcuts help
 */
function handleHelpKey(e: KeyboardEvent) {
  // Note: '?' typically requires Shift key, so we allow shiftKey
  if (e.key === '?' && !e.metaKey && !e.ctrlKey) {
    // Only trigger if not typing in input field
    const target = e.target as HTMLElement
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return

    e.preventDefault()
    showKeyboardHelp.value = true
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleHelpKey)

  // Set up cross-tab authentication synchronization
  authChannel = createAuthChannel()

  // Listen for logout events from other tabs
  authChannel.onLogout(async (message) => {
    console.info('[App] Received logout from another tab', message)

    // Check if this tab initiated the logout
    // If so, don't show the "another tab" message
    const isLocalLogout = sessionStorage.getItem('__logout_initiated') === 'true'

    if (!isLocalLogout) {
      // Only show toast if logout came from another tab
      toast.showInfo('Logged out (session ended in another tab)')
    }

    // Perform logout in this tab (without broadcasting again to avoid loop)
    // We redirect directly instead of calling logout() to avoid double broadcast
    await clearAllClientSideStorage()
    router.push('/login')
  })

  // Optional: Listen for session extension events to keep all tabs in sync
  authChannel.onSessionExtended((message) => {
    console.info('[App] Session extended in another tab', message)
    // Could update session expiration timers here if needed
  })
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleHelpKey)

  // Cleanup auth channel
  if (authChannel) {
    authChannel.close()
    authChannel = null
  }
})

/**
 * Clear all client-side storage (duplicated from useAuth for cross-tab logout)
 * This is needed because we can't call logout() directly from the broadcast handler
 * as it would cause a broadcast loop.
 */
async function clearAllClientSideStorage() {
  try {
    // Clear localStorage
    try {
      localStorage.clear()
    } catch (error) {
      console.error('[App] Failed to clear localStorage:', error)
    }

    // Clear sessionStorage
    try {
      sessionStorage.clear()
    } catch (error) {
      console.error('[App] Failed to clear sessionStorage:', error)
    }

    // Clear IndexedDB (including SOAP drafts)
    try {
      if ('indexedDB' in window) {
        const databases = await window.indexedDB.databases()
        await Promise.allSettled(
          databases
            .filter((db) => db.name)
            .map((db) => {
              return new Promise<void>((resolve) => {
                const deleteRequest = window.indexedDB.deleteDatabase(db.name!)
                deleteRequest.onsuccess = () => resolve()
                deleteRequest.onerror = () => resolve()
                deleteRequest.onblocked = () => resolve()
              })
            }),
        )
      }
    } catch (error) {
      console.error('[App] Failed to clear IndexedDB:', error)
    }
  } catch (error) {
    console.error('[App] Client-side storage cleanup failed:', error)
  }
}
</script>

<template>
  <div id="app" class="min-h-screen bg-gray-50">
    <!-- Session Expiration Banner (5-minute warning) -->
    <SessionExpirationBanner
      :visible="sessionExpiration.showBanner.value"
      :time-remaining="sessionExpiration.timeRemaining.value"
      :is-extending="sessionExpiration.isExtending.value"
      @extend="sessionExpiration.extendSession"
      @dismiss="sessionExpiration.dismissBanner"
    />

    <!-- Rate Limit Banner (appears at top when rate limited) -->
    <RateLimitBanner />

    <!-- Only show navigation when authenticated -->
    <AppNavigation v-if="authStore.isAuthenticated" />
    <RouterView />

    <!-- Global Keyboard Shortcuts Help Modal -->
    <KeyboardShortcutsHelp
      :visible="showKeyboardHelp"
      @update:visible="showKeyboardHelp = $event"
    />

    <!-- Session Timeout Warning Modal (HIPAA Compliance) -->
    <SessionTimeoutModal
      :show-warning="sessionTimeout.showWarning.value"
      :remaining-seconds="sessionTimeout.remainingSeconds.value"
      :refresh-session="sessionTimeout.refreshSession"
      :handle-timeout="sessionTimeout.handleTimeout"
    />

    <!-- Session Expiration Modal (1-minute warning) -->
    <SessionExpirationModal
      :visible="sessionExpiration.showModal.value"
      :time-remaining="sessionExpiration.timeRemaining.value"
      :has-unsaved-changes="authSessionStore.hasUnsavedChanges"
      :is-extending="sessionExpiration.isExtending.value"
      @extend="sessionExpiration.extendSession"
      @logout="sessionExpiration.logoutNow"
    />
  </div>
</template>

<style>
/* Global styles */
body {
  margin: 0;
  padding: 0;
}
</style>
