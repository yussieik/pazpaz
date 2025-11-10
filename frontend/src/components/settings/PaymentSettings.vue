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
import { useI18n } from '@/composables/useI18n'
import { usePayments } from '@/composables/usePayments'
import apiClient from '@/api/client'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import IconBitLogo from '@/components/icons/IconBitLogo.vue'

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
const { t } = useI18n()
const { refreshPaymentConfig } = usePayments()

// Computed
const paymentTypeLabel = computed(() => {
  const type = currentConfig.value?.payment_link_type
  if (!type) return ''
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return t(`settings.payments.methods.${type}` as any)
})

const paymentTemplate = computed(() => currentConfig.value?.payment_link_template || '')

const isValidBitPhone = computed(() => {
  if (!bitPhoneNumber.value) return false
  // Accept either phone number or URL
  return validateIsraeliPhone(bitPhoneNumber.value) || validateUrl(bitPhoneNumber.value)
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

  // Accept either phone number or URL
  const isPhone = validateIsraeliPhone(bitPhoneNumber.value)
  const isUrl = validateUrl(bitPhoneNumber.value)

  if (!isPhone && !isUrl) {
    bitPhoneError.value = t('settings.payments.bit.errorInvalid')
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
    payboxUrlError.value = t('settings.payments.paybox.errorInvalid')
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
    customUrlError.value = t('settings.payments.custom.errorInvalid')
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
    showError(t('settings.payments.toasts.loadError'))
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

    // Refresh global payment config cache
    await refreshPaymentConfig()

    showSuccess(t('settings.payments.toasts.bitSuccess'))
  } catch (error: unknown) {
    console.error('Failed to save Bit payment:', error)
    const errorMessage =
      (error as { response?: { data?: { detail?: string } } }).response?.data?.detail ||
      t('settings.payments.toasts.bitError')
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

    // Refresh global payment config cache
    await refreshPaymentConfig()

    showSuccess(t('settings.payments.toasts.payboxSuccess'))
  } catch (error: unknown) {
    console.error('Failed to save PayBox payment:', error)
    const errorMessage =
      (error as { response?: { data?: { detail?: string } } }).response?.data?.detail ||
      t('settings.payments.toasts.payboxError')
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

    // Refresh global payment config cache
    await refreshPaymentConfig()

    showSuccess(t('settings.payments.toasts.bankSuccess'))
  } catch (error: unknown) {
    console.error('Failed to save bank transfer:', error)
    const errorMessage =
      (error as { response?: { data?: { detail?: string } } }).response?.data?.detail ||
      t('settings.payments.toasts.bankError')
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

    // Refresh global payment config cache
    await refreshPaymentConfig()

    showSuccess(t('settings.payments.toasts.customSuccess'))
  } catch (error: unknown) {
    console.error('Failed to save custom link:', error)
    const errorMessage =
      (error as { response?: { data?: { detail?: string } } }).response?.data?.detail ||
      t('settings.payments.toasts.customError')
    customUrlError.value = errorMessage
    showError(errorMessage)
  } finally {
    saving.value = false
  }
}

async function disablePayments() {
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

    // Refresh global payment config cache
    await refreshPaymentConfig()

    showSuccess(t('settings.payments.toasts.disableSuccess'))
  } catch (error) {
    console.error('Failed to disable payments:', error)
    showError(t('settings.payments.toasts.disableError'))
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
    showSuccess(t('settings.payments.toasts.copySuccess'))
  } catch (error) {
    console.error('Failed to copy:', error)
    showError(t('settings.payments.toasts.copyError'))
  }
}

// Lifecycle
onMounted(() => {
  fetchConfig()
})
</script>

<template>
  <div class="payment-settings">
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
              {{
                t('settings.payments.currentSettings.title', {
                  method: paymentTypeLabel,
                })
              }}
            </h3>
            <p class="text-sm text-slate-600">
              {{ t('settings.payments.currentSettings.description') }}
            </p>
          </div>
          <span
            class="rounded-full bg-green-100 px-3 py-1 text-sm font-medium text-green-800"
          >
            {{ t('settings.payments.currentSettings.active') }}
          </span>
        </div>

        <div class="mb-4 rounded-lg bg-slate-50 p-4">
          <p class="mb-1 text-xs font-medium text-slate-500 uppercase">
            {{ t('settings.payments.currentSettings.paymentDetailsLabel') }}
          </p>
          <p class="font-mono text-sm text-slate-900">{{ paymentTemplate }}</p>
        </div>

        <div class="flex gap-3">
          <button
            @click="copyPaymentLink"
            type="button"
            class="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-200"
          >
            {{ t('settings.payments.currentSettings.copyButton') }}
          </button>
          <button
            @click="editSettings"
            type="button"
            class="rounded-lg bg-blue-100 px-4 py-2 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-200"
          >
            {{ t('settings.payments.currentSettings.editButton') }}
          </button>
          <button
            @click="disablePayments"
            type="button"
            class="ml-auto rounded-lg bg-red-100 px-4 py-2 text-sm font-medium text-red-700 transition-colors hover:bg-red-200"
            :disabled="saving"
          >
            {{
              saving
                ? t('settings.payments.currentSettings.disabling')
                : t('settings.payments.currentSettings.disableButton')
            }}
          </button>
        </div>
      </div>

      <!-- Payment Method Selector -->
      <div v-if="!hasPaymentSettings || isEditing">
        <div class="grid grid-cols-1 gap-4">
          <!-- Bit Card -->
          <div
            @click="selectMethod('bit')"
            class="cursor-pointer rounded-lg border-2 p-6 transition-all hover:border-blue-500 hover:shadow-md"
            :class="{
              'border-blue-500 bg-blue-50 shadow-md': selectedMethod === 'bit',
              'border-slate-200 bg-white': selectedMethod !== 'bit',
            }"
          >
            <div class="flex items-center gap-3">
              <IconBitLogo class="h-12 w-12" />
              <h4 class="font-semibold text-slate-900">Bit (ביט)</h4>
            </div>
          </div>
        </div>
      </div>

      <!-- Bit Configuration Form -->
      <div
        v-if="selectedMethod === 'bit'"
        class="rounded-lg border border-slate-200 bg-white p-6"
      >
        <h3 class="mb-2 text-lg font-semibold text-slate-900">
          {{ t('settings.payments.bit.title') }}
        </h3>
        <p class="mb-4 text-sm text-slate-600">
          {{ t('settings.payments.bit.description') }}
        </p>

        <div class="mb-4">
          <label for="bitPhone" class="mb-2 block text-sm font-medium text-slate-900">
            {{ t('settings.payments.bit.label') }}
          </label>
          <input
            id="bitPhone"
            v-model="bitPhoneNumber"
            @input="validateBitPhone"
            type="text"
            :placeholder="t('settings.payments.bit.placeholder')"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 focus:border-transparent focus:ring-2 focus:ring-blue-500 focus:outline-none"
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
            <span>{{
              saving
                ? t('settings.payments.bit.saving')
                : t('settings.payments.bit.saveButton')
            }}</span>
          </button>
          <button
            @click="cancel"
            type="button"
            class="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-200"
          >
            {{ t('settings.payments.common.cancelButton') }}
          </button>
        </div>
      </div>

      <!-- PayBox Configuration Form -->
      <div
        v-if="selectedMethod === 'paybox'"
        class="rounded-lg border border-slate-200 bg-white p-6"
      >
        <h3 class="mb-2 text-lg font-semibold text-slate-900">
          {{ t('settings.payments.paybox.title') }}
        </h3>
        <p class="mb-4 text-sm text-slate-600">
          {{ t('settings.payments.paybox.description') }}
        </p>

        <div class="mb-4">
          <label for="payboxUrl" class="mb-2 block text-sm font-medium text-slate-900">
            {{ t('settings.payments.paybox.label') }}
          </label>
          <input
            id="payboxUrl"
            v-model="payboxUrl"
            @input="validatePayboxUrl"
            type="url"
            :placeholder="t('settings.payments.paybox.placeholder')"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 focus:border-transparent focus:ring-2 focus:ring-blue-500 focus:outline-none"
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
            <span>{{
              saving
                ? t('settings.payments.paybox.saving')
                : t('settings.payments.paybox.saveButton')
            }}</span>
          </button>
          <button
            @click="cancel"
            type="button"
            class="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-200"
          >
            {{ t('settings.payments.common.cancelButton') }}
          </button>
        </div>
      </div>

      <!-- Bank Transfer Configuration Form -->
      <div
        v-if="selectedMethod === 'bank'"
        class="rounded-lg border border-slate-200 bg-white p-6"
      >
        <h3 class="mb-2 text-lg font-semibold text-slate-900">
          {{ t('settings.payments.bank.title') }}
        </h3>
        <p class="mb-4 text-sm text-slate-600">
          {{ t('settings.payments.bank.description') }}
        </p>

        <div class="mb-4">
          <label
            for="bankDetails"
            class="mb-2 block text-sm font-medium text-slate-900"
          >
            {{ t('settings.payments.bank.label') }}
          </label>
          <textarea
            id="bankDetails"
            v-model="bankDetails"
            rows="6"
            :placeholder="t('settings.payments.bank.placeholder')"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-sm focus:border-transparent focus:ring-2 focus:ring-blue-500 focus:outline-none"
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
            <span>{{
              saving
                ? t('settings.payments.bank.saving')
                : t('settings.payments.bank.saveButton')
            }}</span>
          </button>
          <button
            @click="cancel"
            type="button"
            class="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-200"
          >
            {{ t('settings.payments.common.cancelButton') }}
          </button>
        </div>
      </div>

      <!-- Custom Link Configuration Form -->
      <div
        v-if="selectedMethod === 'custom'"
        class="rounded-lg border border-slate-200 bg-white p-6"
      >
        <h3 class="mb-2 text-lg font-semibold text-slate-900">
          {{ t('settings.payments.custom.title') }}
        </h3>
        <p class="mb-4 text-sm text-slate-600">
          {{ t('settings.payments.custom.description') }}
        </p>

        <div class="mb-4">
          <label for="customUrl" class="mb-2 block text-sm font-medium text-slate-900">
            {{ t('settings.payments.custom.label') }}
          </label>
          <input
            id="customUrl"
            v-model="customUrl"
            @input="validateCustomUrl"
            type="url"
            :placeholder="t('settings.payments.custom.placeholder')"
            class="w-full rounded-lg border border-slate-300 px-3 py-2 font-mono text-sm focus:border-transparent focus:ring-2 focus:ring-blue-500 focus:outline-none"
            :class="{ 'border-red-500': customUrlError }"
          />
          <span v-if="customUrlError" class="mt-1 block text-sm text-red-600">{{
            customUrlError
          }}</span>
        </div>

        <div class="mb-4 rounded-lg bg-blue-50 p-4">
          <p class="mb-2 text-sm font-semibold text-slate-900">
            {{ t('settings.payments.custom.variablesTitle') }}
          </p>
          <ul class="space-y-1 text-sm text-slate-700">
            <li>
              <code class="rounded bg-slate-200 px-1 py-0.5">{amount}</code> -
              {{ t('settings.payments.custom.variableAmount') }}
            </li>
            <li>
              <code class="rounded bg-slate-200 px-1 py-0.5">{client_name}</code> -
              {{ t('settings.payments.custom.variableClientName') }}
            </li>
            <li>
              <code class="rounded bg-slate-200 px-1 py-0.5">{appointment_id}</code> -
              {{ t('settings.payments.custom.variableAppointmentId') }}
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
            <span>{{
              saving
                ? t('settings.payments.custom.saving')
                : t('settings.payments.custom.saveButton')
            }}</span>
          </button>
          <button
            @click="cancel"
            type="button"
            class="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-200"
          >
            {{ t('settings.payments.common.cancelButton') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Component-specific styles if needed */
</style>
