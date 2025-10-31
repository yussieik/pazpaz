<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useCrossTabAuth } from '@/composables/useCrossTabAuth'
import apiClient from '@/api/client'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { notifyAuthSuccess } = useCrossTabAuth()

const status = ref<'loading' | 'success' | 'error' | 'already-authenticated'>('loading')
const errorMessage = ref<string>('')

/**
 * Remove token from URL immediately after reading it
 * Security: Prevents token exposure in browser history or URL sharing
 */
function removeTokenFromUrl() {
  // Replace URL without token query param (prevent history pollution)
  const newUrl = window.location.pathname
  window.history.replaceState({}, '', newUrl)
}

/**
 * Request a new magic link (navigate to login with pre-filled email)
 */
function requestNewLink() {
  // Try to get email from current user or route state
  const email = authStore.user?.email || route.query.email

  if (email) {
    router.push({
      path: '/login',
      query: { email: email as string },
    })
  } else {
    router.push('/login')
  }
}

/**
 * Return to home page
 */
function returnToHome() {
  router.push('/')
}

/**
 * Handle keyboard shortcuts for error state
 */
function handleKeyDown(event: KeyboardEvent) {
  if (status.value === 'error') {
    if (event.key === 'Enter') {
      event.preventDefault()
      requestNewLink()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      returnToHome()
    }
  }
}

onMounted(async () => {
  // Add keyboard event listener
  window.addEventListener('keydown', handleKeyDown)

  // Task 1.1: Check if user is already authenticated
  if (authStore.isAuthenticated) {
    console.debug('[AuthVerify] User already authenticated, redirecting to calendar')
    status.value = 'already-authenticated'

    // Notify other tabs (e.g., close any open login tabs)
    notifyAuthSuccess(authStore.user?.id)

    // Redirect after 1 second
    setTimeout(() => {
      router.push('/')
    }, 1000)
    return
  }

  const token = route.query.token as string

  // Remove token from URL immediately for security
  removeTokenFromUrl()

  if (!token) {
    status.value = 'error'
    errorMessage.value = 'No verification token provided'
    return
  }

  try {
    // Call the verify endpoint - this sets the JWT cookie and returns user data
    const response = await apiClient.post('/auth/verify', {
      token,
    })

    status.value = 'success'

    // Set user in auth store from verification response
    if (response.data?.user) {
      authStore.setUser(response.data.user)
      console.debug('[AuthVerify] User authenticated:', response.data.user.id)

      // Notify other tabs that authentication succeeded
      // This will auto-close any open login tabs
      notifyAuthSuccess(response.data.user.id)
    }

    // Get redirect URL from query params (set by login page or route guard)
    const redirectTo = (route.query.redirect as string) || '/'

    // Redirect to intended destination after successful authentication
    setTimeout(() => {
      router.push(redirectTo)
    }, 1500)
  } catch (error: unknown) {
    status.value = 'error'
    const axiosError = error as { response?: { data?: { detail?: string } } }
    errorMessage.value =
      axiosError?.response?.data?.detail || 'Invalid or expired magic link'

    console.error('[AuthVerify] Verification failed:', error)

    // Task 1.2: Do NOT auto-redirect on error - let user choose action
    // (Removed the setTimeout redirect)
  }

  // Cleanup keyboard listener on unmount
  return () => {
    window.removeEventListener('keydown', handleKeyDown)
  }
})
</script>

<template>
  <div
    class="flex min-h-screen items-center justify-center bg-gradient-to-br from-emerald-50 to-slate-50 px-4"
  >
    <div class="w-full max-w-md space-y-8 p-8">
      <!-- Task 1.3: Enhanced Loading State -->
      <div v-if="status === 'loading'" class="text-center">
        <!-- Animated key icon with spinning border -->
        <div class="relative mx-auto mb-6 h-16 w-16">
          <div
            class="absolute inset-0 animate-spin rounded-full border-4 border-emerald-200 border-t-emerald-600"
          ></div>
          <div class="absolute inset-0 flex items-center justify-center">
            <svg
              class="h-8 w-8 text-emerald-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"
              />
            </svg>
          </div>
        </div>

        <h2 class="text-2xl font-semibold text-slate-900">Signing you in...</h2>
        <p class="mt-2 text-slate-600">Verifying your magic link</p>

        <!-- Bouncing dots -->
        <div class="mt-6 flex justify-center space-x-2">
          <div
            class="h-2 w-2 animate-bounce rounded-full bg-emerald-600"
            style="animation-delay: 0ms"
          ></div>
          <div
            class="h-2 w-2 animate-bounce rounded-full bg-emerald-600"
            style="animation-delay: 150ms"
          ></div>
          <div
            class="h-2 w-2 animate-bounce rounded-full bg-emerald-600"
            style="animation-delay: 300ms"
          ></div>
        </div>
      </div>

      <!-- Task 1.3: Enhanced Success State -->
      <div v-else-if="status === 'success'" class="text-center">
        <div
          class="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100"
        >
          <svg
            class="animate-scale-in h-8 w-8 text-emerald-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>
        <h2 class="text-2xl font-semibold text-slate-900">Welcome back!</h2>
        <p class="mt-2 text-slate-600">Taking you to your calendar...</p>
      </div>

      <!-- Task 1.1: Already Authenticated State -->
      <div v-else-if="status === 'already-authenticated'" class="text-center">
        <div
          class="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-blue-100"
        >
          <svg
            class="h-8 w-8 text-blue-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
        <h2 class="text-2xl font-semibold text-slate-900">You're already signed in</h2>
        <p class="mt-2 text-slate-600">Taking you back to your calendar...</p>
      </div>

      <!-- Task 1.3: Enhanced Error State with Task 1.2: Manual Actions -->
      <div v-else class="text-center">
        <!-- Red X icon -->
        <div
          class="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-red-100"
        >
          <svg
            class="h-8 w-8 text-red-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </div>

        <h2 class="text-2xl font-semibold text-slate-900">Link expired or invalid</h2>
        <p class="mt-3 text-slate-700">{{ errorMessage }}</p>
        <p class="mt-2 text-sm text-slate-500">
          Magic links expire after 15 minutes for security
        </p>

        <!-- Task 1.2: Manual action buttons -->
        <div class="mt-8 flex flex-col space-y-3">
          <button
            @click="requestNewLink"
            ref="primaryActionButton"
            type="button"
            class="w-full rounded-lg bg-emerald-600 px-6 py-3 font-semibold text-white transition-all duration-200 hover:bg-emerald-700 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:outline-none"
            autofocus
          >
            Request new magic link
          </button>

          <button
            @click="returnToHome"
            type="button"
            class="w-full rounded-lg border-2 border-slate-300 bg-white px-6 py-3 font-semibold text-slate-700 transition-all duration-200 hover:border-slate-400 hover:bg-slate-50 focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 focus:outline-none"
          >
            Return to home
          </button>
        </div>

        <!-- Keyboard shortcuts hint -->
        <p class="mt-4 text-xs text-slate-500">
          Press <kbd class="rounded bg-slate-100 px-2 py-1 font-mono">Enter</kbd> to
          request new link or
          <kbd class="rounded bg-slate-100 px-2 py-1 font-mono">Esc</kbd> to go home
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Task 1.3: Scale-in animation for checkmark */
@keyframes scale-in {
  0% {
    transform: scale(0);
    opacity: 0;
  }
  50% {
    transform: scale(1.1);
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

.animate-scale-in {
  animation: scale-in 0.5s ease-out forwards;
}

/* Spinning border animation (Tailwind's animate-spin) */
@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.animate-spin {
  animation: spin 1s linear infinite;
}

/* Bouncing dots animation (Tailwind's animate-bounce) */
@keyframes bounce {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-0.5rem);
  }
}

.animate-bounce {
  animation: bounce 1s ease-in-out infinite;
}

/* Task 1.3: Respect reduced motion preference */
@media (prefers-reduced-motion: reduce) {
  .animate-spin,
  .animate-bounce,
  .animate-scale-in {
    animation: none;
  }

  /* Show static state instead */
  .animate-scale-in {
    transform: scale(1);
    opacity: 1;
  }
}
</style>
