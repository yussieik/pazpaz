<script setup lang="ts">
import { computed } from 'vue'
import { formatDistanceToNow } from 'date-fns'
import type { SessionWithAmendments } from '@/types/calendar'

interface Props {
  session: Partial<SessionWithAmendments>
}

const props = defineProps<Props>()

/**
 * Check if session is draft (not finalized)
 */
const isDraft = computed(() => {
  return !props.session.finalized_at
})

/**
 * Check if session has been amended
 */
const isAmended = computed(() => {
  return !!props.session.amended_at
})

/**
 * Format relative time for tooltips
 */
function formatRelativeTime(isoString: string | null | undefined): string {
  if (!isoString) return ''
  return formatDistanceToNow(new Date(isoString), { addSuffix: true })
}
</script>

<template>
  <div class="flex items-center gap-2 min-w-[140px]">
    <!-- Status Badge - Single element that transitions between states -->
    <span
      class="inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium tracking-wide uppercase badge-transition"
      :class="{
        'bg-blue-100 text-blue-700': isDraft,
        'bg-green-100 text-green-700': !isDraft
      }"
      :title="isDraft ? 'This note is still in draft mode' : `Finalized ${formatRelativeTime(session.finalized_at)}`"
    >
      <!-- Draft Icon -->
      <svg v-if="isDraft" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
        />
      </svg>

      <!-- Finalized Icon -->
      <svg v-else class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>

      {{ isDraft ? 'Draft' : 'Finalized' }}
    </span>

    <!-- Amended Badge (only if amended) -->
    <span
      v-if="isAmended"
      class="inline-flex items-center gap-1 rounded bg-amber-100 px-2 py-1 text-xs font-medium tracking-wide text-amber-700 uppercase badge-transition"
      :title="`Amended ${formatRelativeTime(session.amended_at)}`"
    >
      <svg class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
        />
      </svg>
      Amended
      <span v-if="session.amendment_count && session.amendment_count > 1">
        ({{ session.amendment_count }}x)
      </span>
    </span>
  </div>
</template>

<style scoped>
/* Smooth transitions for badge state changes */
.badge-transition {
  transition: background-color 0.2s ease-in-out, color 0.2s ease-in-out, transform 0.15s ease-in-out;
}
</style>
