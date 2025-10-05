<script setup lang="ts">
import type { Client } from '@/types/client'
import { formatDate } from '@/utils/calendar/dateFormatters'

interface Props {
  client: Client
  isRecent?: boolean
  lastVisitDate?: string | null
  isSelected?: boolean
  isHighlighted?: boolean
}

withDefaults(defineProps<Props>(), {
  isRecent: false,
  lastVisitDate: null,
  isSelected: false,
  isHighlighted: false,
})

/**
 * Get initials from client name for avatar
 */
function getInitials(client: Client): string {
  const first = client.first_name?.[0] || ''
  const last = client.last_name?.[0] || ''
  return (first + last).toUpperCase() || 'C'
}
</script>

<template>
  <div
    :class="[
      'flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors',
      isHighlighted ? 'bg-emerald-50' : 'hover:bg-slate-50',
      isSelected && 'bg-emerald-100',
    ]"
    role="option"
    :aria-selected="isSelected"
  >
    <!-- Avatar with Initials -->
    <div
      :class="[
        'flex h-10 w-10 items-center justify-center rounded-full font-medium text-sm shrink-0',
        isHighlighted || isSelected
          ? 'bg-emerald-200 text-emerald-800'
          : 'bg-slate-100 text-slate-700',
      ]"
    >
      {{ getInitials(client) }}
    </div>

    <!-- Client Info -->
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2">
        <span class="font-medium text-slate-900 truncate">
          {{ client.full_name }}
        </span>
        <span
          v-if="isRecent"
          class="inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 shrink-0"
        >
          Recent
        </span>
      </div>
      <div v-if="lastVisitDate" class="text-sm text-slate-500">
        Last visit: {{ formatDate(lastVisitDate, 'MMM d, yyyy') }}
      </div>
    </div>

    <!-- Selected Check Mark -->
    <div v-if="isSelected" class="shrink-0">
      <svg
        class="h-5 w-5 text-emerald-600"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M5 13l4 4L19 7"
        />
      </svg>
    </div>
  </div>
</template>
