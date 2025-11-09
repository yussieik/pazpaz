<script setup lang="ts">
/**
 * PaymentActions - Action Buttons for Payment Requests
 *
 * Presentational component for payment action buttons (send request, copy link).
 * November 2025 best practices: Stateless component with clear prop interfaces.
 *
 * Usage:
 *   <PaymentActions
 *     :price="price"
 *     :status="status"
 *     :sending="sending"
 *     :sent="sent"
 *     @send-payment-request="handleSend"
 *     @copy-payment-link="handleCopy"
 *   />
 */

import { computed } from 'vue'
import IconSend from '@/components/icons/IconSend.vue'
import IconRefresh from '@/components/icons/IconRefresh.vue'
import IconCheck from '@/components/icons/IconCheck.vue'
import IconCopy from '@/components/icons/IconCopy.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

interface Props {
  price: number | null
  status: 'not_paid' | 'paid' | 'payment_sent' | 'waived'
  readonly?: boolean
  sending?: boolean
  sent?: boolean
  copying?: boolean
  copied?: boolean
}

interface Emits {
  (e: 'send-payment-request'): void
  (e: 'copy-payment-link'): void
}

const props = withDefaults(defineProps<Props>(), {
  readonly: false,
  sending: false,
  sent: false,
  copying: false,
  copied: false,
})

const emit = defineEmits<Emits>()

/**
 * Show send payment request button when price is set and > 0
 */
const showSendButton = computed(() => {
  return props.price !== null && props.price > 0
})

/**
 * Show copy link button when price is set and not paid
 */
const showCopyButton = computed(() => {
  return props.price !== null && props.price > 0 && props.status !== 'paid'
})

/**
 * Determines button label and styling for payment request action
 */
const sendButtonState = computed(() => {
  // Loading state
  if (props.sending) {
    return {
      label: 'Sending...',
      icon: null,
      variant: 'primary',
      disabled: true,
      showSpinner: true,
    }
  }

  // Success state (brief)
  if (props.sent) {
    return {
      label: 'Sent!',
      icon: 'check',
      variant: 'success',
      disabled: true,
      showSpinner: false,
    }
  }

  // Resend state (after payment_sent)
  if (props.status === 'payment_sent') {
    return {
      label: 'Resend Payment Request',
      icon: 'refresh',
      variant: 'secondary',
      disabled: false,
      showSpinner: false,
    }
  }

  // Initial send state
  return {
    label: 'Send Payment Request',
    icon: 'send',
    variant: 'primary',
    disabled: !props.price,
    showSpinner: false,
  }
})

/**
 * Copy button state
 */
const copyButtonState = computed(() => {
  if (props.copying) {
    return {
      label: 'Copying...',
      icon: null,
      disabled: true,
      showSpinner: true,
    }
  }

  if (props.copied) {
    return {
      label: 'Copied!',
      icon: 'check',
      disabled: true,
      showSpinner: false,
    }
  }

  return {
    label: 'Copy Payment Link',
    icon: 'copy',
    disabled: false,
    showSpinner: false,
  }
})
</script>

<template>
  <!-- Hide action buttons when in readonly mode -->
  <div v-if="!readonly" class="space-y-3">
    <!-- Send Payment Request Button -->
    <button
      v-if="showSendButton"
      @click="emit('send-payment-request')"
      :disabled="sendButtonState.disabled"
      :class="[
        'flex min-h-[44px] w-full items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-all duration-200',
        sendButtonState.variant === 'primary' &&
          'bg-emerald-600 text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50',
        sendButtonState.variant === 'secondary' &&
          'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50',
        sendButtonState.variant === 'success' &&
          'cursor-default bg-emerald-600 text-white opacity-95',
      ]"
    >
      <LoadingSpinner v-if="sendButtonState.showSpinner" size="sm" />
      <IconSend
        v-else-if="sendButtonState.icon === 'send'"
        class="h-4 w-4"
        aria-hidden="true"
      />
      <IconRefresh
        v-else-if="sendButtonState.icon === 'refresh'"
        class="h-4 w-4"
        aria-hidden="true"
      />
      <IconCheck
        v-else-if="sendButtonState.icon === 'check'"
        class="h-4 w-4"
        aria-hidden="true"
      />
      <span>{{ sendButtonState.label }}</span>
    </button>

    <!-- Copy Payment Link Button -->
    <button
      v-if="showCopyButton"
      @click="emit('copy-payment-link')"
      :disabled="copyButtonState.disabled"
      class="flex min-h-[44px] w-full items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition-all duration-200 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
    >
      <LoadingSpinner v-if="copyButtonState.showSpinner" size="sm" color="slate" />
      <IconCopy
        v-else-if="copyButtonState.icon === 'copy'"
        class="h-4 w-4"
        aria-hidden="true"
      />
      <IconCheck
        v-else-if="copyButtonState.icon === 'check'"
        class="h-4 w-4"
        aria-hidden="true"
      />
      <span>{{ copyButtonState.label }}</span>
    </button>

    <!-- Info message (no price set) -->
    <div
      v-if="!price"
      class="flex items-center gap-2 rounded-lg bg-blue-50 px-3 py-2 text-xs text-blue-700"
    >
      <svg
        class="h-4 w-4 flex-shrink-0"
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
      <span>Set a price above to send payment requests</span>
    </div>
  </div>

  <!-- Read-only message when payments are disabled -->
  <div v-else class="rounded-lg bg-slate-50 p-4 text-center">
    <p class="text-sm text-slate-600">
      Payment actions are not available because payments are currently disabled in your
      workspace settings.
    </p>
    <p class="mt-2 text-xs text-slate-500">
      Payment data is preserved from when payments were enabled.
    </p>
  </div>
</template>
