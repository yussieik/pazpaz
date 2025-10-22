<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { RouterView } from 'vue-router'
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

/**
 * Root App Component
 *
 * Provides the main application layout with persistent navigation and router outlet.
 * Handles global keyboard shortcuts and help modal.
 * Implements session timeout warning for HIPAA compliance.
 * Displays rate limit banner when API requests are throttled.
 */

// Enable global shortcuts at app level
useGlobalKeyboardShortcuts()

// Session timeout tracking (HIPAA compliance)
const sessionTimeout = useSessionTimeout()

// Session expiration warnings (5-minute and 1-minute warnings)
const sessionExpiration = useSessionExpiration()
const authSessionStore = useAuthSessionStore()

// Global keyboard shortcuts help modal
const showKeyboardHelp = ref(false)

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
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleHelpKey)
})
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

    <AppNavigation />
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
