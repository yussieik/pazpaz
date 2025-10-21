<script setup lang="ts">
/**
 * PreviousSessionSummaryStrip Component (Tier 1)
 *
 * Mobile-only persistent summary strip that shows one-line preview of previous session.
 * Always visible at top of form on mobile (lg:hidden) to provide constant context.
 *
 * Features:
 * - Sticky positioning above SOAP form fields
 * - Smart field extraction (reuses logic from PreviousSessionSummary)
 * - Loading skeleton state
 * - Tap to expand to Tier 2 (bottom sheet)
 * - Minimal height (48px touch target)
 * - Accessible (keyboard navigation, ARIA labels, screen reader support)
 *
 * Usage:
 *   <PreviousSessionSummaryStrip
 *     :client-id="clientId"
 *     :current-session-id="sessionId"
 *     @expand="openBottomSheet"
 *   />
 */

import { computed } from 'vue'
import { usePreviousSession } from '@/composables/usePreviousSession'
import { formatRelativeDate } from '@/utils/calendar/dateFormatters'

interface Props {
  clientId: string
  currentSessionId?: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'expand'): void
}>()

// Fetch previous session (start in loading state)
const { loading, session, notFound, fetchLatestFinalized } = usePreviousSession(true)

// Smart extraction: Prioritize most clinically relevant field
const keyNote = computed(() => {
  if (!session.value) return null

  const s = session.value

  // 1. Prefer Plan if it contains actionable next steps
  if (s.plan && /continue|follow-up|next|goal|plan|recommend|schedule/i.test(s.plan)) {
    return {
      label: 'Plan',
      content: s.plan,
    }
  }

  // 2. Prefer Assessment if it contains clinical conclusions
  if (
    s.assessment &&
    /diagnosis|improve|progress|assess|condition|prognosis|status/i.test(s.assessment)
  ) {
    return {
      label: 'Assessment',
      content: s.assessment,
    }
  }

  // 3. Prefer Subjective if recent symptom report
  if (
    s.subjective &&
    /pain|symptom|feel|report|complain|describes|states/i.test(s.subjective)
  ) {
    return {
      label: 'Subjective',
      content: s.subjective,
    }
  }

  // 4. Fallback to first non-empty field
  if (s.subjective) return { label: 'Subjective', content: s.subjective }
  if (s.objective) return { label: 'Objective', content: s.objective }
  if (s.assessment) return { label: 'Assessment', content: s.assessment }
  if (s.plan) return { label: 'Plan', content: s.plan }

  return null
})

// Truncate to 80 characters for strip preview
const truncatedPreview = computed(() => {
  if (!keyNote.value) return 'No content'
  const maxLength = 80
  const content = keyNote.value.content
  if (content.length <= maxLength) return content
  return content.substring(0, maxLength).trim() + '...'
})

const relativeDate = computed(() => {
  if (!session.value) return ''
  return formatRelativeDate(session.value.session_date)
})

// Should show: hide if no previous session or if it's the same as current
const shouldShow = computed(() => {
  if (notFound.value) return false
  if (
    session.value &&
    props.currentSessionId &&
    session.value.id === props.currentSessionId
  ) {
    return false
  }
  return true
})

// Handle expand (click, Enter, Space)
function handleExpand() {
  emit('expand')
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    handleExpand()
  }
}

// Fetch when mounted
if (props.clientId) {
  fetchLatestFinalized(props.clientId)
}
</script>

<template>
  <!-- Only show on mobile if there's a previous session -->
  <div
    v-if="shouldShow"
    role="button"
    tabindex="0"
    :aria-label="`Previous session from ${relativeDate}: ${keyNote?.label} - ${truncatedPreview}. Tap to view full treatment context.`"
    class="sticky top-0 z-10 flex min-h-[56px] cursor-pointer items-start gap-3 border-b-2 border-blue-300 bg-blue-50 px-4 py-3 shadow-sm transition-all hover:border-blue-400 hover:bg-blue-100 focus:bg-blue-100 focus:ring-2 focus:ring-blue-500 focus:outline-none focus:ring-inset active:bg-blue-100 lg:hidden"
    @click="handleExpand"
    @keydown="handleKeydown"
  >
    <!-- Loading State -->
    <div v-if="loading" class="flex flex-1 animate-pulse items-center gap-3">
      <div class="h-4 w-24 rounded bg-blue-300"></div>
      <div class="h-4 flex-1 rounded bg-blue-300"></div>
    </div>

    <!-- Content State -->
    <div v-else class="flex flex-1 items-start gap-3 overflow-hidden">
      <!-- Icon with improved styling -->
      <svg
        class="h-5 w-5 flex-shrink-0 text-blue-600"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        aria-hidden="true"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>

      <!-- Two-line layout: metadata row above, content below -->
      <div class="min-w-0 flex-1">
        <!-- Line 1: Label + Date (metadata row) -->
        <div class="mb-1 flex items-center gap-2">
          <span class="text-xs font-semibold tracking-wide text-blue-700 uppercase">
            Previous Session
          </span>
          <span class="text-xs text-gray-500">•</span>
          <span class="text-xs text-gray-600">{{ relativeDate }}</span>
        </div>

        <!-- Line 2: Content preview (readable) -->
        <p class="truncate text-sm leading-tight text-gray-900">
          <span v-if="keyNote" class="font-medium text-gray-700">{{ keyNote.label }}:</span>
          {{ truncatedPreview }}
        </p>
      </div>

      <!-- Chevron Down Icon - Larger with subtle animation -->
      <svg
        class="animate-bounce-subtle h-6 w-6 flex-shrink-0 text-blue-600"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        aria-hidden="true"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2.5"
          d="M19 9l-7 7-7-7"
        />
      </svg>
    </div>
  </div>
</template>

<style scoped>
/* Subtle bounce animation for chevron - draws attention without being annoying */
@keyframes bounce-subtle {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(2px);
  }
}

.animate-bounce-subtle {
  animation: bounce-subtle 2s ease-in-out infinite;
}

/* Disable animation for users who prefer reduced motion */
@media (prefers-reduced-motion: reduce) {
  .animate-bounce-subtle {
    animation: none;
  }
}
</style>
