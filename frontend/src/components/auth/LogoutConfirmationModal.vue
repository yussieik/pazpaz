<template>
  <Teleport to="body">
    <Transition name="modal-backdrop">
      <div
        v-if="visible"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
        role="dialog"
        aria-modal="true"
        aria-labelledby="logout-modal-title"
        aria-describedby="logout-modal-description"
        @click.self="handleCancel"
        @keydown.esc="handleCancel"
      >
        <Transition name="modal-content">
          <div
            v-if="visible"
            ref="modalRef"
            class="mx-4 w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl"
            role="alertdialog"
            tabindex="-1"
          >
            <!-- Warning Icon and Title -->
            <div class="mb-4 flex items-start">
              <svg
                class="mt-0.5 mr-3 h-6 w-6 flex-shrink-0 text-amber-500"
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
                <h3
                  id="logout-modal-title"
                  class="text-lg font-semibold text-slate-900"
                >
                  {{ title }}
                </h3>
              </div>
            </div>

            <!-- Description with Unsaved Changes List -->
            <div id="logout-modal-description" class="mb-6 text-slate-700">
              <p v-if="hasUnsavedChanges" class="mb-3">
                You have unsaved work that will be lost if you logout:
              </p>
              <p v-else class="mb-3">Are you sure you want to logout?</p>

              <!-- Unsaved Changes List -->
              <ul
                v-if="hasUnsavedChanges && unsavedItemDescriptions.length > 0"
                class="mb-4 list-inside list-disc space-y-1 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm"
                role="list"
              >
                <li
                  v-for="(description, index) in unsavedItemDescriptions"
                  :key="index"
                  class="text-amber-900"
                >
                  {{ description }}
                </li>
              </ul>

              <p v-if="hasUnsavedChanges" class="text-sm text-slate-600">
                Your drafts are saved locally and will be permanently deleted when you
                logout.
              </p>
              <p v-else class="text-sm text-slate-600">
                You will need to sign in again to access your workspace.
              </p>
            </div>

            <!-- Action Buttons -->
            <div class="flex gap-3">
              <button
                ref="cancelButtonRef"
                @click="handleCancel"
                :class="[
                  'flex-1 rounded-lg bg-emerald-600 px-4 py-2.5 font-medium text-white',
                  'transition-all duration-200 ease-in-out',
                  'transform hover:scale-102 hover:bg-emerald-700 hover:shadow-lg active:scale-98',
                  'focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:outline-none',
                ]"
                type="button"
              >
                Cancel
              </button>
              <button
                @click="handleLogout"
                :class="[
                  'flex-1 rounded-lg bg-slate-200 px-4 py-2.5 font-medium text-slate-800',
                  'transition-all duration-200 ease-in-out',
                  'focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 focus:outline-none',
                  isLoggingOut
                    ? 'cursor-not-allowed opacity-50'
                    : 'transform hover:scale-102 hover:bg-slate-300 hover:shadow-md active:scale-98',
                ]"
                type="button"
                :disabled="isLoggingOut"
              >
                {{ isLoggingOut ? 'Logging out...' : 'Logout Anyway' }}
              </button>
            </div>

            <!-- HIPAA Compliance Notice (only if unsaved changes) -->
            <p v-if="hasUnsavedChanges" class="mt-4 text-center text-xs text-slate-500">
              For HIPAA compliance, all local data is cleared on logout.
            </p>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'

/**
 * Logout Confirmation Modal
 *
 * Context-aware confirmation dialog before logout.
 * Displays list of unsaved SOAP note drafts if any exist.
 *
 * Two states:
 * 1. With unsaved changes: Shows warning with list of drafts
 * 2. Without unsaved changes: Simple confirmation
 *
 * Features:
 * - Focus trap (modal captures focus, ESC to dismiss)
 * - Accessible (ARIA labels, keyboard navigation)
 * - Auto-focus on cancel button (primary action)
 * - Teleport to body for proper z-index stacking
 * - Backdrop click dismisses modal
 * - Respects prefers-reduced-motion
 *
 * Usage:
 *   <LogoutConfirmationModal
 *     :visible="showLogoutModal"
 *     :has-unsaved-changes="authSessionStore.hasUnsavedChanges"
 *     :unsaved-item-descriptions="authSessionStore.unsavedItemDescriptions"
 *     :is-logging-out="isLoggingOut"
 *     @cancel="showLogoutModal = false"
 *     @logout="handleLogout"
 *   />
 */

interface Props {
  visible: boolean
  hasUnsavedChanges: boolean
  unsavedItemDescriptions: string[]
  isLoggingOut: boolean
}

interface Emits {
  (e: 'cancel'): void
  (e: 'logout'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// Template refs for focus management
const modalRef = ref<HTMLElement | null>(null)
const cancelButtonRef = ref<HTMLElement | null>(null)

/**
 * Computed title based on unsaved changes
 */
const title = computed(() => {
  if (props.hasUnsavedChanges) {
    return 'You Have Unsaved Work'
  }
  return 'Confirm Logout'
})

/**
 * Handle cancel action
 */
function handleCancel() {
  emit('cancel')
}

/**
 * Handle logout action
 */
function handleLogout() {
  emit('logout')
}

/**
 * Focus trap: Focus cancel button when modal opens
 */
watch(
  () => props.visible,
  async (isVisible) => {
    if (isVisible) {
      await nextTick()
      // Focus cancel button (primary action to prevent accidental logout)
      cancelButtonRef.value?.focus()

      // Trap focus within modal
      modalRef.value?.focus()
    }
  }
)
</script>

<style scoped>
/* Backdrop fade transition */
.modal-backdrop-enter-active {
  transition: opacity 200ms ease-out;
}

.modal-backdrop-leave-active {
  transition: opacity 150ms ease-in;
}

.modal-backdrop-enter-from,
.modal-backdrop-leave-to {
  opacity: 0;
}

/* Content scale and fade transition (staggered after backdrop) */
.modal-content-enter-active {
  transition:
    transform 300ms ease-out 50ms,
    opacity 300ms ease-out 50ms;
}

.modal-content-leave-active {
  transition:
    transform 200ms ease-in,
    opacity 200ms ease-in;
}

.modal-content-enter-from {
  transform: scale(0.95);
  opacity: 0;
}

.modal-content-leave-to {
  transform: scale(0.95);
  opacity: 0;
}

/* Respect user's motion preferences */
@media (prefers-reduced-motion: reduce) {
  .modal-backdrop-enter-active,
  .modal-backdrop-leave-active,
  .modal-content-enter-active,
  .modal-content-leave-active {
    transition-duration: 1ms;
    transition-delay: 0ms;
  }

  .modal-content-enter-from,
  .modal-content-leave-to {
    transform: none;
  }

  button {
    transform: none !important;
  }

  button:hover,
  button:active {
    transform: none !important;
  }
}
</style>
