<template>
  <Transition name="banner-slide">
    <div
      v-if="visible"
      class="fixed top-0 left-0 right-0 z-40 bg-amber-50 border-b border-amber-200 shadow-md"
      role="alert"
      aria-live="polite"
      aria-atomic="true"
    >
      <div class="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div class="flex items-center justify-between py-3">
          <!-- Warning Icon + Message -->
          <div class="flex items-center gap-3 flex-1">
            <svg
              class="h-5 w-5 text-amber-600 flex-shrink-0"
              fill="currentColor"
              viewBox="0 0 20 20"
              aria-hidden="true"
            >
              <path
                fill-rule="evenodd"
                d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                clip-rule="evenodd"
              />
            </svg>
            <div class="flex-1">
              <p class="text-sm text-amber-900">
                <span class="font-medium">Session expiring soon.</span>
                Your session will expire in
                <strong class="font-mono">{{ formattedTime }}</strong
                >.
                <button
                  @click="handleExtend"
                  class="underline hover:no-underline focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 rounded"
                  :disabled="isExtending"
                >
                  {{ isExtending ? 'Extending...' : 'Click here to extend' }}
                </button>
              </p>
            </div>
          </div>

          <!-- Dismiss Button -->
          <button
            @click="handleDismiss"
            class="ml-4 rounded-md p-1 text-amber-700 hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 focus:ring-offset-amber-50 transition-colors"
            type="button"
            aria-label="Dismiss warning"
          >
            <svg class="h-5 w-5" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
              <path
                fill-rule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clip-rule="evenodd"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'

/**
 * Session Expiration Banner (5-minute warning)
 *
 * Subtle notification banner that appears at the top of the screen
 * when session has 5 minutes or less remaining.
 *
 * Features:
 * - Shows time remaining with live countdown
 * - "Click here to extend" link to refresh session
 * - Dismissible (user can close banner)
 * - Slide-down animation with reduced motion support
 * - Accessible (ARIA live region, keyboard navigation)
 *
 * Usage:
 *   <SessionExpirationBanner
 *     :visible="sessionExpiration.showBanner.value"
 *     :time-remaining="sessionExpiration.timeRemaining.value"
 *     :is-extending="sessionExpiration.isExtending.value"
 *     @extend="sessionExpiration.extendSession"
 *     @dismiss="sessionExpiration.dismissBanner"
 *   />
 */

interface Props {
  visible: boolean
  timeRemaining: number | null
  isExtending: boolean
}

interface Emits {
  (e: 'extend'): void
  (e: 'dismiss'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

/**
 * Format remaining time as MM:SS
 */
const formattedTime = computed(() => {
  if (props.timeRemaining === null) {
    return '0:00'
  }

  const minutes = Math.floor(props.timeRemaining / 60)
  const seconds = props.timeRemaining % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
})

/**
 * Handle extend session action
 */
function handleExtend() {
  emit('extend')
}

/**
 * Handle dismiss banner action
 */
function handleDismiss() {
  emit('dismiss')
}
</script>

<style scoped>
/* Banner slide-down transition */
.banner-slide-enter-active,
.banner-slide-leave-active {
  transition: transform 300ms cubic-bezier(0.4, 0, 0.2, 1);
}

.banner-slide-enter-from,
.banner-slide-leave-to {
  transform: translateY(-100%);
}

.banner-slide-enter-to,
.banner-slide-leave-from {
  transform: translateY(0);
}

/* Respect user's motion preferences */
@media (prefers-reduced-motion: reduce) {
  .banner-slide-enter-active,
  .banner-slide-leave-active {
    transition-duration: 1ms;
  }
}
</style>
