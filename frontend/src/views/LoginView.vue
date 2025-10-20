<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import apiClient from '@/api/client'

const route = useRoute()

const email = ref('')
const isLoading = ref(false)
const error = ref<string | null>(null)
const success = ref(false)
const emailInputRef = ref<HTMLInputElement | null>(null)

// Check if user was redirected due to session expiration
const sessionExpiredMessage = computed(() => {
  return route.query.message === 'session_expired'
})

onMounted(() => {
  // Focus email input on mount for keyboard-first UX
  emailInputRef.value?.focus()

  // Check if there's an error from failed auth verification
  if (route.query.error === 'invalid_link') {
    error.value = 'Invalid or expired magic link. Please request a new one.'
  }
})

async function requestMagicLink() {
  // Client-side validation
  if (!email.value || !email.value.includes('@')) {
    error.value = 'Please enter a valid email address'
    return
  }

  isLoading.value = true
  error.value = null
  success.value = false

  try {
    // Request magic link from backend
    // Note: Backend returns generic success to prevent email enumeration
    await apiClient.post('/auth/magic-link', {
      email: email.value.toLowerCase().trim(),
    })

    success.value = true
  } catch (err: unknown) {
    // Handle specific error cases
    const axiosError = err as { response?: { status: number } }
    if (axiosError.response?.status === 429) {
      error.value = 'Too many requests. Please try again later.'
    } else if (axiosError.response?.status === 422) {
      error.value = 'Please enter a valid email address'
    } else {
      error.value = 'An error occurred. Please try again.'
    }
    console.error('Magic link request failed:', err)
  } finally {
    isLoading.value = false
  }
}

function handleSubmit() {
  requestMagicLink()
}
</script>

<template>
  <div
    class="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 px-4"
  >
    <div class="w-full max-w-md">
      <!-- Logo/Branding -->
      <div class="mb-8 text-center">
        <h1 class="text-4xl font-bold text-emerald-600">PazPaz</h1>
        <p class="mt-2 text-slate-600">Practice Management for Therapists</p>
      </div>

      <!-- Login Card -->
      <div class="rounded-2xl bg-white p-8 shadow-xl">
        <h2 class="mb-6 text-2xl font-semibold text-slate-900">Sign In</h2>

        <!-- Session Expired Warning -->
        <div
          v-if="sessionExpiredMessage"
          class="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-4"
          role="alert"
        >
          <div class="flex items-start">
            <svg
              class="mt-0.5 mr-3 h-5 w-5 text-amber-600"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fill-rule="evenodd"
                d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                clip-rule="evenodd"
              />
            </svg>
            <div class="flex-1">
              <h3 class="font-semibold text-amber-900">Session Expired</h3>
              <p class="mt-1 text-sm text-amber-700">
                Your session has expired due to inactivity. Please sign in again to
                continue.
              </p>
            </div>
          </div>
        </div>

        <!-- Success Message -->
        <div
          v-if="success"
          class="mb-6 rounded-lg border border-emerald-200 bg-emerald-50 p-4"
          role="alert"
        >
          <div class="flex items-start">
            <svg
              class="mt-0.5 mr-3 h-5 w-5 text-emerald-600"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fill-rule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                clip-rule="evenodd"
              />
            </svg>
            <div class="flex-1">
              <h3 class="font-semibold text-emerald-900">Check your email</h3>
              <p class="mt-1 text-sm text-emerald-700">
                We've sent a login link to <strong>{{ email }}</strong
                >. Click the link in the email to sign in.
              </p>
              <p class="mt-2 text-xs text-emerald-600">
                The link will expire in 10 minutes.
              </p>
            </div>
          </div>
        </div>

        <!-- Error Message -->
        <div
          v-if="error"
          class="mb-6 rounded-lg border border-red-200 bg-red-50 p-4"
          role="alert"
        >
          <div class="flex items-start">
            <svg
              class="mt-0.5 mr-3 h-5 w-5 text-red-600"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fill-rule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clip-rule="evenodd"
              />
            </svg>
            <p class="text-sm text-red-700">{{ error }}</p>
          </div>
        </div>

        <!-- Login Form -->
        <form @submit.prevent="handleSubmit" class="space-y-6">
          <div>
            <label for="email" class="mb-2 block text-sm font-medium text-slate-700">
              Email Address
            </label>
            <input
              id="email"
              ref="emailInputRef"
              v-model="email"
              type="email"
              autocomplete="email"
              required
              :disabled="isLoading || success"
              class="block w-full rounded-lg border border-slate-300 px-4 py-3 text-slate-900 placeholder-slate-400 transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-100"
              placeholder="you@example.com"
              aria-required="true"
              aria-describedby="email-description"
            />
            <p id="email-description" class="mt-2 text-xs text-slate-500">
              We'll send you a magic link to sign in
            </p>
          </div>

          <button
            type="submit"
            :disabled="isLoading || success || !email"
            class="w-full rounded-lg bg-emerald-600 px-4 py-3 font-semibold text-white transition hover:bg-emerald-700 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            <span v-if="isLoading" class="flex items-center justify-center">
              <svg
                class="mr-3 -ml-1 h-5 w-5 animate-spin text-white"
                fill="none"
                viewBox="0 0 24 24"
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
            <span v-else-if="success"> Link Sent! </span>
            <span v-else> Send Magic Link </span>
          </button>
        </form>

        <!-- Help Text -->
        <div class="mt-6 text-center">
          <p class="text-sm text-slate-500">
            Don't have an account?
            <a
              href="/signup"
              class="font-medium text-emerald-600 hover:text-emerald-700"
            >
              Sign up
            </a>
          </p>
        </div>
      </div>

      <!-- Security Note -->
      <div class="mt-6 text-center">
        <p class="text-xs text-slate-500">
          <svg class="mr-1 inline h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
            <path
              fill-rule="evenodd"
              d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z"
              clip-rule="evenodd"
            />
          </svg>
          Secure passwordless authentication
        </p>
      </div>
    </div>
  </div>
</template>
