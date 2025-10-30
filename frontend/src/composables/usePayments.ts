import { ref, computed } from 'vue'
import apiClient from '@/api/client'

/**
 * Payment utilities composable
 *
 * Provides payment-related functionality:
 * - Check if payments are enabled for workspace
 * - Validate payment request eligibility
 * - Format currency amounts
 * - Get payment status badge info
 *
 * Usage:
 *   const { paymentsEnabled, canSendPaymentRequest, formatCurrency } = usePayments()
 *
 *   if (paymentsEnabled.value) {
 *     // Show payment UI
 *   }
 */

/**
 * Payment configuration response from API
 */
interface PaymentConfig {
  enabled: boolean
  provider: string | null
  auto_send: boolean
  send_timing: 'immediately' | 'end_of_day' | 'end_of_month' | 'manual'
}

/**
 * Payment status badge configuration
 */
interface PaymentBadge {
  label: string
  color: 'green' | 'yellow' | 'red' | 'gray'
  icon: string
}

// Global state for payment configuration
// Shared across all instances to avoid duplicate API calls
const paymentConfig = ref<PaymentConfig | null>(null)
const configLoading = ref(false)
const configLoaded = ref(false)

export function usePayments() {
  /**
   * Load payment configuration from API
   * Only loads once and caches the result
   */
  async function loadPaymentConfig(): Promise<void> {
    // Skip if already loaded or currently loading
    if (configLoaded.value || configLoading.value) {
      return
    }

    configLoading.value = true

    try {
      const response = await apiClient.get<PaymentConfig>('/payments/config')
      paymentConfig.value = response.data
      configLoaded.value = true
    } catch (error) {
      console.error('[usePayments] Failed to load payment config:', error)
      // Default to disabled on error
      paymentConfig.value = {
        enabled: false,
        provider: null,
        auto_send: false,
        send_timing: 'manual',
      }
    } finally {
      configLoading.value = false
    }
  }

  /**
   * Check if payments are enabled for workspace
   * Automatically loads config on first access
   */
  const paymentsEnabled = computed(() => {
    // Trigger config load if not yet loaded
    if (!configLoaded.value && !configLoading.value) {
      loadPaymentConfig()
    }

    return paymentConfig.value?.enabled || false
  })

  /**
   * Get payment provider name
   */
  const paymentProvider = computed(() => {
    return paymentConfig.value?.provider || null
  })

  /**
   * Check if can send payment request for appointment
   *
   * Validation rules (all must pass):
   * 1. Payments enabled for workspace
   * 2. Appointment has a price set
   * 3. Not already paid
   * 4. Appointment is completed (attended)
   *
   * @param appointment - Appointment to check
   * @returns true if payment request can be sent
   */
  function canSendPaymentRequest(appointment: {
    payment_price?: number | null
    payment_status?: string | null
    status: string
  }): boolean {
    if (!paymentsEnabled.value) return false
    if (!appointment.payment_price) return false
    if (appointment.payment_status === 'paid') return false
    if (appointment.status !== 'attended') return false

    return true
  }

  /**
   * Get payment status badge info for UI display
   *
   * @param status - Payment status (paid, pending, failed, refunded)
   * @returns Badge configuration or null if no status
   */
  function getPaymentStatusBadge(status: string | null): PaymentBadge | null {
    const badges: Record<string, PaymentBadge> = {
      paid: { label: 'Paid', color: 'green', icon: '💵' },
      pending: { label: 'Pending', color: 'yellow', icon: '🔄' },
      failed: { label: 'Failed', color: 'red', icon: '❌' },
      refunded: { label: 'Refunded', color: 'gray', icon: '↩' },
    }

    return status ? badges[status] || null : null
  }

  /**
   * Format currency amount for display
   *
   * @param amount - Amount to format
   * @param currency - Currency code (ILS, USD, EUR)
   * @returns Formatted string (e.g., "₪ 150.00")
   */
  function formatCurrency(
    amount: number,
    currency: 'ILS' | 'USD' | 'EUR' = 'ILS'
  ): string {
    const symbols: Record<string, string> = {
      ILS: '₪',
      USD: '$',
      EUR: '€',
    }

    return `${symbols[currency] || currency} ${amount.toFixed(2)}`
  }

  /**
   * Refresh payment configuration from API
   * Useful after updating payment settings
   */
  async function refreshPaymentConfig(): Promise<void> {
    configLoaded.value = false
    await loadPaymentConfig()
  }

  return {
    // State
    paymentsEnabled,
    paymentProvider,
    configLoading: computed(() => configLoading.value),

    // Methods
    canSendPaymentRequest,
    getPaymentStatusBadge,
    formatCurrency,
    loadPaymentConfig,
    refreshPaymentConfig,
  }
}
