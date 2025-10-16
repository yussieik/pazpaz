<script setup lang="ts">
/**
 * PreviousSessionSummary Component
 *
 * Displays a compact preview of a previous session with smart field extraction.
 * Prioritizes the most clinically relevant SOAP field based on content analysis.
 *
 * Features:
 * - Smart extraction: Prioritizes Plan → Assessment → Subjective → Objective
 * - Truncated preview (150 chars) for quick scanning
 * - Session metadata: date, relative time, draft status
 * - Click to expand to full detail view
 *
 * Usage:
 *   <PreviousSessionSummary :session="session" @view-full="showDetail" />
 */

import { computed } from 'vue'
import { formatLongDate, formatRelativeDate } from '@/utils/calendar/dateFormatters'
import type { SessionResponse } from '@/types/sessions'

interface Props {
  session: SessionResponse
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'view-full'): void
}>()

// Smart extraction: Prioritize most clinically relevant field
const keyNote = computed(() => {
  const s = props.session

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

// Truncate to 150 characters for preview
const truncatedKeyNote = computed(() => {
  if (!keyNote.value) return null
  const maxLength = 150
  const content = keyNote.value.content
  if (content.length <= maxLength) return content
  return content.substring(0, maxLength).trim() + '...'
})

const sessionDate = computed(() => {
  return formatLongDate(props.session.session_date)
})

const relativeDate = computed(() => {
  return formatRelativeDate(props.session.session_date)
})
</script>

<template>
  <div
    class="rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition-all hover:shadow-md"
  >
    <!-- Header: Date + Status -->
    <div class="mb-3 flex items-start justify-between">
      <div>
        <h4 class="text-sm font-semibold text-gray-900">
          {{ sessionDate }}
        </h4>
        <p class="text-xs text-gray-600">
          {{ relativeDate }}
        </p>
      </div>
      <span
        :class="[
          'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
          session.is_draft
            ? 'bg-blue-100 text-blue-800'
            : 'bg-green-100 text-green-800',
        ]"
      >
        {{ session.is_draft ? 'Draft' : 'Finalized' }}
      </span>
    </div>

    <!-- Key Note Preview -->
    <div v-if="keyNote" class="mb-3">
      <p class="mb-1 text-xs font-semibold text-gray-700">{{ keyNote.label }}:</p>
      <p class="text-sm leading-relaxed text-gray-700">
        {{ truncatedKeyNote }}
      </p>
    </div>

    <!-- No Content State -->
    <div v-else class="mb-3">
      <span
        class="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs text-gray-600"
      >
        Draft - incomplete
      </span>
    </div>

    <!-- View Full Note Button -->
    <button
      @click="emit('view-full')"
      class="text-sm font-medium text-blue-600 transition-colors hover:text-blue-700 focus:underline focus:outline-none"
      type="button"
    >
      View Full Note →
    </button>
  </div>
</template>
