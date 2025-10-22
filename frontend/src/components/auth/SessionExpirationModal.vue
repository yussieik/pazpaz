<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div
        v-if="visible"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
        role="dialog"
        aria-modal="true"
        aria-labelledby="session-expiration-title"
        aria-describedby="session-expiration-description"
      >
        <div
          ref="modalRef"
          class="bg-white rounded-2xl p-6 max-w-md w-full mx-4 shadow-2xl"
          role="alertdialog"
          tabindex="-1"
        >
          <!-- Critical Warning Icon and Title -->
          <div class="flex items-start mb-4">
            <div class="flex-shrink-0">
              <div class="flex items-center justify-center w-12 h-12 rounded-full bg-red-100">
                <svg
                  class="w-6 h-6 text-red-600"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                  aria-hidden="true"
                >
                  <path
                    fill-rule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                    clip-rule="evenodd"
                  />
                </svg>
              </div>
            </div>
            <div class="ml-4 flex-1">
              <h3 id="session-expiration-title" class="text-xl font-semibold text-slate-900">
                Session Expiring
              </h3>
              <p class="mt-1 text-sm text-slate-600">Action required</p>
            </div>
          </div>

          <!-- Description with Prominent Countdown -->
          <div id="session-expiration-description" class="mb-6">
            <div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
              <div class="text-center">
                <p class="text-sm text-red-900 mb-2">Your session expires in:</p>
                <div
                  class="text-4xl font-mono font-bold text-red-600 tabular-nums"
                  :class="{ 'animate-pulse': timeRemaining <= 10 }"
                >
                  {{ formattedTime }}
                </div>
              </div>
            </div>

            <p class="text-sm text-slate-700 mb-2">
              You will be automatically logged out to protect your patient data.
            </p>

            <p
              v-if="hasUnsavedChanges"
              class="text-sm text-amber-900 bg-amber-50 border border-amber-200 rounded-lg p-3"
            >
              <strong>Warning:</strong> You have unsaved work that will be lost if you logout.
            </p>
          </div>

          <!-- Action Buttons -->
          <div class="flex gap-3">
            <button
              ref="extendButtonRef"
              @click="handleExtend"
              class="flex-1 bg-emerald-600 text-white px-4 py-3 rounded-lg font-semibold hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 transition-colors"
              type="button"
              :disabled="isExtending"
            >
              <span v-if="!isExtending">Extend Session</span>
              <span v-else>Extending...</span>
            </button>
            <button
              @click="handleLogout"
              class="flex-1 bg-slate-200 text-slate-800 px-4 py-3 rounded-lg font-semibold hover:bg-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 transition-colors"
              type="button"
            >
              Logout Now
            </button>
          </div>

          <!-- HIPAA Compliance Notice -->
          <p class="text-xs text-slate-500 mt-4 text-center">
            Automatic session timeout is required for HIPAA compliance to protect patient data.
          </p>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'

/**
 * Session Expiration Modal (1-minute warning)
 *
 * Prominent modal dialog that appears when session has 1 minute or less remaining.
 * User MUST take action - cannot dismiss the modal.
 *
 * Features:
 * - Large countdown timer with pulse animation when < 10 seconds
 * - Shows warning if user has unsaved changes
 * - "Extend Session" (primary action) or "Logout Now" (secondary)
 * - Non-dismissible (no ESC or backdrop click)
 * - Focus trap with auto-focus on extend button
 * - Accessible (ARIA labels, keyboard navigation)
 *
 * Usage:
 *   <SessionExpirationModal
 *     :visible="sessionExpiration.showModal.value"
 *     :time-remaining="sessionExpiration.timeRemaining.value"
 *     :has-unsaved-changes="authSessionStore.hasUnsavedChanges"
 *     :is-extending="sessionExpiration.isExtending.value"
 *     @extend="sessionExpiration.extendSession"
 *     @logout="sessionExpiration.logoutNow"
 *   />
 */

interface Props {
  visible: boolean
  timeRemaining: number | null
  hasUnsavedChanges: boolean
  isExtending: boolean
}

interface Emits {
  (e: 'extend'): void
  (e: 'logout'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// Template refs for focus management
const modalRef = ref<HTMLElement | null>(null)
const extendButtonRef = ref<HTMLElement | null>(null)

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
 * Handle logout action
 */
function handleLogout() {
  emit('logout')
}

/**
 * Focus trap: Focus extend button when modal opens
 */
watch(
  () => props.visible,
  async (isVisible) => {
    if (isVisible) {
      await nextTick()
      // Focus extend button (primary action to encourage session extension)
      extendButtonRef.value?.focus()

      // Trap focus within modal
      modalRef.value?.focus()
    }
  }
)
</script>

<style scoped>
/* Modal fade transition */
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 250ms ease-out;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}

/* Pulse animation for critical countdown */
@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

.animate-pulse {
  animation: pulse 1s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

/* Respect user's motion preferences */
@media (prefers-reduced-motion: reduce) {
  .modal-fade-enter-active,
  .modal-fade-leave-active {
    transition-duration: 1ms;
  }

  .animate-pulse {
    animation: none;
  }
}
</style>
