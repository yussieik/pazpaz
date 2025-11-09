<script setup lang="ts">
/**
 * PaymentDetailsForm - Price and Status Fields
 *
 * Presentational component for payment price and status inputs.
 * November 2025 best practices: Pure presentational component with no business logic.
 *
 * Usage:
 *   <PaymentDetailsForm
 *     v-model:price="price"
 *     v-model:status="status"
 *     @update:price="handlePriceChange"
 *     @update:status="handleStatusChange"
 *   />
 */

import { computed } from 'vue'

interface Props {
  price: number | null
  status: 'not_paid' | 'paid' | 'payment_sent' | 'waived'
  readonly?: boolean
}

interface Emits {
  (e: 'update:price', value: number | null): void
  (e: 'update:status', value: string): void
}

const props = withDefaults(defineProps<Props>(), {
  readonly: false,
})

const emit = defineEmits<Emits>()

// Local computed for v-model binding
const localPrice = computed({
  get: () => props.price,
  set: (value) => emit('update:price', value),
})

const localStatus = computed({
  get: () => props.status,
  set: (value) => emit('update:status', value),
})

/**
 * Payment status label mapping
 */
function getPaymentStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    not_paid: 'Not Paid',
    paid: 'Paid',
    payment_sent: 'Request Sent',
    waived: 'Waived',
  }
  return labels[status] || 'Unknown'
}
</script>

<template>
  <div class="space-y-4">
    <!-- Price Input -->
    <div>
      <label
        for="payment-price"
        class="mb-1.5 block text-sm font-medium text-slate-700"
      >
        Price (₪)
      </label>
      <input
        id="payment-price"
        v-model.number="localPrice"
        type="number"
        step="0.01"
        min="0"
        placeholder="Enter price"
        :disabled="readonly"
        class="block min-h-[44px] w-full rounded-lg border border-slate-300 px-3 py-2 text-base text-slate-900 placeholder-slate-400 transition-colors focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:bg-slate-50 disabled:text-slate-500 sm:text-sm"
      />
    </div>

    <!-- Payment Status Dropdown -->
    <div>
      <label
        for="payment-status"
        class="mb-1.5 block text-sm font-medium text-slate-700"
      >
        Status
      </label>
      <select
        id="payment-status"
        v-model="localStatus"
        :disabled="readonly"
        class="block min-h-[44px] w-full rounded-lg border border-slate-300 px-3 py-2 text-base text-slate-900 transition-colors focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:bg-slate-50 disabled:text-slate-500 sm:text-sm"
      >
        <option value="not_paid">{{ getPaymentStatusLabel('not_paid') }}</option>
        <option value="paid">{{ getPaymentStatusLabel('paid') }}</option>
        <option value="payment_sent">
          {{ getPaymentStatusLabel('payment_sent') }}
        </option>
        <option value="waived">{{ getPaymentStatusLabel('waived') }}</option>
      </select>
    </div>

    <!-- Helper text -->
    <p class="text-xs text-slate-500">
      Set price and status to track payment for this appointment
    </p>
  </div>
</template>
