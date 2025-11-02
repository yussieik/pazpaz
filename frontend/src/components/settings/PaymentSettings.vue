<script setup lang="ts">
/**
 * Payment Settings Component (Phase 1.5: Smart Payment Links)
 *
 * Allows therapists to configure payment methods for sending payment requests.
 *
 * Features (Phase 1.5):
 * - Choose payment method: Bit, PayBox, Bank Transfer, Custom Link
 * - Configure payment details (phone number, URL, bank details)
 * - Enable/disable payment tracking
 * - Copy payment link for testing
 *
 * Payment Methods:
 * - Bit: Israeli mobile payment app (phone number)
 * - PayBox: Payment gateway with links (URL)
 * - Bank Transfer: Manual bank account details (free-text)
 * - Custom Link: Custom payment URL with variables
 *
 * Future Phases:
 * - Phase 2+: Add automated payment provider integration (Bit API, PayBox API, etc.)
 */

import { ref, computed, onMounted } from 'vue'
import { useToast } from '@/composables/useToast'
import apiClient from '@/api/client'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

// State
const selectedMethod = ref<'bit' | 'paybox' | 'bank' | 'custom' | null>(null)
const isEditing = ref(false)
const saving = ref(false)
const loading = ref(false)

// Current configuration from API
const currentConfig = ref<{
  payment_mode: string | null
  payment_link_type: string | null
  payment_link_template: string | null
  bank_account_details: string | null
  payment_provider: string | null
} | null>(null)

const hasPaymentSettings = computed(() => currentConfig.value?.payment_mode !== null)

// Form fields
const bitPhoneNumber = ref('')
const bitPhoneError = ref('')

const payboxUrl = ref('')
const payboxUrlError = ref('')

const bankDetails = ref('')
const bankDetailsError = ref('')

const customUrl = ref('')
const customUrlError = ref('')

// Composables
const { showSuccess, showError } = useToast()

// Computed
const paymentTypeLabel = computed(() => {
  const labels: Record<string, string> = {
    bit: 'Bit (ביט)',
    paybox: 'PayBox',
    bank: 'Bank Transfer',
    custom: 'Custom Link',
  }
  return currentConfig.value?.payment_link_type
    ? labels[currentConfig.value.payment_link_type] || ''
    : ''
})

const paymentTemplate = computed(() => currentConfig.value?.payment_link_template || '')

const isValidBitPhone = computed(() => {
  if (!bitPhoneNumber.value) return false
  return validateIsraeliPhone(bitPhoneNumber.value)
})

const isValidPayboxUrl = computed(() => {
  if (!payboxUrl.value) return false
  return validateUrl(payboxUrl.value)
})

const isValidCustomUrl = computed(() => {
  if (!customUrl.value) return false
  return validateUrl(customUrl.value)
})

// Validation Functions
function validateIsraeliPhone(phone: string): boolean {
  const cleaned = phone.replace(/[-\s()]/g, '')
  return cleaned.startsWith('05') && cleaned.length === 10 && /^\d+$/.test(cleaned)
}

function validateUrl(url: string): boolean {
  try {
    // Ensure URL is valid and starts with http/https
    new URL(url)
    return url.startsWith('http://') || url.startsWith('https://')
  } catch {
    return false
  }
}

function validateBitPhone() {
  if (!bitPhoneNumber.value) {
    bitPhoneError.value = ''
    return
  }

  if (!validateIsraeliPhone(bitPhoneNumber.value)) {
    bitPhoneError.value = 'Invalid Israeli phone number. Must be 05X-XXXXXXX format.'
  } else {
    bitPhoneError.value = ''
  }
}

function validatePayboxUrl() {
  if (!payboxUrl.value) {
    payboxUrlError.value = ''
    return
  }

  if (!validateUrl(payboxUrl.value)) {
    payboxUrlError.value = 'Invalid URL. Must start with http:// or https://'
  } else {
    payboxUrlError.value = ''
  }
}

function validateCustomUrl() {
  if (!customUrl.value) {
    customUrlError.value = ''
    return
  }

  if (!validateUrl(customUrl.value)) {
    customUrlError.value = 'Invalid URL. Must start with http:// or https://'
  } else {
    customUrlError.value = ''
  }
}

// API Methods
async function fetchConfig() {
  loading.value = true
  try {
    const response = await apiClient.get('/payments/config')
    currentConfig.value = response.data
  } catch (error) {
    console.error('Failed to fetch payment config:', error)
    showError('Failed to load payment settings')
  } finally {
    loading.value = false
  }
}

function selectMethod(method: 'bit' | 'paybox' | 'bank' | 'custom') {
  selectedMethod.value = method
}

async function saveBitPayment() {
  saving.value = true
  bitPhoneError.value = ''

  try {
    const response = await apiClient.put('/payments/config', {
      payment_link_type: 'bit',
      payment_link_template: bitPhoneNumber.value,
    })

    currentConfig.value = response.data
    selectedMethod.value = null
    isEditing.value = false
    bitPhoneNumber.value = ''

    showSuccess('Bit payment configured successfully')
  } catch (error: unknown) {
    console.error('Failed to save Bit payment:', error)
    const errorMessage =
      (error as { response?: { data?: { detail?: string } } }).response?.data?.detail ||
      'Failed to save Bit payment'
    bitPhoneError.value = errorMessage
    showError(errorMessage)
  } finally {
    saving.value = false
  }
}

async function savePayboxPayment() {
  saving.value = true
  payboxUrlError.value = ''

  try {
    const response = await apiClient.put('/payments/config', {
      payment_link_type: 'paybox',
      payment_link_template: payboxUrl.value,
    })

    currentConfig.value = response.data
    selectedMethod.value = null
    isEditing.value = false
    payboxUrl.value = ''

    showSuccess('PayBox payment configured successfully')
  } catch (error: unknown) {
    console.error('Failed to save PayBox payment:', error)
    const errorMessage =
      (error as { response?: { data?: { detail?: string } } }).response?.data?.detail ||
      'Failed to save PayBox payment'
    payboxUrlError.value = errorMessage
    showError(errorMessage)
  } finally {
    saving.value = false
  }
}

async function saveBankPayment() {
  saving.value = true
  bankDetailsError.value = ''

  try {
    const response = await apiClient.put('/payments/config', {
      payment_link_type: 'bank',
      payment_link_template: bankDetails.value,
      bank_account_details: bankDetails.value, // For backwards compatibility
    })

    currentConfig.value = response.data
    selectedMethod.value = null
    isEditing.value = false
    bankDetails.value = ''

    showSuccess('Bank transfer configured successfully')
  } catch (error: unknown) {
    console.error('Failed to save bank transfer:', error)
    const errorMessage =
      (error as { response?: { data?: { detail?: string } } }).response?.data?.detail ||
      'Failed to save bank transfer'
    bankDetailsError.value = errorMessage
    showError(errorMessage)
  } finally {
    saving.value = false
  }
}

async function saveCustomPayment() {
  saving.value = true
  customUrlError.value = ''

  try {
    const response = await apiClient.put('/payments/config', {
      payment_link_type: 'custom',
      payment_link_template: customUrl.value,
    })

    currentConfig.value = response.data
    selectedMethod.value = null
    isEditing.value = false
    customUrl.value = ''

    showSuccess('Custom link configured successfully')
  } catch (error: unknown) {
    console.error('Failed to save custom link:', error)
    const errorMessage =
      (error as { response?: { data?: { detail?: string } } }).response?.data?.detail ||
      'Failed to save custom link'
    customUrlError.value = errorMessage
    showError(errorMessage)
  } finally {
    saving.value = false
  }
}

async function disablePayments() {
  if (!confirm('Are you sure you want to disable payment tracking?')) {
    return
  }

  saving.value = true
  try {
    const response = await apiClient.put('/payments/config', {
      payment_link_type: null,
      payment_link_template: null,
      bank_account_details: null,
    })

    currentConfig.value = response.data
    selectedMethod.value = null
    isEditing.value = false

    showSuccess('Payment tracking disabled')
  } catch (error) {
    console.error('Failed to disable payments:', error)
    showError('Failed to disable payment tracking')
  } finally {
    saving.value = false
  }
}

function editSettings() {
  isEditing.value = true
  // Pre-populate form based on current type
  if (currentConfig.value?.payment_link_type === 'bit') {
    selectedMethod.value = 'bit'
    bitPhoneNumber.value = currentConfig.value.payment_link_template || ''
  } else if (currentConfig.value?.payment_link_type === 'paybox') {
    selectedMethod.value = 'paybox'
    payboxUrl.value = currentConfig.value.payment_link_template || ''
  } else if (currentConfig.value?.payment_link_type === 'bank') {
    selectedMethod.value = 'bank'
    bankDetails.value = currentConfig.value.payment_link_template || ''
  } else if (currentConfig.value?.payment_link_type === 'custom') {
    selectedMethod.value = 'custom'
    customUrl.value = currentConfig.value.payment_link_template || ''
  }
}

function cancel() {
  selectedMethod.value = null
  isEditing.value = false
  // Clear form fields
  bitPhoneNumber.value = ''
  bitPhoneError.value = ''
  payboxUrl.value = ''
  payboxUrlError.value = ''
  bankDetails.value = ''
  bankDetailsError.value = ''
  customUrl.value = ''
  customUrlError.value = ''
}

async function copyPaymentLink() {
  try {
    await navigator.clipboard.writeText(paymentTemplate.value)
    showSuccess('Payment details copied to clipboard')
  } catch (error) {
    console.error('Failed to copy:', error)
    showError('Failed to copy to clipboard')
  }
}

// Lifecycle
onMounted(() => {
  fetchConfig()
})
</script>

<template>
  <div class="payment-settings">
    <!-- Header -->
    <div class="mb-6">
      <h2 class="mb-2 text-2xl font-semibold text-slate-900">Payment Configuration</h2>
      <p class="text-slate-600">
        Configure how clients can pay you for appointments and sessions
      </p>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex items-center justify-center py-12">
      <LoadingSpinner size="lg" />
    </div>

    <!-- Main Content -->
    <div v-else class="space-y-6">
      <!-- Current Settings Display -->
      <div
        v-if="hasPaymentSettings && !isEditing"
        class="rounded-lg border border-slate-200 bg-white p-6"
      >
        <div class="mb-4 flex items-start justify-between">
          <div>
            <h3 class="mb-1 text-lg font-semibold text-slate-900">
              Current Payment Method: {{ paymentTypeLabel }}
            </h3>
            <p class="text-sm text-slate-600">Your payment method is configured and active</p>
          </div>
          <span class="rounded-full bg-green-100 px-3 py-1 text-sm font-medium text-green-800">
            Active
          </span>
        </div>

        <div class="mb-4 rounded-lg bg-slate-50 p-4">
          <p class="mb-1 text-xs font-medium uppercase text-slate-500">
            Payment Details
          </p>
          <p class="font-mono text-sm text-slate-900">{{ paymentTemplate }}</p>
        </div>

        <div class="flex gap-3">
          <button
            @click="copyPaymentLink"
            type="button"
            class="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-200"
          >
            Copy Details
          </button>
          <button
            @click="editSettings"
            type="button"
            class="rounded-lg bg-blue-100 px-4 py-2 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-200"
          >
            Edit Settings
          </button>
          <button
            @click="disablePayments"
            type="button"
            class="ml-auto rounded-lg bg-red-100 px-4 py-2 text-sm font-medium text-red-700 transition-colors hover:bg-red-200"
            :disabled="saving"
          >
            {{ saving ? 'Disabling...' : 'Disable Payments' }}
          </button>
        </div>
      </div>

      <!-- Payment Method Selector -->
      <div v-if="!hasPaymentSettings || isEditing">
        <h3 class="mb-4 text-lg font-semibold text-slate-900">
          {{ isEditing ? 'Change Payment Method' : 'Choose Payment Method' }}
        </h3>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <!-- Bit Card -->
          <div
            @click="selectMethod('bit')"
            class="cursor-pointer rounded-lg border-2 p-6 transition-all hover:border-blue-500 hover:shadow-md"
            :class="{
              'border-blue-500 bg-blue-50 shadow-md': selectedMethod === 'bit',
              'border-slate-200 bg-white': selectedMethod !== 'bit',
            }"
          >
            <div class="mb-3 text-4xl">💳</div>
            <h4 class="mb-2 font-semibold text-slate-900">Bit (ביט)</h4>
            <p class="text-sm text-slate-600">Israeli mobile payment app</p>
          </div>

          <!-- PayBox Card -->
          <div
            @click="selectMethod('paybox')"
            class="cursor-pointer rounded-lg border-2 p-6 transition-all hover:border-blue-500 hover:shadow-md"
            :class="{
              'border-blue-500 bg-blue-50 shadow-md': selectedMethod === 'paybox',
              'border-slate-200 bg-white': selectedMethod !== 'paybox',
            }"
          >
            <div class="mb-3 text-4xl">💰</div>
            <h4 class="mb-2 font-semibold text-slate-900">PayBox</h4>
            <p class="text-sm text-slate-600">Payment gateway with links</p>
          </div>

          <!-- Bank Transfer Card -->
          <div
            @click="selectMethod('bank')"
            class="cursor-pointer rounded-lg border-2 p-6 transition-all hover:border-blue-500 hover:shadow-md"
            :class="{
              'border-blue-500 bg-blue-50 shadow-md': selectedMethod === 'bank',
              'border-slate-200 bg-white': selectedMethod !== 'bank',
            }"
          >
            <div class="mb-3 text-4xl">🏦</div>
            <h4 class="mb-2 font-semibold text-slate-900">Bank Transfer</h4>
            <p class="text-sm text-slate-600">Manual bank account details</p>
          </div>

          <!-- Custom Link Card -->
          <div
            @click="selectMethod('custom')"
            class="cursor-pointer rounded-lg border-2 p-6 transition-all hover:border-blue-500 hover:shadow-md"
            :class="{
              'border-blue-500 bg-blue-50 shadow-md': selectedMethod === 'custom',
              'border-slate-200 bg-white': selectedMethod !== 'custom',
            }"
          >
            <div class="mb-3 text-4xl">🔗</div>
            <h4 class="mb-2 font-semibold text-slate-900">Custom Link</h4>
            <p class="text-sm text-slate-600">Your own payment link</p>
          </div>
        </div>
      </div>

      <!-- Bit Configuration Form -->
      <div v-if="selectedMethod === 'bit'" class="rounded-lg border border-slate-200 bg-white p-6">
        <h3 class="mb-2 text-lg font-semibold text-slate-900">Configure Bit Payment</h3>
        <p class="mb-4 text-sm text-slate-600">
          Enter your Bit phone number (Israeli format: 05X-XXXXXXX)
        </p>

        <div class="mb-4">
          <label for="bitPhone" class="mb-2 block text-sm font-medium text-slate-900">
            Phone Number
          </label>
          <input
            id="bitPhone"
            v-model="bitPhoneNumber"
            @input="validateBitPhone"
            type="tel"
            placeholder="050-123-4567"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-500"
            :class="{ 'border-red-500': bitPhoneError }"
          />
          <span v-if="bitPhoneError" class="mt-1 block text-sm text-red-600">{{
            bitPhoneError
          }}</span>
        </div>

        <div class="flex gap-3">
          <button
            @click="saveBitPayment"
            type="button"
            class="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="!isValidBitPhone || saving"
          >
            <LoadingSpinner v-if="saving" size="sm" />
            <span>{{ saving ? 'Saving...' : 'Save Bit Payment' }}</span>
          </button>
          <button
            @click="cancel"
            type="button"
            class="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-200"
          >
            Cancel
          </button>
        </div>
      </div>

      <!-- PayBox Configuration Form -->
      <div
        v-if="selectedMethod === 'paybox'"
        class="rounded-lg border border-slate-200 bg-white p-6"
      >
        <h3 class="mb-2 text-lg font-semibold text-slate-900">Configure PayBox Payment</h3>
        <p class="mb-4 text-sm text-slate-600">Enter your PayBox payment page URL</p>

        <div class="mb-4">
          <label for="payboxUrl" class="mb-2 block text-sm font-medium text-slate-900">
            PayBox URL
          </label>
          <input
            id="payboxUrl"
            v-model="payboxUrl"
            @input="validatePayboxUrl"
            type="url"
            placeholder="https://paybox.co.il/p/yourname"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-500"
            :class="{ 'border-red-500': payboxUrlError }"
          />
          <span v-if="payboxUrlError" class="mt-1 block text-sm text-red-600">{{
            payboxUrlError
          }}</span>
        </div>

        <div class="flex gap-3">
          <button
            @click="savePayboxPayment"
            type="button"
            class="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="!isValidPayboxUrl || saving"
          >
            <LoadingSpinner v-if="saving" size="sm" />
            <span>{{ saving ? 'Saving...' : 'Save PayBox Payment' }}</span>
          </button>
          <button
            @click="cancel"
            type="button"
            class="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-200"
          >
            Cancel
          </button>
        </div>
      </div>

      <!-- Bank Transfer Configuration Form -->
      <div
        v-if="selectedMethod === 'bank'"
        class="rounded-lg border border-slate-200 bg-white p-6"
      >
        <h3 class="mb-2 text-lg font-semibold text-slate-900">Configure Bank Transfer</h3>
        <p class="mb-4 text-sm text-slate-600">
          Enter your bank account details that clients will use for transfers
        </p>

        <div class="mb-4">
          <label for="bankDetails" class="mb-2 block text-sm font-medium text-slate-900">
            Bank Account Details
          </label>
          <textarea
            id="bankDetails"
            v-model="bankDetails"
            rows="6"
            placeholder="Bank: Leumi&#10;Account: 12345&#10;Branch: 678&#10;Account Name: Your Name"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-sm focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-500"
            :class="{ 'border-red-500': bankDetailsError }"
          ></textarea>
          <span v-if="bankDetailsError" class="mt-1 block text-sm text-red-600">{{
            bankDetailsError
          }}</span>
        </div>

        <div class="flex gap-3">
          <button
            @click="saveBankPayment"
            type="button"
            class="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="!bankDetails || saving"
          >
            <LoadingSpinner v-if="saving" size="sm" />
            <span>{{ saving ? 'Saving...' : 'Save Bank Transfer' }}</span>
          </button>
          <button
            @click="cancel"
            type="button"
            class="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-200"
          >
            Cancel
          </button>
        </div>
      </div>

      <!-- Custom Link Configuration Form -->
      <div
        v-if="selectedMethod === 'custom'"
        class="rounded-lg border border-slate-200 bg-white p-6"
      >
        <h3 class="mb-2 text-lg font-semibold text-slate-900">Configure Custom Payment Link</h3>
        <p class="mb-4 text-sm text-slate-600">
          Enter your custom payment link URL. You can use variables: {amount}, {client_name},
          {appointment_id}
        </p>

        <div class="mb-4">
          <label for="customUrl" class="mb-2 block text-sm font-medium text-slate-900">
            Payment Link URL
          </label>
          <input
            id="customUrl"
            v-model="customUrl"
            @input="validateCustomUrl"
            type="url"
            placeholder="https://example.com/pay?amount={amount}"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-sm focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-500"
            :class="{ 'border-red-500': customUrlError }"
          />
          <span v-if="customUrlError" class="mt-1 block text-sm text-red-600">{{
            customUrlError
          }}</span>
        </div>

        <div class="mb-4 rounded-lg bg-blue-50 p-4">
          <p class="mb-2 text-sm font-semibold text-slate-900">Available Variables:</p>
          <ul class="space-y-1 text-sm text-slate-700">
            <li>
              <code class="rounded bg-slate-200 px-1 py-0.5">{amount}</code> - Payment amount
              (e.g., 150.00)
            </li>
            <li>
              <code class="rounded bg-slate-200 px-1 py-0.5">{client_name}</code> - Client name
              (URL-encoded)
            </li>
            <li>
              <code class="rounded bg-slate-200 px-1 py-0.5">{appointment_id}</code> - Appointment
              UUID
            </li>
          </ul>
        </div>

        <div class="flex gap-3">
          <button
            @click="saveCustomPayment"
            type="button"
            class="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="!isValidCustomUrl || saving"
          >
            <LoadingSpinner v-if="saving" size="sm" />
            <span>{{ saving ? 'Saving...' : 'Save Custom Link' }}</span>
          </button>
          <button
            @click="cancel"
            type="button"
            class="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-200"
          >
            Cancel
          </button>
        </div>
      </div>

      <!-- Info Section (when no method selected and payments disabled) -->
      <div
        v-if="!hasPaymentSettings && !selectedMethod"
        class="rounded-lg border border-slate-200 bg-slate-50 p-6"
      >
        <div class="flex items-start gap-3">
          <div class="text-2xl">💡</div>
          <div>
            <h4 class="mb-2 font-medium text-slate-900">How Payment Links Work</h4>
            <ol class="list-inside list-decimal space-y-2 text-sm text-slate-700">
              <li>Choose your preferred payment method above</li>
              <li>Configure your payment details (phone number, URL, or bank account)</li>
              <li>
                Send payment requests to clients directly from appointment details
              </li>
              <li>Track which clients have paid and which are pending</li>
            </ol>
            <p class="mt-3 text-sm font-medium text-blue-700">
              Select a payment method above to get started!
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Component-specific styles if needed */
</style>
