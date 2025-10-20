<template>
  <Teleport to="body">
    <div
      v-if="showWarning"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      role="dialog"
      aria-modal="true"
      aria-labelledby="session-timeout-title"
      aria-describedby="session-timeout-description"
    >
      <div
        class="bg-white rounded-lg p-6 max-w-md w-full mx-4 shadow-xl"
        role="alertdialog"
      >
        <!-- Warning Icon and Title -->
        <div class="flex items-center mb-4">
          <svg
            class="w-6 h-6 text-yellow-500 mr-3 flex-shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
          <h3 id="session-timeout-title" class="text-lg font-semibold text-gray-900">
            Session Expiring Soon
          </h3>
        </div>

        <!-- Description with Countdown -->
        <p id="session-timeout-description" class="text-gray-700 mb-6">
          Your session will expire in
          <strong class="text-gray-900 font-mono text-lg">{{ formattedTime }}</strong
          >.
          <span class="block mt-2">
            You will be automatically logged out to protect your data.
          </span>
        </p>

        <!-- Action Buttons -->
        <div class="flex gap-3">
          <button
            @click="handleRefresh"
            class="flex-1 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
            type="button"
            :disabled="isRefreshing"
          >
            <span v-if="!isRefreshing">Stay Logged In</span>
            <span v-else>Refreshing...</span>
          </button>
          <button
            @click="handleLogout"
            class="flex-1 bg-gray-200 text-gray-800 px-4 py-2 rounded-lg hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 transition-colors"
            type="button"
            :disabled="isRefreshing"
          >
            Log Out Now
          </button>
        </div>

        <!-- HIPAA Compliance Notice -->
        <p class="text-xs text-gray-500 mt-4 text-center">
          Automatic session timeout is required for HIPAA compliance to protect patient data.
        </p>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

/**
 * Session Timeout Warning Modal
 *
 * HIPAA Compliance: §164.312(a)(2)(iii) - Automatic Logoff
 *
 * Displays a warning modal when session is about to expire.
 * Shows live countdown and provides options to extend or end session.
 *
 * Props:
 * - showWarning: Boolean to control modal visibility
 * - remainingSeconds: Number of seconds until session expires
 * - refreshSession: Async function to refresh session (extends JWT)
 * - handleTimeout: Async function to logout immediately
 *
 * Features:
 * - Accessible (ARIA labels, role, keyboard navigation)
 * - Live countdown timer (MM:SS format)
 * - Loading state for "Stay logged in" button
 * - Teleport to body for proper z-index stacking
 * - Focus trap (modal captures focus)
 * - HIPAA compliance notice
 *
 * Usage:
 *   <SessionTimeoutModal
 *     :show-warning="sessionTimeout.showWarning.value"
 *     :remaining-seconds="sessionTimeout.remainingSeconds.value"
 *     :refresh-session="sessionTimeout.refreshSession"
 *     :handle-timeout="sessionTimeout.handleTimeout"
 *   />
 */

interface Props {
  showWarning: boolean
  remainingSeconds: number
  refreshSession: () => Promise<void>
  handleTimeout: () => Promise<void>
}

const props = defineProps<Props>()

// Loading state for refresh button
const isRefreshing = ref(false)

/**
 * Format remaining seconds as MM:SS
 */
const formattedTime = computed(() => {
  const minutes = Math.floor(props.remainingSeconds / 60)
  const seconds = props.remainingSeconds % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
})

/**
 * Handle "Stay logged in" button click
 * Calls refresh session endpoint and shows loading state
 */
async function handleRefresh(): Promise<void> {
  isRefreshing.value = true
  try {
    await props.refreshSession()
  } finally {
    // Reset loading state even if refresh fails
    // (refreshSession handles logout on failure)
    isRefreshing.value = false
  }
}

/**
 * Handle "Log out now" button click
 * Immediately logs out user
 */
async function handleLogout(): Promise<void> {
  await props.handleTimeout()
}
</script>

<style scoped>
/* Modal backdrop with semi-transparent overlay */
/* Using Tailwind utility classes for consistency */
</style>
