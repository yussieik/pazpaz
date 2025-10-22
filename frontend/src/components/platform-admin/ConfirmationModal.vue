<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'

interface Props {
  visible: boolean
  title: string
  message: string
  confirmText?: string
  confirmStyle?: 'danger' | 'primary'
  showReasonField?: boolean
  reasonLabel?: string
  reasonPlaceholder?: string
  reasonRequired?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  confirmText: 'Confirm',
  confirmStyle: 'primary',
  showReasonField: false,
  reasonLabel: 'Reason',
  reasonPlaceholder: 'Enter reason...',
  reasonRequired: false,
})

const emit = defineEmits<{
  confirm: [reason?: string]
  cancel: []
}>()

const reason = ref('')
const modalRef = ref<HTMLDivElement | null>(null)
const firstFocusableElement = ref<HTMLElement | null>(null)
const lastFocusableElement = ref<HTMLElement | null>(null)

// Reset reason when modal visibility changes
watch(() => props.visible, (isVisible) => {
  if (isVisible) {
    reason.value = ''
    // Setup focus trap on next tick to ensure DOM is rendered
    setTimeout(setupFocusTrap, 0)
  }
})

function setupFocusTrap() {
  if (modalRef.value) {
    const focusableElements = modalRef.value.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
    if (focusableElements.length > 0) {
      firstFocusableElement.value = focusableElements[0]
      lastFocusableElement.value = focusableElements[focusableElements.length - 1]
      firstFocusableElement.value?.focus()
    }
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleEscapeKey)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleEscapeKey)
})

function handleEscapeKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.visible) {
    handleCancel()
  }
}

function handleCancel() {
  reason.value = ''
  emit('cancel')
}

function handleConfirm() {
  // Validate reason if required
  if (props.showReasonField && props.reasonRequired && !reason.value.trim()) {
    return
  }

  emit('confirm', props.showReasonField ? reason.value : undefined)
  reason.value = ''
}

function handleTabKey(e: KeyboardEvent) {
  if (e.key !== 'Tab') return

  if (e.shiftKey) {
    // Shift + Tab
    if (document.activeElement === firstFocusableElement.value) {
      e.preventDefault()
      lastFocusableElement.value?.focus()
    }
  } else {
    // Tab
    if (document.activeElement === lastFocusableElement.value) {
      e.preventDefault()
      firstFocusableElement.value?.focus()
    }
  }
}

const confirmButtonClass = props.confirmStyle === 'danger'
  ? 'bg-red-600 text-white hover:bg-red-700 focus:ring-red-500'
  : 'bg-emerald-600 text-white hover:bg-emerald-700 focus:ring-emerald-500'
</script>

<template>
  <Transition name="modal">
    <div
      v-if="visible"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4"
      @click.self="handleCancel"
      @keydown="handleTabKey"
      role="dialog"
      aria-modal="true"
      :aria-labelledby="`modal-title-${title}`"
    >
      <div ref="modalRef" class="w-full max-w-md rounded-xl bg-white p-4 shadow-xl sm:p-6">
        <!-- Header -->
        <div class="mb-4 flex items-start justify-between">
          <div class="flex items-center">
            <div
              v-if="confirmStyle === 'danger'"
              class="mr-3 flex h-10 w-10 items-center justify-center rounded-full bg-red-100"
              aria-hidden="true"
            >
              <svg
                class="h-6 w-6 text-red-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                />
              </svg>
            </div>
            <h2 :id="`modal-title-${title}`" class="text-xl font-semibold text-slate-900">
              {{ title }}
            </h2>
          </div>
          <button
            @click="handleCancel"
            class="rounded-lg p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
            aria-label="Close modal"
            type="button"
          >
            <svg
              class="h-6 w-6"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        <!-- Message -->
        <p class="mb-4 text-sm text-slate-700">{{ message }}</p>

        <!-- Reason Field (Optional) -->
        <div v-if="showReasonField" class="mb-4">
          <label
            :for="`reason-${title}`"
            class="mb-1 block text-sm font-medium text-slate-700"
          >
            {{ reasonLabel }}
            <span v-if="reasonRequired" class="text-red-600" aria-label="required">*</span>
          </label>
          <textarea
            :id="`reason-${title}`"
            v-model="reason"
            :placeholder="reasonPlaceholder"
            :required="reasonRequired"
            rows="3"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm transition focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            :aria-required="reasonRequired"
          />
        </div>

        <!-- Actions -->
        <div class="flex flex-col gap-3 sm:flex-row sm:space-x-3 sm:gap-0">
          <button
            type="button"
            @click="handleCancel"
            class="flex-1 rounded-lg border border-slate-300 px-4 py-2 font-medium text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-slate-500 focus:ring-offset-2"
          >
            Cancel
          </button>
          <button
            type="button"
            @click="handleConfirm"
            :disabled="showReasonField && reasonRequired && !reason.trim()"
            :class="[
              confirmButtonClass,
              'flex-1 rounded-lg px-4 py-2 font-semibold transition focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50'
            ]"
          >
            {{ confirmText }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* Modal transition */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

/* Respect user's motion preferences for accessibility */
@media (prefers-reduced-motion: reduce) {
  .modal-enter-active,
  .modal-leave-active {
    transition: none !important;
  }
}
</style>
