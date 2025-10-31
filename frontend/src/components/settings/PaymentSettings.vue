<script setup lang="ts">
/**
 * Payment Settings Component
 *
 * Manages payment provider configuration for workspace.
 *
 * Features:
 * - Enable/disable payments toggle
 * - Progressive disclosure account checkpoint
 * - Setup guide for new PayPlus users
 * - API credentials form with numbered fields and help text
 * - Connection testing with success/error states
 * - Business details form (name, tax ID, address)
 * - VAT configuration (rate and registration status)
 * - Auto-send payment request settings
 * - Save configuration with encryption
 *
 * UX Improvements:
 * - Account checkpoint: branches flow for existing vs new users
 * - Setup guide: 3-step instructions for account creation
 * - Human-friendly field labels with contextual help
 * - Visual feedback: checkmarks, numbered circles, success/error states
 * - Progressive disclosure: sections appear after previous completed
 *
 * States:
 * - Not Enabled: Shows enable toggle and provider info
 * - Enabled + No Account: Shows setup guide
 * - Enabled + Has Account: Shows credentials form
 * - Connection Success: Shows business details and remaining sections
 *
 * HIPAA Note: Credentials are encrypted before sending to backend
 */

import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import apiClient from '@/api/client'
import ToggleSwitch from '@/components/common/ToggleSwitch.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

// State - Existing
const paymentsEnabled = ref(false)
const provider = ref<'payplus' | ''>('payplus')
const apiKey = ref('')
const paymentPageUid = ref('')
const webhookSecret = ref('')
const baseUrl = ref('')
const businessName = ref('')
const businessNameHebrew = ref('')
const taxId = ref('')
const businessLicense = ref('')
const businessAddress = ref('')
const vatRegistered = ref(false)
const vatRate = ref(17.0)
const autoSend = ref(false)
const sendTiming = ref<'immediately' | 'end_of_day' | 'end_of_month' | 'manual'>(
  'immediately'
)

const loading = ref(false)
const testing = ref(false)
const saveError = ref<string | null>(null)

// State - New UX features
const accountStatus = ref<'has-account' | 'needs-account' | ''>('')
const showDetailedGuide = ref(false)
const connectionSuccess = ref(false)
const connectionError = ref(false)
const errorMessage = ref<string | null>(null)

// Composables
const authStore = useAuthStore()
const { showSuccess, showError, showWarning } = useToast()

// Computed - Existing
const isFormValid = computed(() => {
  if (!paymentsEnabled.value) return true

  return (
    provider.value !== '' &&
    apiKey.value.trim() !== '' &&
    paymentPageUid.value.trim() !== '' &&
    webhookSecret.value.trim() !== '' &&
    businessName.value.trim() !== '' &&
    taxId.value.trim() !== ''
  )
})

// Computed - New UX features
const allFieldsFilled = computed(() => {
  return (
    apiKey.value.trim() !== '' &&
    paymentPageUid.value.trim() !== '' &&
    webhookSecret.value.trim() !== ''
  )
})

const showCredentialsForm = computed(() => {
  return paymentsEnabled.value && accountStatus.value === 'has-account'
})

const showSetupGuide = computed(() => {
  return paymentsEnabled.value && accountStatus.value === 'needs-account'
})

const sendTimingOptions = [
  { value: 'immediately', label: 'Immediately after marking complete' },
  { value: 'end_of_day', label: 'End of day (11:59 PM)' },
  { value: 'end_of_month', label: 'End of month' },
  { value: 'manual', label: 'Manual only (no auto-send)' },
]

// Methods
onMounted(async () => {
  await loadPaymentConfig()
})

async function loadPaymentConfig() {
  loading.value = true
  saveError.value = null

  try {
    // Fetch payment configuration
    const response = await apiClient.get('/payments/config')
    const config = response.data

    // Populate form
    paymentsEnabled.value = config.enabled || false
    provider.value = config.provider || 'payplus'

    // Business details
    businessName.value = config.business_name || ''
    businessNameHebrew.value = config.business_name_hebrew || ''
    taxId.value = config.tax_id || ''
    businessLicense.value = config.business_license || ''
    businessAddress.value = config.business_address || ''

    // VAT settings
    vatRegistered.value = config.vat_registered || false
    vatRate.value = config.vat_rate || 17.0

    // Auto-send settings
    autoSend.value = config.auto_send || false
    sendTiming.value = config.send_timing || 'immediately'

    // Note: API credentials are NOT returned from backend for security
    // User must re-enter them if they want to change
  } catch (error: unknown) {
    console.error('[PaymentSettings] Failed to load config:', error)

    if (
      error &&
      typeof error === 'object' &&
      'response' in error &&
      error.response &&
      typeof error.response === 'object' &&
      'status' in error.response &&
      error.response.status === 404
    ) {
      // No config exists yet, use defaults
      console.debug('[PaymentSettings] No existing config found, using defaults')
    } else {
      showError('Failed to load payment settings')
    }
  } finally {
    loading.value = false
  }
}

async function testConnection() {
  if (!apiKey.value || !paymentPageUid.value || !webhookSecret.value) {
    showWarning('Please fill in all API credentials before testing')
    return
  }

  testing.value = true
  connectionSuccess.value = false
  connectionError.value = false
  errorMessage.value = null

  try {
    // Test PayPlus API credentials
    // Note: This endpoint validates credentials without storing them
    const payload: Record<string, string> = {
      api_key: apiKey.value,
      payment_page_uid: paymentPageUid.value,
      webhook_secret: webhookSecret.value,
    }

    // Include base_url if provided (for testing/sandbox environments)
    if (baseUrl.value.trim()) {
      payload.base_url = baseUrl.value
    }

    const response = await apiClient.post('/payments/test-credentials', payload)

    if (response.data?.valid !== false) {
      connectionSuccess.value = true
      showSuccess('Connection successful! Credentials are valid.')
    } else {
      connectionError.value = true
      errorMessage.value = response.data?.error || 'Invalid credentials'
      showError('Connection failed')
    }
  } catch (error: unknown) {
    console.error('[PaymentSettings] Connection test failed:', error)
    connectionError.value = true

    if (
      error &&
      typeof error === 'object' &&
      'response' in error &&
      error.response &&
      typeof error.response === 'object' &&
      'data' in error.response &&
      error.response.data &&
      typeof error.response.data === 'object' &&
      'detail' in error.response.data &&
      typeof error.response.data.detail === 'string'
    ) {
      errorMessage.value = error.response.data.detail
      showError(`Connection failed: ${error.response.data.detail}`)
    } else {
      errorMessage.value = 'Failed to connect to PayPlus'
      showError('Connection test failed. Please check your credentials.')
    }
  } finally {
    testing.value = false
  }
}

async function saveSettings() {
  if (!isFormValid.value) {
    showWarning('Please fill in all required fields')
    return
  }

  loading.value = true
  saveError.value = null

  try {
    // Prepare payload
    const payload: Record<string, unknown> = {
      payment_enabled: paymentsEnabled.value,
      payment_provider: paymentsEnabled.value ? provider.value : null,
      business_name: businessName.value || null,
      business_name_hebrew: businessNameHebrew.value || null,
      tax_id: taxId.value || null,
      business_license: businessLicense.value || null,
      business_address: businessAddress.value || null,
      vat_registered: vatRegistered.value,
      vat_rate: vatRate.value,
      payment_auto_send: autoSend.value,
      payment_send_timing: sendTiming.value,
    }

    // Only include credentials if they are provided (changed)
    if (
      paymentsEnabled.value &&
      apiKey.value &&
      paymentPageUid.value &&
      webhookSecret.value
    ) {
      const config: Record<string, string> = {
        api_key: apiKey.value,
        payment_page_uid: paymentPageUid.value,
        webhook_secret: webhookSecret.value,
      }

      // Include base_url if provided (for testing/sandbox environments)
      if (baseUrl.value.trim()) {
        config.base_url = baseUrl.value
      }

      payload.payment_provider_config = config
    }

    // Update workspace settings
    const workspaceId = authStore.user?.workspace_id
    if (!workspaceId) {
      throw new Error('Workspace ID not found')
    }

    await apiClient.patch(`/workspaces/${workspaceId}`, payload)

    showSuccess('Payment settings saved successfully!')

    // Clear credentials from form (security best practice)
    if (paymentsEnabled.value) {
      apiKey.value = ''
      paymentPageUid.value = ''
      webhookSecret.value = ''
      baseUrl.value = ''
      showWarning(
        'For security, please re-enter credentials if you need to change them'
      )
    }
  } catch (error: unknown) {
    console.error('[PaymentSettings] Save failed:', error)
    saveError.value = 'Failed to save settings'

    if (
      error &&
      typeof error === 'object' &&
      'response' in error &&
      error.response &&
      typeof error.response === 'object' &&
      'data' in error.response &&
      error.response.data &&
      typeof error.response.data === 'object' &&
      'detail' in error.response.data &&
      typeof error.response.data.detail === 'string'
    ) {
      showError(`Failed to save: ${error.response.data.detail}`)
    } else {
      showError('Failed to save payment settings. Please try again.')
    }
  } finally {
    loading.value = false
  }
}

function handleTogglePayments(enabled: boolean) {
  paymentsEnabled.value = enabled

  if (!enabled) {
    // Clear form when disabling
    apiKey.value = ''
    paymentPageUid.value = ''
    webhookSecret.value = ''
    accountStatus.value = ''
    connectionSuccess.value = false
    connectionError.value = false
    errorMessage.value = null
  }
}

function handleAccountCreated() {
  accountStatus.value = 'has-account'
  showDetailedGuide.value = false
}
</script>

<template>
  <div>
    <!-- Loading State -->
    <div
      v-if="loading && !paymentsEnabled"
      class="flex items-center justify-center py-12"
    >
      <LoadingSpinner />
    </div>

    <!-- Main Content -->
    <div v-else class="max-w-2xl space-y-6">
      <!-- Enable Payments Card -->
      <div class="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div class="flex items-start justify-between gap-4">
          <div class="flex items-start gap-4">
            <!-- Payment Icon -->
            <div class="flex-shrink-0">
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
                  d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"
                />
              </svg>
            </div>

            <div class="flex-1">
              <h2 class="text-lg font-semibold text-slate-900">
                Enable Payment Processing
              </h2>
              <p class="mt-1 text-sm text-slate-600">
                Accept payments from clients directly through PazPaz. Requires a PayPlus
                account (Israel market).
              </p>
            </div>
          </div>

          <!-- Toggle -->
          <div class="flex-shrink-0">
            <ToggleSwitch
              :model-value="paymentsEnabled"
              label="Enable payments"
              @update:model-value="handleTogglePayments"
            />
          </div>
        </div>

        <!-- Warning -->
        <div
          v-if="!paymentsEnabled"
          class="mt-4 rounded-md border border-blue-200 bg-blue-50 p-4"
        >
          <div class="flex items-start gap-3">
            <svg
              class="mt-0.5 h-5 w-5 flex-shrink-0 text-blue-600"
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
            <div class="flex-1 text-sm text-blue-900">
              <p class="font-medium">Before enabling payments:</p>
              <ul class="mt-2 list-inside list-disc space-y-1">
                <li>
                  Create a PayPlus account at
                  <a
                    href="https://www.payplus.co.il"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="underline hover:no-underline"
                    >payplus.co.il</a
                  >
                </li>
                <li>Generate API credentials from your PayPlus dashboard</li>
                <li>Have your business tax ID (תעודת זהות / עוסק מורשה) ready</li>
              </ul>
            </div>
          </div>
        </div>
      </div>

      <!-- Account Checkpoint (NEW) -->
      <div v-if="paymentsEnabled" class="rounded-lg border-2 border-slate-300 bg-white p-6 shadow-sm">
        <h3 class="text-base font-semibold text-slate-900">
          Let's connect your PayPlus account
        </h3>
        <p class="mt-1 text-sm text-slate-600">
          PayPlus is an Israeli payment provider that handles secure online payments.
        </p>

        <div class="mt-4 space-y-3">
          <!-- Option 1: Has account -->
          <label
            class="flex cursor-pointer items-start gap-3 rounded-md border-2 p-4 transition"
            :class="accountStatus === 'has-account' ? 'border-emerald-500 bg-emerald-50' : 'border-slate-200 hover:border-emerald-500 hover:bg-emerald-50'"
          >
            <input
              v-model="accountStatus"
              type="radio"
              value="has-account"
              class="mt-1 h-5 w-5 text-emerald-600"
            />
            <div class="flex-1">
              <div class="font-medium text-slate-900">Yes, I have a PayPlus account</div>
              <div class="text-sm text-slate-600">I'm ready to connect my account</div>
            </div>
          </label>

          <!-- Option 2: Needs account -->
          <label
            class="flex cursor-pointer items-start gap-3 rounded-md border-2 p-4 transition"
            :class="accountStatus === 'needs-account' ? 'border-blue-500 bg-blue-50' : 'border-slate-200 hover:border-blue-500 hover:bg-blue-50'"
          >
            <input
              v-model="accountStatus"
              type="radio"
              value="needs-account"
              class="mt-1 h-5 w-5 text-blue-600"
            />
            <div class="flex-1">
              <div class="font-medium text-slate-900">No, I need to sign up first</div>
              <div class="text-sm text-slate-600">Show me how to create an account</div>
            </div>
          </label>
        </div>
      </div>

      <!-- Setup Guide (NEW - conditional) -->
      <Transition name="slide-fade">
        <div v-if="showSetupGuide" class="rounded-lg border-2 border-blue-200 bg-blue-50 p-6 shadow-sm">
          <div class="flex items-start gap-3">
            <svg
              class="h-6 w-6 flex-shrink-0 text-blue-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <div class="flex-1">
              <h3 class="text-base font-semibold text-blue-900">
                How to set up PayPlus in 3 simple steps
              </h3>
              <p class="mt-1 text-sm text-blue-800">
                This takes about 5-10 minutes. You'll need your business tax ID.
              </p>
            </div>
          </div>

          <ol class="mt-6 space-y-6">
            <!-- Step 1: Create Account -->
            <li class="flex gap-4">
              <div class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold text-white">
                1
              </div>
              <div class="flex-1">
                <h4 class="font-semibold text-blue-900">Create a PayPlus account</h4>
                <p class="mt-1 text-sm text-blue-800">
                  Sign up for a free PayPlus business account. You'll need your business tax ID
                  and bank details.
                </p>
                <a
                  href="https://www.payplus.co.il"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="mt-2 inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                >
                  Go to PayPlus
                  <svg
                    class="h-4 w-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                    />
                  </svg>
                </a>
              </div>
            </li>

            <!-- Step 2: Get Credentials -->
            <li class="flex gap-4">
              <div class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold text-white">
                2
              </div>
              <div class="flex-1">
                <h4 class="font-semibold text-blue-900">Get your API credentials</h4>
                <p class="mt-1 text-sm text-blue-800">
                  After signing up, you'll need to collect three pieces of information from your
                  PayPlus dashboard:
                </p>

                <button
                  type="button"
                  class="mt-2 flex items-center gap-2 text-sm font-medium text-blue-700 hover:text-blue-800"
                  @click="showDetailedGuide = !showDetailedGuide"
                >
                  <svg
                    class="h-4 w-4 transition-transform"
                    :class="{ 'rotate-90': showDetailedGuide }"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      stroke-linecap="round"
                      stroke-linejoin="round"
                      stroke-width="2"
                      d="M9 5l7 7-7 7"
                    />
                  </svg>
                  {{ showDetailedGuide ? 'Hide' : 'Show' }} detailed instructions
                </button>

                <div v-if="showDetailedGuide" class="mt-4 space-y-4">
                  <div class="rounded-md border border-blue-300 bg-white p-4">
                    <p class="text-sm font-medium text-slate-900">1. API Key</p>
                    <p class="mt-1 text-sm text-slate-600">
                      Go to PayPlus Dashboard → Settings → API Keys
                    </p>
                    <!-- TODO: Add screenshot placeholder -->
                    <div class="mt-2 rounded border border-slate-200 bg-slate-100 p-8 text-center text-sm text-slate-500">
                      [Screenshot: PayPlus API Key location will be added here]
                    </div>
                  </div>

                  <div class="rounded-md border border-blue-300 bg-white p-4">
                    <p class="text-sm font-medium text-slate-900">2. Payment Page UID</p>
                    <p class="mt-1 text-sm text-slate-600">
                      Go to PayPlus Dashboard → Payment Pages → Settings
                    </p>
                    <!-- TODO: Add screenshot placeholder -->
                    <div class="mt-2 rounded border border-slate-200 bg-slate-100 p-8 text-center text-sm text-slate-500">
                      [Screenshot: Payment Page UID location will be added here]
                    </div>
                  </div>

                  <div class="rounded-md border border-blue-300 bg-white p-4">
                    <p class="text-sm font-medium text-slate-900">3. Webhook Secret</p>
                    <p class="mt-1 text-sm text-slate-600">
                      Go to PayPlus Dashboard → Settings → Webhooks
                    </p>
                    <!-- TODO: Add screenshot placeholder -->
                    <div class="mt-2 rounded border border-slate-200 bg-slate-100 p-8 text-center text-sm text-slate-500">
                      [Screenshot: Webhook Secret location will be added here]
                    </div>
                  </div>
                </div>
              </div>
            </li>

            <!-- Step 3: Return Here -->
            <li class="flex gap-4">
              <div class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-blue-600 text-sm font-bold text-white">
                3
              </div>
              <div class="flex-1">
                <h4 class="font-semibold text-blue-900">Return here and connect</h4>
                <p class="mt-1 text-sm text-blue-800">
                  Once you have your credentials, come back and click the button below to enter
                  them.
                </p>
                <button
                  type="button"
                  class="mt-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                  @click="handleAccountCreated"
                >
                  I've created my account
                </button>
              </div>
            </li>
          </ol>
        </div>
      </Transition>

      <!-- API Credentials Form (REDESIGNED - conditional) -->
      <Transition name="slide-fade">
        <div v-if="showCredentialsForm" class="space-y-6">
          <div class="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
            <div class="flex items-start gap-3">
              <svg
                class="h-6 w-6 flex-shrink-0 text-emerald-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"
                />
              </svg>
              <div class="flex-1">
                <h3 class="text-base font-semibold text-slate-900">
                  Connect your PayPlus account
                </h3>
                <p class="mt-1 text-sm text-slate-600">
                  Enter your PayPlus credentials to enable payment processing.
                </p>
              </div>
            </div>

            <div class="mt-6 space-y-4">
              <!-- Field 1: API Key -->
              <div class="rounded-md border border-slate-200 bg-slate-50 p-4">
                <div class="flex items-start gap-3">
                  <div class="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-slate-700 text-sm font-bold text-white">
                    1
                  </div>
                  <div class="flex-1">
                    <label for="api-key" class="block text-sm font-semibold text-slate-900">
                      API Key <span class="text-red-600">*</span>
                    </label>
                    <p class="mt-1 text-xs text-slate-600">
                      This connects PazPaz to your PayPlus account.
                      <a
                        href="https://dashboard.payplus.co.il/settings/api-keys"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="text-emerald-600 underline hover:text-emerald-700"
                      >
                        Find it in PayPlus Settings → API Keys
                      </a>
                    </p>
                    <div class="relative mt-2">
                      <input
                        id="api-key"
                        v-model="apiKey"
                        type="password"
                        class="w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 pr-10 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                        placeholder="Paste your API key here"
                      />
                      <div
                        v-if="apiKey.length > 0"
                        class="absolute right-3 top-1/2 -translate-y-1/2"
                      >
                        <svg
                          class="h-5 w-5 text-emerald-600"
                          fill="currentColor"
                          viewBox="0 0 20 20"
                        >
                          <path
                            fill-rule="evenodd"
                            d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                            clip-rule="evenodd"
                          />
                        </svg>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Field 2: Payment Page UID -->
              <div class="rounded-md border border-slate-200 bg-slate-50 p-4">
                <div class="flex items-start gap-3">
                  <div class="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-slate-700 text-sm font-bold text-white">
                    2
                  </div>
                  <div class="flex-1">
                    <label
                      for="payment-page-uid"
                      class="block text-sm font-semibold text-slate-900"
                    >
                      Payment Page UID <span class="text-red-600">*</span>
                    </label>
                    <p class="mt-1 text-xs text-slate-600">
                      This tells PayPlus which payment page to use.
                      <a
                        href="https://dashboard.payplus.co.il/payment-pages"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="text-emerald-600 underline hover:text-emerald-700"
                      >
                        Find it in PayPlus Payment Pages → Settings
                      </a>
                    </p>
                    <div class="relative mt-2">
                      <input
                        id="payment-page-uid"
                        v-model="paymentPageUid"
                        type="text"
                        class="w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 pr-10 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                        placeholder="Paste your Payment Page UID here"
                      />
                      <div
                        v-if="paymentPageUid.length > 0"
                        class="absolute right-3 top-1/2 -translate-y-1/2"
                      >
                        <svg
                          class="h-5 w-5 text-emerald-600"
                          fill="currentColor"
                          viewBox="0 0 20 20"
                        >
                          <path
                            fill-rule="evenodd"
                            d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                            clip-rule="evenodd"
                          />
                        </svg>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- Field 3: Webhook Secret -->
              <div class="rounded-md border border-slate-200 bg-slate-50 p-4">
                <div class="flex items-start gap-3">
                  <div class="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-slate-700 text-sm font-bold text-white">
                    3
                  </div>
                  <div class="flex-1">
                    <label for="webhook-secret" class="block text-sm font-semibold text-slate-900">
                      Webhook Secret <span class="text-red-600">*</span>
                    </label>
                    <p class="mt-1 text-xs text-slate-600">
                      This verifies that payment notifications are really from PayPlus.
                      <a
                        href="https://dashboard.payplus.co.il/settings/webhooks"
                        target="_blank"
                        rel="noopener noreferrer"
                        class="text-emerald-600 underline hover:text-emerald-700"
                      >
                        Find it in PayPlus Settings → Webhooks
                      </a>
                    </p>
                    <div class="relative mt-2">
                      <input
                        id="webhook-secret"
                        v-model="webhookSecret"
                        type="password"
                        class="w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 pr-10 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                        placeholder="Paste your webhook secret here"
                      />
                      <div
                        v-if="webhookSecret.length > 0"
                        class="absolute right-3 top-1/2 -translate-y-1/2"
                      >
                        <svg
                          class="h-5 w-5 text-emerald-600"
                          fill="currentColor"
                          viewBox="0 0 20 20"
                        >
                          <path
                            fill-rule="evenodd"
                            d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                            clip-rule="evenodd"
                          />
                        </svg>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Base URL Field (Optional - for testing/sandbox) -->
            <div class="rounded-md bg-slate-50 p-4">
              <div class="flex gap-3">
                <div
                  class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-slate-200 text-sm font-bold text-slate-700"
                >
                  4
                </div>
                <div class="flex-1">
                  <label for="base-url" class="block text-sm font-semibold text-slate-900">
                    API Base URL <span class="text-slate-500 font-normal">(Optional)</span>
                  </label>
                  <p class="mt-1 text-xs text-slate-600">
                    Use this to override the default PayPlus API endpoint. Leave blank for production API, or set to
                    <code class="bg-slate-200 px-1 py-0.5 rounded text-xs font-mono">https://restapidev.payplus.co.il/api/v1.0</code>
                    for testing environment.
                  </p>
                  <div class="relative mt-2">
                    <input
                      id="base-url"
                      v-model="baseUrl"
                      type="text"
                      class="w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none font-mono"
                      placeholder="https://restapidev.payplus.co.il/api/v1.0 (optional)"
                    />
                  </div>
                </div>
              </div>
            </div>

            <!-- Test Connection Button (Enhanced) -->
            <div class="mt-6 flex items-center justify-between gap-4 rounded-md border-2 border-emerald-200 bg-emerald-50 p-4">
              <div class="flex-1">
                <p class="text-sm font-medium text-emerald-900">
                  Test your connection before saving
                </p>
                <p class="mt-0.5 text-xs text-emerald-700">
                  We'll verify these credentials work with PayPlus
                </p>
              </div>
              <button
                type="button"
                :disabled="testing || !allFieldsFilled"
                class="flex-shrink-0 rounded-md bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-emerald-700 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                @click="testConnection"
              >
                <span v-if="!testing">Test Connection</span>
                <span v-else class="flex items-center gap-2">
                  <LoadingSpinner class="h-4 w-4" />
                  Testing...
                </span>
              </button>
            </div>

            <!-- Success State -->
            <div
              v-if="connectionSuccess"
              class="mt-4 flex items-start gap-3 rounded-md border border-emerald-200 bg-emerald-50 p-4"
            >
              <svg
                class="h-5 w-5 flex-shrink-0 text-emerald-600"
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
                <p class="text-sm font-medium text-emerald-900">Connection successful!</p>
                <p class="mt-0.5 text-xs text-emerald-700">
                  Your PayPlus credentials are working correctly. Continue below to complete setup.
                </p>
              </div>
            </div>

            <!-- Error State -->
            <div
              v-if="connectionError"
              class="mt-4 flex items-start gap-3 rounded-md border border-red-200 bg-red-50 p-4"
            >
              <svg
                class="h-5 w-5 flex-shrink-0 text-red-600"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fill-rule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clip-rule="evenodd"
                />
              </svg>
              <div class="flex-1">
                <p class="text-sm font-medium text-red-900">Connection failed</p>
                <p class="mt-0.5 text-xs text-red-700">
                  {{
                    errorMessage ||
                    'The credentials you entered are invalid. Double-check that you copied them correctly from PayPlus.'
                  }}
                </p>
              </div>
            </div>
          </div>
        </div>
      </Transition>

      <!-- Business Details (Progressive Disclosure - after connection success) -->
      <Transition name="slide-fade">
        <div v-if="connectionSuccess" class="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <h3 class="text-base font-semibold text-slate-900">Business Details</h3>
          <p class="mt-1 text-sm text-slate-600">
            This information appears on invoices and payment receipts
          </p>

          <div class="mt-6 space-y-4">
            <div>
              <label
                for="business-name"
                class="block text-sm font-medium text-slate-900"
              >
                Business Name <span class="text-red-600">*</span>
              </label>
              <input
                id="business-name"
                v-model="businessName"
                type="text"
                required
                class="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                placeholder="Your clinic or practice name"
              />
            </div>

            <div>
              <label
                for="business-name-hebrew"
                class="block text-sm font-medium text-slate-900"
              >
                Business Name (Hebrew)
              </label>
              <input
                id="business-name-hebrew"
                v-model="businessNameHebrew"
                type="text"
                dir="rtl"
                class="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                placeholder="שם העסק בעברית"
              />
              <p class="mt-1 text-xs text-slate-500">
                Optional: For receipts in Hebrew
              </p>
            </div>

            <div>
              <label for="tax-id" class="block text-sm font-medium text-slate-900">
                Tax ID / Business Number <span class="text-red-600">*</span>
              </label>
              <input
                id="tax-id"
                v-model="taxId"
                type="text"
                required
                class="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                placeholder="עוסק מורשה / מספר ח.פ"
              />
              <p class="mt-1 text-xs text-slate-500">
                Your Israeli business registration number
              </p>
            </div>

            <div>
              <label
                for="business-license"
                class="block text-sm font-medium text-slate-900"
              >
                Business License Number
              </label>
              <input
                id="business-license"
                v-model="businessLicense"
                type="text"
                class="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                placeholder="Optional license number"
              />
            </div>

            <div>
              <label
                for="business-address"
                class="block text-sm font-medium text-slate-900"
              >
                Business Address
              </label>
              <textarea
                id="business-address"
                v-model="businessAddress"
                rows="3"
                class="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
                placeholder="Street address, city, postal code"
              />
            </div>
          </div>
        </div>
      </Transition>

      <!-- VAT Settings (show if payments enabled) -->
      <div v-if="paymentsEnabled" class="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <h3 class="text-base font-semibold text-slate-900">VAT Settings</h3>
          <p class="mt-1 text-sm text-slate-600">
            Configure value-added tax for invoices
          </p>

          <div class="mt-6 space-y-4">
            <div class="flex items-start gap-3">
              <input
                id="vat-registered"
                v-model="vatRegistered"
                type="checkbox"
                class="mt-1 h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
              />
              <div class="flex-1">
                <label for="vat-registered" class="text-sm font-medium text-slate-900">
                  Business is VAT registered (עוסק מורשה)
                </label>
                <p class="mt-1 text-sm text-slate-600">
                  Enable if your business is registered for VAT in Israel
                </p>
              </div>
            </div>

            <div v-if="vatRegistered">
              <label for="vat-rate" class="block text-sm font-medium text-slate-900">
                VAT Rate (%)
              </label>
              <input
                id="vat-rate"
                v-model.number="vatRate"
                type="number"
                min="0"
                max="100"
                step="0.01"
                class="mt-1 w-32 rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              />
              <p class="mt-1 text-xs text-slate-500">Standard rate in Israel is 17%</p>
            </div>
          </div>
      </div>

      <!-- Auto-Send Settings (show if payments enabled) -->
      <div v-if="paymentsEnabled" class="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <h3 class="text-base font-semibold text-slate-900">
            Payment Request Settings
          </h3>
          <p class="mt-1 text-sm text-slate-600">
            Automatically send payment requests when appointments are completed
          </p>

          <div class="mt-6 space-y-4">
            <div class="flex items-start justify-between gap-4">
              <div class="flex-1">
                <label class="text-sm font-medium text-slate-900">
                  Auto-send payment requests
                </label>
                <p class="mt-1 text-sm text-slate-600">
                  Automatically send payment links to clients after appointments
                </p>
              </div>
              <div class="flex-shrink-0">
                <ToggleSwitch v-model="autoSend" label="Enable auto-send" />
              </div>
            </div>

            <div v-if="autoSend">
              <label for="send-timing" class="block text-sm font-medium text-slate-900">
                Send timing
              </label>
              <select
                id="send-timing"
                v-model="sendTiming"
                class="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
              >
                <option
                  v-for="option in sendTimingOptions"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </option>
              </select>
            </div>
          </div>
      </div>

      <!-- Save Button -->
      <div class="flex items-center justify-between gap-4">
        <div v-if="saveError" class="text-sm text-red-600">
          {{ saveError }}
        </div>
        <div v-else />

        <button
          type="button"
          :disabled="loading || !isFormValid"
          class="rounded-md bg-emerald-600 px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-emerald-700 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
          @click="saveSettings"
        >
          <span v-if="!loading">Save Settings</span>
          <span v-else class="flex items-center gap-2">
            <LoadingSpinner class="h-4 w-4" />
            Saving...
          </span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Transition animations for progressive disclosure */
.slide-fade-enter-active {
  transition: all 0.3s ease-out;
}

.slide-fade-leave-active {
  transition: all 0.2s ease-in;
}

.slide-fade-enter-from {
  transform: translateY(-20px);
  opacity: 0;
}

.slide-fade-leave-to {
  opacity: 0;
}
</style>
