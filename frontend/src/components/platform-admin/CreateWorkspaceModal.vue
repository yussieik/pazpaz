<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import type { InviteTherapistRequest } from '@/api/generated'

// Props for error and loading state from parent composable
defineProps<{
  error?: string | null
  isLoading?: boolean
}>()

const emit = defineEmits<{
  close: []
  submit: [data: InviteTherapistRequest]
}>()

const form = ref<InviteTherapistRequest>({
  workspace_name: '',
  therapist_email: '',
  therapist_full_name: '',
})

const validationError = ref<string | null>(null)

// Focus trap for accessibility
const modalRef = ref<HTMLDivElement | null>(null)
const firstFocusableElement = ref<HTMLElement | null>(null)
const lastFocusableElement = ref<HTMLElement | null>(null)

onMounted(() => {
  // Set up focus trap
  if (modalRef.value) {
    const focusableElements = modalRef.value.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
    if (focusableElements.length > 0) {
      firstFocusableElement.value = focusableElements[0] ?? null
      lastFocusableElement.value =
        focusableElements[focusableElements.length - 1] ?? null
      firstFocusableElement.value?.focus()
    }
  }

  // Add escape key listener
  document.addEventListener('keydown', handleEscapeKey)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleEscapeKey)
})

function handleEscapeKey(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    handleClose()
  }
}

function handleClose() {
  // Clear form and validation error state when closing
  form.value = {
    workspace_name: '',
    therapist_email: '',
    therapist_full_name: '',
  }
  validationError.value = null
  emit('close')
}

function handleSubmit() {
  // Clear previous validation error
  validationError.value = null

  // Client-side validation (HTML5 required attributes handle most validation)
  if (
    !form.value.workspace_name.trim() ||
    !form.value.therapist_email.trim() ||
    !form.value.therapist_full_name.trim()
  ) {
    validationError.value = 'All fields are required'
    return
  }

  // Basic email validation
  if (!form.value.therapist_email.includes('@')) {
    validationError.value = 'Please enter a valid email address'
    return
  }

  // Emit submit event - parent handles the actual API call
  emit('submit', form.value)
}

// Handle tab key for focus trap
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
</script>

<template>
  <div
    class="bg-opacity-50 fixed inset-0 z-50 flex items-center justify-center bg-black p-4"
    @click.self="handleClose"
    @keydown="handleTabKey"
    role="dialog"
    aria-modal="true"
    aria-labelledby="invite-modal-title"
  >
    <div
      ref="modalRef"
      class="w-full max-w-md rounded-lg bg-white p-4 shadow-xl sm:p-6"
    >
      <!-- Header -->
      <div class="mb-4 flex items-center justify-between">
        <h2 id="invite-modal-title" class="text-xl font-semibold text-slate-900">
          Invite New Therapist
        </h2>
        <button
          @click="handleClose"
          class="rounded-lg p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:outline-none"
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

      <!-- Form -->
      <form @submit.prevent="handleSubmit" class="space-y-4">
        <!-- Workspace Name -->
        <div>
          <label
            for="workspace-name"
            class="mb-1 block text-sm font-medium text-slate-700"
          >
            Workspace Name <span class="text-red-600" aria-label="required">*</span>
          </label>
          <input
            id="workspace-name"
            v-model="form.workspace_name"
            type="text"
            required
            :disabled="isLoading"
            placeholder="Sarah's Massage Therapy"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-100"
            aria-required="true"
            aria-describedby="workspace-name-help"
          />
          <p id="workspace-name-help" class="mt-1 text-xs text-slate-500">
            The therapist's practice name
          </p>
        </div>

        <!-- Therapist Email -->
        <div>
          <label
            for="therapist-email"
            class="mb-1 block text-sm font-medium text-slate-700"
          >
            Therapist Email <span class="text-red-600" aria-label="required">*</span>
          </label>
          <input
            id="therapist-email"
            v-model="form.therapist_email"
            type="email"
            required
            :disabled="isLoading"
            placeholder="sarah@example.com"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-100"
            aria-required="true"
          />
        </div>

        <!-- Therapist Full Name -->
        <div>
          <label
            for="therapist-full-name"
            class="mb-1 block text-sm font-medium text-slate-700"
          >
            Full Name <span class="text-red-600" aria-label="required">*</span>
          </label>
          <input
            id="therapist-full-name"
            v-model="form.therapist_full_name"
            type="text"
            required
            :disabled="isLoading"
            placeholder="Sarah Chen"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-100"
            aria-required="true"
          />
        </div>

        <!-- What Happens Next Info Box -->
        <div
          class="rounded-lg border border-blue-200 bg-blue-50 p-3"
          role="region"
          aria-label="What happens next"
        >
          <p class="text-sm font-semibold text-blue-800">What happens next:</p>
          <ul class="mt-2 space-y-1 text-xs text-blue-700">
            <li class="flex items-start">
              <svg
                class="mt-0.5 mr-1.5 h-3 w-3 flex-shrink-0 text-blue-600"
                fill="currentColor"
                viewBox="0 0 20 20"
                aria-hidden="true"
              >
                <path
                  fill-rule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clip-rule="evenodd"
                />
              </svg>
              Workspace created
            </li>
            <li class="flex items-start">
              <svg
                class="mt-0.5 mr-1.5 h-3 w-3 flex-shrink-0 text-blue-600"
                fill="currentColor"
                viewBox="0 0 20 20"
                aria-hidden="true"
              >
                <path
                  fill-rule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clip-rule="evenodd"
                />
              </svg>
              Invitation email sent to therapist
            </li>
            <li class="flex items-start">
              <svg
                class="mt-0.5 mr-1.5 h-3 w-3 flex-shrink-0 text-blue-600"
                fill="currentColor"
                viewBox="0 0 20 20"
                aria-hidden="true"
              >
                <path
                  fill-rule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clip-rule="evenodd"
                />
              </svg>
              Therapist clicks link to activate account (valid for 7 days)
            </li>
            <li class="flex items-start">
              <svg
                class="mt-0.5 mr-1.5 h-3 w-3 flex-shrink-0 text-blue-600"
                fill="currentColor"
                viewBox="0 0 20 20"
                aria-hidden="true"
              >
                <path
                  fill-rule="evenodd"
                  d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                  clip-rule="evenodd"
                />
              </svg>
              They log in and start using PazPaz
            </li>
          </ul>
        </div>

        <!-- Error Message -->
        <div
          v-if="validationError || error"
          class="rounded-lg border border-red-200 bg-red-50 p-3"
          role="alert"
        >
          <div class="flex items-start">
            <svg
              class="mt-0.5 mr-3 h-5 w-5 flex-shrink-0 text-red-600"
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
            <p class="text-sm font-medium text-red-800">
              {{ validationError || error }}
            </p>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex flex-col gap-3 pt-4 sm:flex-row sm:gap-0 sm:space-x-3">
          <button
            type="button"
            @click="handleClose"
            :disabled="isLoading"
            class="flex-1 rounded-lg border border-slate-300 px-4 py-2 font-medium text-slate-700 transition hover:bg-slate-50 focus:ring-2 focus:ring-slate-500 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            :disabled="isLoading"
            class="flex-1 rounded-lg bg-emerald-600 px-4 py-2 font-semibold text-white transition hover:bg-emerald-700 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
          >
            <span v-if="isLoading" class="flex items-center justify-center">
              <svg
                class="mr-2 -ml-1 h-4 w-4 animate-spin text-white"
                fill="none"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <circle
                  class="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  stroke-width="4"
                ></circle>
                <path
                  class="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                ></path>
              </svg>
              Sending...
            </span>
            <span v-else>Send Invitation</span>
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
/* Respect user's motion preferences for accessibility */
@media (prefers-reduced-motion: reduce) {
  .transition,
  .animate-spin {
    animation: none !important;
    transition: none !important;
  }
}
</style>
