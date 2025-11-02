import { ref, computed } from 'vue'
import apiClient from '@/api/client'

/**
 * Payment utilities composable (Phase 1.5: Smart Payment Links)
 *
 * Provides payment-related functionality:
 * - Check if payments are enabled for workspace
 * - Format currency amounts
 * - Get payment status badge info
 * - Get payment mode (manual, smart_link, automated)
 *
 * Phase 1: Manual tracking (bank_account_details)
 * Phase 1.5: Smart payment links (payment_link_type + payment_link_template)
 * Phase 2+: Automated payment provider integration (payment_provider)
 *
 * Usage:
 *   const { paymentsEnabled, formatCurrency, paymentMode } = usePayments()
 *
 *   if (paymentsEnabled.value) {
 *     // Show payment UI
 *   }
 */

/**
 * Payment configuration response from API (Phase 1.5)
 */
interface PaymentConfig {
  payment_mode: 'manual' | 'smart_link' | 'automated' | null
  bank_account_details: string | null
  payment_link_type: 'bit' | 'paybox' | 'bank' | 'custom' | null
  payment_link_template: string | null
  payment_provider: string | null
}

/**
 * Payment status badge configuration
 */
interface PaymentBadge {
  label: string
  color: 'green' | 'yellow' | 'red' | 'gray' | 'purple'
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
        payment_mode: null,
        bank_account_details: null,
        payment_link_type: null,
        payment_link_template: null,
        payment_provider: null,
      }
    } finally {
      configLoading.value = false
    }
  }

  /**
   * Check if payments are enabled for workspace
   * Phase 1: Enabled if bank_account_details is set
   * Phase 1.5: Enabled if payment_link_template is set
   * Phase 2+: Enabled if payment_provider is set
   * Automatically loads config on first access
   */
  const paymentsEnabled = computed(() => {
    // Trigger config load if not yet loaded
    if (!configLoaded.value && !configLoading.value) {
      loadPaymentConfig()
    }

    return paymentConfig.value?.payment_mode !== null
  })

  /**
   * Get current payment mode
   * Returns 'manual', 'smart_link', 'automated', or null
   */
  const paymentMode = computed(() => {
    return paymentConfig.value?.payment_mode || null
  })

  /**
   * Get payment link type (Phase 1.5)
   * Returns 'bit', 'paybox', 'bank', 'custom', or null
   */
  const paymentLinkType = computed(() => {
    return paymentConfig.value?.payment_link_type || null
  })

  /**
   * Get payment link template (Phase 1.5)
   * Returns phone number (Bit), URL (PayBox/custom), bank details, or null
   */
  const paymentLinkTemplate = computed(() => {
    return paymentConfig.value?.payment_link_template || null
  })

  /**
   * Get payment provider name (Phase 2+)
   * Returns provider name or null
   */
  const paymentProvider = computed(() => {
    return paymentConfig.value?.payment_provider || null
  })

  /**
   * Get bank account details for sharing with clients (Phase 1)
   * Deprecated: Use payment_link_template instead (Phase 1.5)
   */
  const bankAccountDetails = computed(() => {
    return paymentConfig.value?.bank_account_details || null
  })

  /**
   * Get payment status badge info for UI display
   *
   * @param status - Payment status (paid, not_paid, payment_sent, waived)
   * @returns Badge configuration or null if no status
   */
  function getPaymentStatusBadge(status: string | null): PaymentBadge | null {
    const badges: Record<string, PaymentBadge> = {
      paid: { label: 'Paid', color: 'green', icon: '💵' },
      not_paid: { label: 'Not Paid', color: 'gray', icon: '⏳' },
      payment_sent: { label: 'Payment Sent', color: 'yellow', icon: '📤' },
      waived: { label: 'Waived', color: 'purple', icon: '🎁' },
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
    paymentMode,
    paymentLinkType,
    paymentLinkTemplate,
    paymentProvider,
    bankAccountDetails,
    configLoading: computed(() => configLoading.value),

    // Methods
    getPaymentStatusBadge,
    formatCurrency,
    loadPaymentConfig,
    refreshPaymentConfig,
  }
}
