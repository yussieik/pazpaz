<template>
  <Transition name="slide-down">
    <div
      v-if="rateLimitStore.hasActiveRateLimits"
      class="fixed top-0 right-0 left-0 z-40 border-b border-yellow-200 bg-yellow-50 px-4 py-3 shadow-md"
      role="alert"
      aria-live="polite"
      aria-atomic="true"
    >
      <div class="mx-auto flex max-w-7xl items-center justify-between">
        <!-- Left side: Icon and message -->
        <div class="flex items-center space-x-3">
          <svg
            class="h-5 w-5 flex-shrink-0 text-yellow-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <div>
            <p class="text-sm font-medium text-yellow-800">Rate limit active</p>
            <p class="text-xs text-yellow-700">
              You're sending requests too quickly. Please wait before trying again.
            </p>
          </div>
        </div>

        <!-- Right side: Countdown timers -->
        <div class="flex items-center space-x-4">
          <div
            v-for="limit in rateLimitStore.activeLimits"
            :key="limit.endpoint"
            class="flex items-center space-x-2 text-sm text-yellow-800"
          >
            <span class="font-mono font-semibold">{{
              formatEndpoint(limit.endpoint)
            }}</span>
            <span class="text-yellow-600">-</span>
            <span
              class="font-mono tabular-nums"
              :aria-label="`${getRemainingSeconds(limit.endpoint)} seconds remaining`"
            >
              {{ getRemainingSeconds(limit.endpoint) }}s
            </span>
          </div>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRateLimitStore } from '@/stores/rateLimit'

/**
 * Rate Limit Banner Component
 *
 * Global banner that appears when any API endpoint is rate limited (429).
 * Displays countdown timers for each rate-limited endpoint.
 *
 * HIPAA Compliance: Clear communication about system behavior
 * UX: Prevents user frustration by showing when they can retry
 *
 * Usage:
 *   <RateLimitBanner />
 *
 * Automatically shows/hides based on rate limit store state.
 */

const rateLimitStore = useRateLimitStore()
const remainingSeconds = ref<Map<string, number>>(new Map())

let interval: ReturnType<typeof setInterval> | null = null

/**
 * Get remaining seconds for an endpoint
 */
function getRemainingSeconds(endpoint: string): number {
  return remainingSeconds.value.get(endpoint) || 0
}

/**
 * Format endpoint for display
 * Extracts the last meaningful segment from the endpoint path
 *
 * Examples:
 *   /api/v1/auth/login -> login
 *   /api/v1/clients -> clients
 *   /clients -> clients
 */
function formatEndpoint(endpoint: string): string {
  const parts = endpoint.split('/').filter(Boolean)
  return parts[parts.length - 1] || endpoint
}

/**
 * Update countdown timers every second
 */
function updateCountdowns() {
  rateLimitStore.activeLimits.forEach((limit) => {
    const remaining = rateLimitStore.getRemainingSeconds(limit.endpoint)
    remainingSeconds.value.set(limit.endpoint, remaining)

    // Clean up expired entries
    if (remaining === 0) {
      remainingSeconds.value.delete(limit.endpoint)
    }
  })
}

onMounted(() => {
  updateCountdowns()
  interval = setInterval(updateCountdowns, 1000)
})

onUnmounted(() => {
  if (interval) {
    clearInterval(interval)
  }
})
</script>

<style scoped>
/**
 * Slide down animation for banner entrance/exit
 */
.slide-down-enter-active,
.slide-down-leave-active {
  transition:
    transform 0.3s ease-out,
    opacity 0.3s ease-out;
}

.slide-down-enter-from {
  transform: translateY(-100%);
  opacity: 0;
}

.slide-down-leave-to {
  transform: translateY(-100%);
  opacity: 0;
}

/**
 * Ensure tabular-nums for countdown timer
 * Prevents width shifts as numbers change
 */
.tabular-nums {
  font-variant-numeric: tabular-nums;
}
</style>
