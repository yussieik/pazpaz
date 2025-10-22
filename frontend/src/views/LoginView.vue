<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import apiClient from '@/api/client'
import { useToast } from '@/composables/useToast'

const route = useRoute()
const toast = useToast()

const email = ref('')
const isLoading = ref(false)
const error = ref<string | null>(null)
const success = ref(false)
const emailInputRef = ref<HTMLInputElement | null>(null)
const emailInputHasError = ref(false) // Track validation errors for shake animation

// Enhanced waiting experience state
const linkExpiresIn = ref(15 * 60) // 15 minutes in seconds
const resendCooldown = ref(0) // Cooldown before allowing resend
const isResending = ref(false)
const isEditing = ref(false) // Track if user is editing email after submission
const showHelpAccordion = ref(false) // Track help accordion expanded state

// Development mode MailHog indicator
const isDevelopment = import.meta.env.MODE === 'development'
const mailhogUrl = import.meta.env.VITE_MAILHOG_URL || 'http://localhost:8025'
const showMailHogBanner = ref(
  isDevelopment && !sessionStorage.getItem('mailhog_banner_dismissed'),
)

// Email arrival detection
const hasLeftTab = ref(false)
const timeLeftTab = ref<number | null>(null)
const hasShownReturnMessage = ref(false)

let countdownInterval: ReturnType<typeof setInterval> | null = null
let cooldownInterval: ReturnType<typeof setInterval> | null = null

// Check if user was redirected due to session expiration
const sessionExpiredMessage = computed(() => {
  return route.query.message === 'session_expired'
})

/**
 * Format seconds as MM:SS
 */
const formattedLinkExpiry = computed(() => {
  const minutes = Math.floor(linkExpiresIn.value / 60)
  const seconds = linkExpiresIn.value % 60
  return `${minutes}:${String(seconds).padStart(2, '0')}`
})

/**
 * Check if resend is available
 */
const canResend = computed(() => {
  return success.value && resendCooldown.value <= 0 && !isResending.value
})

/**
 * Handle tab visibility change for email arrival detection
 */
function handleVisibilityChange() {
  if (document.hidden) {
    // User left tab
    if (success.value && !hasLeftTab.value) {
      hasLeftTab.value = true
      timeLeftTab.value = Date.now()
      console.log('[EmailDetection] User left tab to check email')
    }
  } else {
    // User returned to tab
    if (hasLeftTab.value && !hasShownReturnMessage.value && timeLeftTab.value) {
      const timeAway = Date.now() - timeLeftTab.value

      // Only show if away for 10+ seconds
      if (timeAway > 10000) {
        toast.showInfo(
          "Welcome back! The magic link should be in your inbox. Check spam if you don't see it."
        )
        hasShownReturnMessage.value = true
        console.log(`[EmailDetection] User returned after ${Math.round(timeAway / 1000)}s`)
      }
    }
  }
}

/**
 * Reset email detection state when new magic link requested
 */
watch(success, (newValue) => {
  if (newValue) {
    hasLeftTab.value = false
    timeLeftTab.value = null
    hasShownReturnMessage.value = false
  }
})

onMounted(() => {
  // Focus email input on mount for keyboard-first UX
  emailInputRef.value?.focus()

  // Check if there's an error from failed auth verification
  if (route.query.error === 'invalid_link') {
    error.value = 'Invalid or expired magic link. Please request a new one.'
  }

  // Set up visibility change listener for email arrival detection
  document.addEventListener('visibilitychange', handleVisibilityChange)
})

onUnmounted(() => {
  // Cleanup intervals
  if (countdownInterval) {
    clearInterval(countdownInterval)
    countdownInterval = null
  }
  if (cooldownInterval) {
    clearInterval(cooldownInterval)
    cooldownInterval = null
  }

  // Cleanup visibility listener
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})

async function requestMagicLink() {
  // Client-side validation
  if (!email.value || !email.value.includes('@')) {
    error.value = 'Please enter a valid email address'
    emailInputHasError.value = true
    // Reset shake animation after it completes
    setTimeout(() => {
      emailInputHasError.value = false
    }, 400)
    return
  }

  isLoading.value = true
  error.value = null
  emailInputHasError.value = false
  success.value = false

  try {
    // Request magic link from backend
    // Note: Backend returns generic success to prevent email enumeration
    await apiClient.post('/auth/magic-link', {
      email: email.value.toLowerCase().trim(),
    })

    success.value = true

    // Start countdown timer for link expiration
    startCountdown()

    // Start resend cooldown (60 seconds)
    startResendCooldown(60)
  } catch (err: unknown) {
    // Handle specific error cases
    const axiosError = err as { response?: { status: number; data?: { detail?: string } } }
    if (axiosError.response?.status === 429) {
      // Extract retry-after from error message if available
      const detail = axiosError.response.data?.detail || ''
      const retryMatch = detail.match(/try again in (\d+) seconds/)
      const retryAfter = retryMatch && retryMatch[1] ? parseInt(retryMatch[1]) : 60

      error.value = `Too many requests. Please try again in ${retryAfter} seconds.`

      // If we already sent a link, show success and cooldown
      if (success.value) {
        startResendCooldown(retryAfter)
      }
    } else if (axiosError.response?.status === 422) {
      error.value = 'Please enter a valid email address'
    } else {
      error.value = 'An error occurred. Please try again.'
    }
    console.error('Magic link request failed:', err)
  } finally {
    isLoading.value = false
    isResending.value = false
  }
}

/**
 * Start countdown timer for link expiration (15 minutes)
 */
function startCountdown() {
  // Clear existing interval
  if (countdownInterval) {
    clearInterval(countdownInterval)
  }

  // Reset to 15 minutes
  linkExpiresIn.value = 15 * 60

  // Countdown every second
  countdownInterval = setInterval(() => {
    linkExpiresIn.value--

    if (linkExpiresIn.value <= 0) {
      // Link expired
      if (countdownInterval) {
        clearInterval(countdownInterval)
        countdownInterval = null
      }
    }
  }, 1000)
}

/**
 * Start resend cooldown timer
 */
function startResendCooldown(seconds: number) {
  // Clear existing interval
  if (cooldownInterval) {
    clearInterval(cooldownInterval)
  }

  resendCooldown.value = seconds

  cooldownInterval = setInterval(() => {
    resendCooldown.value--

    if (resendCooldown.value <= 0) {
      if (cooldownInterval) {
        clearInterval(cooldownInterval)
        cooldownInterval = null
      }
    }
  }, 1000)
}

/**
 * Resend magic link
 */
async function resendMagicLink() {
  if (resendCooldown.value > 0 || isResending.value) {
    return
  }

  isResending.value = true
  error.value = null

  await requestMagicLink()
}

/**
 * Allow user to edit email after submission
 */
function editEmail() {
  // Clear success state
  success.value = false
  isEditing.value = true
  error.value = null

  // Clear timers
  if (countdownInterval) {
    clearInterval(countdownInterval)
    countdownInterval = null
  }
  if (cooldownInterval) {
    clearInterval(cooldownInterval)
    cooldownInterval = null
  }

  // Reset countdown values
  linkExpiresIn.value = 15 * 60
  resendCooldown.value = 0

  // Focus email input after transition
  setTimeout(() => {
    emailInputRef.value?.focus()
    emailInputRef.value?.select()
  }, 100)
}

/**
 * Toggle help accordion
 */
function toggleHelpAccordion() {
  showHelpAccordion.value = !showHelpAccordion.value
}

/**
 * Dismiss MailHog banner (dev mode only)
 */
function dismissMailHogBanner() {
  showMailHogBanner.value = false
  sessionStorage.setItem('mailhog_banner_dismissed', 'true')
}

function handleSubmit() {
  isEditing.value = false
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

      <!-- MailHog Development Mode Banner -->
      <Transition name="banner-fade">
        <div
          v-if="showMailHogBanner"
          class="mb-6 rounded-lg border border-amber-300 bg-amber-50 p-4 shadow-sm"
          role="status"
        >
          <div class="flex items-start justify-between">
            <div class="flex items-start">
              <svg
                class="mt-0.5 mr-3 h-5 w-5 flex-shrink-0 text-amber-600"
                fill="currentColor"
                viewBox="0 0 20 20"
                aria-hidden="true"
              >
                <path
                  fill-rule="evenodd"
                  d="M12.316 3.051a1 1 0 01.633 1.265l-4 12a1 1 0 11-1.898-.632l4-12a1 1 0 011.265-.633zM5.707 6.293a1 1 0 010 1.414L3.414 10l2.293 2.293a1 1 0 11-1.414 1.414l-3-3a1 1 0 010-1.414l3-3a1 1 0 011.414 0zm8.586 0a1 1 0 011.414 0l3 3a1 1 0 010 1.414l-3 3a1 1 0 11-1.414-1.414L16.586 10l-2.293-2.293a1 1 0 010-1.414z"
                  clip-rule="evenodd"
                />
              </svg>
              <div class="flex-1">
                <h3 class="text-sm font-semibold text-amber-900">Development Mode</h3>
                <p class="mt-1 text-xs text-amber-700">
                  Check
                  <a
                    :href="mailhogUrl"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="font-medium underline hover:no-underline focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-1 rounded"
                  >
                    MailHog
                  </a>
                  for magic link emails during testing
                </p>
              </div>
            </div>
            <button
              @click="dismissMailHogBanner"
              type="button"
              class="ml-3 flex-shrink-0 rounded-md p-1 text-amber-600 hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:ring-offset-1"
              aria-label="Dismiss development mode banner"
            >
              <svg class="h-4 w-4" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                <path
                  fill-rule="evenodd"
                  d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                  clip-rule="evenodd"
                />
              </svg>
            </button>
          </div>
        </div>
      </Transition>

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

        <!-- Enhanced Success Message with Countdown -->
        <div
          v-if="success"
          class="mb-6 rounded-lg border border-emerald-200 bg-emerald-50 p-4"
          role="alert"
        >
          <div class="flex items-start">
            <!-- Animated Checkmark -->
            <div class="mr-3 flex-shrink-0">
              <Transition name="checkmark-scale">
                <svg
                  v-if="success"
                  class="h-5 w-5 text-emerald-600"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                  aria-hidden="true"
                >
                  <path
                    fill-rule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    clip-rule="evenodd"
                  />
                </svg>
              </Transition>
            </div>

            <div class="flex-1">
              <h3 class="font-semibold text-emerald-900">Check your email</h3>
              <p class="mt-1 text-sm text-emerald-700">
                <template v-if="isEditing">
                  Email changed. We'll send a new link to
                </template>
                <template v-else> We've sent a magic link to </template>
                <strong>{{ email }}</strong>
                <button
                  @click="editEmail"
                  type="button"
                  class="ml-2 text-xs font-medium text-emerald-600 underline hover:no-underline focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-1 rounded"
                  :aria-label="`Edit email address ${email}`"
                >
                  Edit
                </button>
                <template v-if="!isEditing">
                  . Click the link in the email to sign in.
                </template>
              </p>

              <!-- Countdown Timer -->
              <div class="mt-3 rounded-md bg-emerald-100 px-3 py-2">
                <p class="text-xs text-emerald-800">
                  <span class="font-medium">Link expires in:</span>
                  <span
                    class="ml-2 font-mono text-sm font-bold tabular-nums"
                    :class="{ 'text-red-600 animate-pulse': linkExpiresIn <= 60 }"
                  >
                    {{ formattedLinkExpiry }}
                  </span>
                </p>
              </div>

              <!-- Helpful Tips -->
              <div class="mt-3 space-y-1">
                <p class="text-xs text-emerald-700 flex items-start">
                  <svg
                    class="mt-0.5 mr-1.5 h-3 w-3 flex-shrink-0"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                    aria-hidden="true"
                  >
                    <path
                      fill-rule="evenodd"
                      d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                      clip-rule="evenodd"
                    />
                  </svg>
                  <span>Check your spam folder if you don't see it</span>
                </p>
                <p class="text-xs text-emerald-700 flex items-start">
                  <svg
                    class="mt-0.5 mr-1.5 h-3 w-3 flex-shrink-0"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                    aria-hidden="true"
                  >
                    <path
                      fill-rule="evenodd"
                      d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                      clip-rule="evenodd"
                    />
                  </svg>
                  <span>The link can only be used once</span>
                </p>
              </div>

              <!-- Resend Link -->
              <div class="mt-4 border-t border-emerald-200 pt-3">
                <p class="text-xs text-emerald-800">
                  Didn't receive it?
                  <button
                    v-if="canResend"
                    @click="resendMagicLink"
                    class="font-medium underline hover:no-underline focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 rounded"
                    :disabled="isResending"
                  >
                    {{ isResending ? 'Resending...' : 'Resend magic link' }}
                  </button>
                  <span v-else class="text-emerald-600">
                    Resend available in {{ resendCooldown }}s
                  </span>
                </p>
              </div>

              <!-- Help Accordion -->
              <div class="mt-4 border-t border-emerald-200 pt-3">
                <button
                  @click="toggleHelpAccordion"
                  type="button"
                  class="flex w-full items-center justify-between text-left text-xs font-medium text-emerald-800 hover:text-emerald-900 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-1 rounded"
                  :aria-expanded="showHelpAccordion"
                  aria-controls="help-content"
                >
                  <span>Didn't receive the email?</span>
                  <svg
                    class="h-4 w-4 transition-transform"
                    :class="{ 'rotate-180': showHelpAccordion }"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                    aria-hidden="true"
                  >
                    <path
                      fill-rule="evenodd"
                      d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
                      clip-rule="evenodd"
                    />
                  </svg>
                </button>

                <Transition name="accordion">
                  <div
                    v-show="showHelpAccordion"
                    id="help-content"
                    role="region"
                    class="mt-2 space-y-2"
                  >
                    <div class="flex items-start text-xs text-emerald-700">
                      <svg
                        class="mt-0.5 mr-2 h-3.5 w-3.5 flex-shrink-0 text-emerald-600"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                        aria-hidden="true"
                      >
                        <path
                          fill-rule="evenodd"
                          d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                          clip-rule="evenodd"
                        />
                      </svg>
                      <span
                        ><strong>Check spam folder:</strong> Magic links sometimes end up in
                        spam or junk folders</span
                      >
                    </div>

                    <div class="flex items-start text-xs text-emerald-700">
                      <svg
                        class="mt-0.5 mr-2 h-3.5 w-3.5 flex-shrink-0 text-emerald-600"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                        aria-hidden="true"
                      >
                        <path
                          fill-rule="evenodd"
                          d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                          clip-rule="evenodd"
                        />
                      </svg>
                      <span
                        ><strong>Check email address:</strong> Make sure
                        <strong>{{ email }}</strong> is correct
                        <button
                          @click="editEmail"
                          type="button"
                          class="ml-1 text-emerald-600 underline hover:no-underline focus:outline-none focus:ring-1 focus:ring-emerald-500 rounded"
                        >
                          (edit)
                        </button></span
                      >
                    </div>

                    <div class="flex items-start text-xs text-emerald-700">
                      <svg
                        class="mt-0.5 mr-2 h-3.5 w-3.5 flex-shrink-0 text-amber-600"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                        aria-hidden="true"
                      >
                        <path
                          fill-rule="evenodd"
                          d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z"
                          clip-rule="evenodd"
                        />
                      </svg>
                      <span
                        ><strong>Wait a few minutes:</strong> Email delivery can take up to 5
                        minutes</span
                      >
                    </div>

                    <div class="flex items-start text-xs text-emerald-700">
                      <svg
                        class="mt-0.5 mr-2 h-3.5 w-3.5 flex-shrink-0 text-amber-600"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                        aria-hidden="true"
                      >
                        <path
                          fill-rule="evenodd"
                          d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                          clip-rule="evenodd"
                        />
                      </svg>
                      <span
                        ><strong>Check email provider:</strong> Some email providers block
                        automated emails. Try a different email address.</span
                      >
                    </div>

                    <div class="flex items-start text-xs text-emerald-700">
                      <svg
                        class="mt-0.5 mr-2 h-3.5 w-3.5 flex-shrink-0 text-amber-600"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                        aria-hidden="true"
                      >
                        <path
                          fill-rule="evenodd"
                          d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                          clip-rule="evenodd"
                        />
                      </svg>
                      <span
                        ><strong>Firewall/filters:</strong> Corporate email systems may block
                        external emails</span
                      >
                    </div>

                    <div class="mt-3 flex items-start rounded-md bg-emerald-100 p-2 text-xs text-emerald-800">
                      <svg
                        class="mt-0.5 mr-2 h-3.5 w-3.5 flex-shrink-0"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                        aria-hidden="true"
                      >
                        <path
                          d="M2.003 5.884L10 9.882l7.997-3.998A2 2 0 0016 4H4a2 2 0 00-1.997 1.884z"
                        />
                        <path d="M18 8.118l-8 4-8-4V14a2 2 0 002 2h12a2 2 0 002-2V8.118z" />
                      </svg>
                      <span
                        ><strong>Still having trouble?</strong> Contact
                        <a
                          href="mailto:support@pazpaz.com"
                          class="font-medium underline hover:no-underline focus:outline-none focus:ring-1 focus:ring-emerald-500 rounded"
                          >support@pazpaz.com</a
                        ></span
                      >
                    </div>
                  </div>
                </Transition>
              </div>
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
              :disabled="isLoading"
              :class="[
                'block w-full rounded-lg border px-4 py-3 text-slate-900 placeholder-slate-400',
                'transition-all duration-200 ease-in-out',
                'focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none',
                'hover:border-slate-400 hover:shadow-sm',
                'disabled:cursor-not-allowed disabled:bg-slate-100',
                emailInputHasError
                  ? 'border-red-300 animate-shake'
                  : 'border-slate-300',
              ]"
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
            :disabled="isLoading || !email"
            :class="[
              'w-full rounded-lg px-4 py-3 font-semibold text-white',
              'transition-all duration-200 ease-in-out',
              'focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:outline-none',
              'disabled:cursor-not-allowed disabled:bg-slate-300 disabled:hover:bg-slate-300',
              isLoading || !email
                ? 'bg-slate-300'
                : 'bg-emerald-600 hover:bg-emerald-700 hover:shadow-lg transform hover:scale-102 active:scale-98',
            ]"
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
            <span v-else-if="success && isEditing"> Send New Link </span>
            <span v-else-if="success"> Link Sent! </span>
            <span v-else> Send Magic Link </span>
          </button>
        </form>
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

<style scoped>
/* Checkmark bounce-in animation (enhanced) */
.checkmark-scale-enter-active {
  animation: bounce-in 0.5s cubic-bezier(0.68, -0.55, 0.265, 1.55);
}

.checkmark-scale-enter-from {
  transform: scale(0);
  opacity: 0;
}

.checkmark-scale-enter-to {
  transform: scale(1);
  opacity: 1;
}

/* Pulse animation for expiring countdown */
@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}

.animate-pulse {
  animation: pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

/* Accordion expand/collapse animation */
.accordion-enter-active,
.accordion-leave-active {
  transition:
    opacity 200ms ease,
    max-height 300ms ease;
  overflow: hidden;
}

.accordion-enter-from,
.accordion-leave-to {
  opacity: 0;
  max-height: 0;
}

.accordion-enter-to,
.accordion-leave-from {
  opacity: 1;
  max-height: 500px;
}

/* Banner fade animation */
.banner-fade-enter-active,
.banner-fade-leave-active {
  transition:
    opacity 200ms ease,
    transform 200ms ease;
}

.banner-fade-enter-from,
.banner-fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

.banner-fade-enter-to,
.banner-fade-leave-from {
  opacity: 1;
  transform: translateY(0);
}

/* Respect user's motion preferences */
@media (prefers-reduced-motion: reduce) {
  .checkmark-scale-enter-active {
    animation: none;
    transition: opacity 1ms;
  }

  .animate-pulse {
    animation: none;
  }

  .accordion-enter-active,
  .accordion-leave-active {
    transition-duration: 1ms;
  }

  .banner-fade-enter-active,
  .banner-fade-leave-active {
    transition-duration: 1ms;
  }

  button {
    transform: none !important;
  }

  button:hover,
  button:active {
    transform: none !important;
  }

  input {
    animation: none !important;
  }
}
</style>
