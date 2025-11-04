<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import type { PaymentStatus, PaymentMethod } from '@/types/calendar'
import { useI18n } from '@/composables/useI18n'

interface Props {
  paymentPrice?: number | null
  paymentStatus: PaymentStatus
  paymentMethod?: PaymentMethod | null
  paymentNotes?: string | null
  paidAt?: string | null
  readonly?: boolean
}

interface Emits {
  (e: 'update:paymentPrice', value: number | null): void
  (e: 'update:paymentStatus', value: PaymentStatus): void
  (e: 'update:paymentMethod', value: PaymentMethod | null): void
  (e: 'update:paymentNotes', value: string | null): void
  (e: 'blur', field: 'price' | 'status' | 'method' | 'notes'): void
}

const props = withDefaults(defineProps<Props>(), {
  paymentPrice: null,
  paymentStatus: 'not_paid',
  paymentMethod: null,
  paymentNotes: null,
  paidAt: null,
  readonly: false,
})

const emit = defineEmits<Emits>()

const { t } = useI18n()

// Local state for form fields
const localPrice = ref<number | null>(props.paymentPrice)
const localStatus = ref<PaymentStatus>(props.paymentStatus)
const localMethod = ref<PaymentMethod | null>(props.paymentMethod)
const localNotes = ref<string | null>(props.paymentNotes)

// Sync local state with props
watch(
  () => props.paymentPrice,
  (newValue) => {
    localPrice.value = newValue
  }
)

watch(
  () => props.paymentStatus,
  (newValue) => {
    localStatus.value = newValue
  }
)

watch(
  () => props.paymentMethod,
  (newValue) => {
    localMethod.value = newValue
  }
)

watch(
  () => props.paymentNotes,
  (newValue) => {
    localNotes.value = newValue
  }
)

// Payment status options with badges
const statusOptions = computed(() => [
  {
    value: 'not_paid',
    label: t('calendar.appointmentDetails.payment.statusNotPaid'),
    badgeClass: 'bg-slate-100 text-slate-700',
  },
  {
    value: 'paid',
    label: t('calendar.appointmentDetails.payment.statusPaid'),
    badgeClass: 'bg-emerald-100 text-emerald-700',
  },
  {
    value: 'payment_sent',
    label: t('calendar.appointmentDetails.payment.statusPaymentSent'),
    badgeClass: 'bg-blue-100 text-blue-700',
  },
  {
    value: 'waived',
    label: t('calendar.appointmentDetails.payment.statusWaived'),
    badgeClass: 'bg-purple-100 text-purple-700',
  },
])

// Payment method options (Phase 1: Manual tracking methods)
const methodOptions = computed(() => [
  { value: 'cash', label: t('calendar.appointmentDetails.payment.methodCash') },
  { value: 'card', label: t('calendar.appointmentDetails.payment.methodCard') },
  {
    value: 'bank_transfer',
    label: t('calendar.appointmentDetails.payment.methodBankTransfer'),
  },
  { value: 'bit', label: t('calendar.appointmentDetails.payment.methodBit') },
  { value: 'paybox', label: t('calendar.appointmentDetails.payment.methodPaybox') },
  { value: 'other', label: t('calendar.appointmentDetails.payment.methodOther') },
])

// Get badge class for current status
const currentStatusBadge = computed(() => {
  return statusOptions.value.find((opt) => opt.value === localStatus.value)?.badgeClass || ''
})

// Handle field updates with auto-save on blur
function handlePriceBlur() {
  emit('update:paymentPrice', localPrice.value)
  emit('blur', 'price')
}

function handleStatusChange() {
  emit('update:paymentStatus', localStatus.value)
  emit('blur', 'status')
}

function handleMethodChange() {
  emit('update:paymentMethod', localMethod.value)
  emit('blur', 'method')
}

function handleNotesBlur() {
  emit('update:paymentNotes', localNotes.value)
  emit('blur', 'notes')
}

// Format paid_at timestamp for display
const formattedPaidAt = computed(() => {
  if (!props.paidAt) return null
  const date = new Date(props.paidAt)
  const dateString = date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
  return t('calendar.appointmentDetails.payment.paidAtLabel', { date: dateString })
})
</script>

<template>
  <div class="rounded-lg border border-slate-200 bg-white p-4">
    <h3 class="mb-3 text-sm font-medium text-slate-900">
      {{ t('calendar.appointmentDetails.payment.title') }}
    </h3>

    <!-- Payment Status -->
    <div class="mb-4">
      <label
        for="payment-status"
        class="mb-1.5 block text-xs font-medium text-slate-700"
      >
        {{ t('calendar.appointmentDetails.payment.statusLabel') }}
      </label>
      <select
        id="payment-status"
        v-model="localStatus"
        @change="handleStatusChange"
        :disabled="readonly"
        class="mt-1 block min-h-[44px] w-full rounded-lg border border-slate-300 px-3 py-2 text-base text-slate-900 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 sm:text-sm"
        aria-label="Payment status"
      >
        <option
          v-for="option in statusOptions"
          :key="option.value"
          :value="option.value"
        >
          {{ option.label }}
        </option>
      </select>

      <!-- Status Badge (visual indicator) -->
      <div class="mt-2">
        <span
          :class="currentStatusBadge"
          class="inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium"
        >
          {{ statusOptions.find((opt) => opt.value === localStatus)?.label }}
        </span>
      </div>

      <!-- Paid At Timestamp (shown when status is 'paid') -->
      <div
        v-if="localStatus === 'paid' && formattedPaidAt"
        class="mt-2 text-xs text-slate-500"
      >
        {{ formattedPaidAt }}
      </div>
    </div>

    <!-- Price -->
    <div class="mb-4">
      <label
        for="payment-price"
        class="mb-1.5 block text-xs font-medium text-slate-700"
      >
        {{ t('calendar.appointmentDetails.payment.priceLabel') }}
      </label>
      <input
        id="payment-price"
        v-model.number="localPrice"
        type="number"
        step="0.01"
        min="0"
        :placeholder="t('calendar.appointmentDetails.payment.priceLabel')"
        @blur="handlePriceBlur"
        :disabled="readonly"
        class="mt-1 block min-h-[44px] w-full rounded-lg border border-slate-300 px-3 py-2 text-base text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 sm:text-sm"
        :aria-label="t('calendar.appointmentDetails.payment.priceLabel')"
      />
    </div>

    <!-- Payment Method -->
    <div class="mb-4">
      <label
        for="payment-method"
        class="mb-1.5 block text-xs font-medium text-slate-700"
      >
        {{ t('calendar.appointmentDetails.payment.methodLabel') }}
      </label>
      <select
        id="payment-method"
        v-model="localMethod"
        @change="handleMethodChange"
        :disabled="readonly"
        class="mt-1 block min-h-[44px] w-full rounded-lg border border-slate-300 px-3 py-2 text-base text-slate-900 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 sm:text-sm"
        :aria-label="t('calendar.appointmentDetails.payment.methodLabel')"
      >
        <option :value="null">{{ t('calendar.appointmentDetails.payment.methodLabel') }}</option>
        <option
          v-for="option in methodOptions"
          :key="option.value"
          :value="option.value"
        >
          {{ option.label }}
        </option>
      </select>
    </div>

    <!-- Payment Notes -->
    <div>
      <label
        for="payment-notes"
        class="mb-1.5 block text-xs font-medium text-slate-700"
      >
        {{ t('calendar.appointmentDetails.payment.notesLabel') }}
      </label>
      <textarea
        id="payment-notes"
        v-model="localNotes"
        rows="3"
        :placeholder="t('calendar.appointmentDetails.payment.notesPlaceholder')"
        @blur="handleNotesBlur"
        :disabled="readonly"
        class="mt-1 block min-h-[88px] w-full rounded-lg border border-slate-300 px-3 py-2 text-base text-slate-900 placeholder-slate-400 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500 sm:text-sm"
        :aria-label="t('calendar.appointmentDetails.payment.notesLabel')"
      ></textarea>
    </div>
  </div>
</template>
