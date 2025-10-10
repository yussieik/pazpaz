<script setup lang="ts">
/**
 * AppointmentToastContent - Rich toast content for appointment notifications
 *
 * Displays appointment-related information with action buttons in vue-toastification.
 * Used for creation, scheduling, and other important appointment actions.
 *
 * Features:
 * - Displays message, client name, and datetime
 * - Supports multiple action buttons (e.g., View Details, View in Calendar)
 * - Accessible button styling with focus states
 * - Optimized for 5-second display duration
 */
interface Props {
  message: string
  clientName?: string
  datetime?: string
  actions?: Array<{ label: string; onClick: () => void }>
}

defineProps<Props>()
</script>

<template>
  <div class="flex min-w-[300px] items-start gap-3">
    <div class="min-w-0 flex-1">
      <p class="text-sm font-medium">{{ message }}</p>
      <p v-if="clientName || datetime" class="mt-0.5 text-xs opacity-90">
        <span v-if="clientName">{{ clientName }}</span>
        <span v-if="clientName && datetime" class="mx-1">•</span>
        <span v-if="datetime">{{ datetime }}</span>
      </p>
    </div>
    <div
      v-if="actions && actions.length > 0"
      class="flex flex-shrink-0 items-center gap-2"
    >
      <button
        v-for="action in actions"
        :key="action.label"
        @click.stop="action.onClick"
        class="rounded px-2 py-1 text-xs font-medium underline transition-colors hover:no-underline focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-emerald-600 focus:outline-none"
      >
        {{ action.label }}
      </button>
    </div>
  </div>
</template>
