<script setup lang="ts">
/**
 * AgentCitationCard Component
 *
 * Displays a session citation reference from AI agent responses
 * Shows session metadata and links to the full session details
 *
 * Features:
 * - Session date formatting
 * - Similarity score display
 * - SOAP field indicator
 * - Click to navigate to session
 * - RTL support via i18n
 */

import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from '@/composables/useI18n'
import type { Citation } from '@/composables/useAIAgent'

interface Props {
  citation: Citation
}

const props = defineProps<Props>()
const router = useRouter()
const { t } = useI18n()

// Format session date (only for session citations)
const formattedDate = computed(() => {
  if (props.citation.type === 'session') {
    const date = new Date(props.citation.session_date)
    return date.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  }
  return null
})

// Format similarity as percentage
const similarityPercent = computed(() => {
  return Math.round(props.citation.similarity * 100)
})

// Get SOAP field display name
const fieldDisplayName = computed(() => {
  const fieldMap: Record<string, string> = {
    subjective: t('sessions.editor.fields.subjective.label'),
    objective: t('sessions.editor.fields.objective.label'),
    assessment: t('sessions.editor.fields.assessment.label'),
    plan: t('sessions.editor.fields.plan.label'),
  }
  return fieldMap[props.citation.field_name] || props.citation.field_name
})

// Similarity-based color for accent bar
const similarityColorClass = computed(() => {
  const sim = props.citation.similarity
  if (sim >= 0.7) return 'from-emerald-500 to-emerald-400'
  if (sim >= 0.5) return 'from-blue-500 to-blue-400'
  return 'from-slate-400 to-slate-300'
})

// Human-readable relevance
const relevanceLabel = computed(() => {
  const sim = props.citation.similarity
  if (sim >= 0.8) return t('aiAgent.citations.highRelevance')
  if (sim >= 0.6) return t('aiAgent.citations.mediumRelevance')
  return t('aiAgent.citations.lowRelevance')
})

// SOAP field color coding
const soapFieldColorClass = computed(() => {
  const fieldColors: Record<string, string> = {
    subjective: 'bg-blue-100 text-blue-700',
    objective: 'bg-purple-100 text-purple-700',
    assessment: 'bg-amber-100 text-amber-700',
    plan: 'bg-emerald-100 text-emerald-700',
  }
  return fieldColors[props.citation.field_name] || 'bg-slate-100 text-slate-700'
})

// Navigate to citation source
function navigateToCitation() {
  if (props.citation.type === 'session') {
    // Navigate to session detail page
    // Browser back button will return to AI chat naturally
    router.push({
      name: 'session-detail',
      params: { id: props.citation.session_id },
    })
  } else if (props.citation.type === 'client') {
    // Navigate to client detail page with AI assistant tab
    // Use replace to avoid adding extra history entry
    router.replace({
      name: 'client-detail',
      params: { id: props.citation.client_id },
      query: { tab: 'ai-assistant' },
    })
  }
}
</script>

<template>
  <button
    type="button"
    class="group relative w-full overflow-hidden rounded-lg border border-slate-200 bg-white p-3 text-start transition-all hover:border-emerald-400 hover:shadow-md focus:ring-2 focus:ring-emerald-500 focus:ring-offset-1 focus:outline-none"
    @click="navigateToCitation"
  >
    <!-- Similarity indicator as left accent bar -->
    <div
      class="absolute inset-y-0 left-0 w-1 bg-gradient-to-b transition-all"
      :class="similarityColorClass"
      :style="{ opacity: citation.similarity }"
    />

    <div class="flex items-start gap-3 pl-2">
      <!-- Session icon -->
      <div
        class="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 transition-colors group-hover:bg-emerald-100"
      >
        <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        </svg>
      </div>

      <!-- Content -->
      <div class="min-w-0 flex-1">
        <!-- Client name and date -->
        <div class="flex items-baseline gap-2">
          <p class="truncate font-medium text-slate-900">
            {{ citation.client_name }}
          </p>
          <template v-if="formattedDate">
            <span class="flex-shrink-0 text-xs text-slate-400">·</span>
            <p class="flex-shrink-0 text-xs text-slate-500">
              {{ formattedDate }}
            </p>
          </template>
        </div>

        <!-- SOAP field badge -->
        <div class="mt-1.5 flex items-center gap-2">
          <span
            class="inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium"
            :class="soapFieldColorClass"
          >
            {{ fieldDisplayName }}
          </span>

          <!-- Relevance indicator -->
          <span
            class="text-xs text-slate-500"
            :title="`${similarityPercent}% relevant`"
          >
            {{ relevanceLabel }}
          </span>
        </div>
      </div>

      <!-- Arrow icon -->
      <div
        class="flex-shrink-0 text-slate-400 transition-transform group-hover:translate-x-1"
      >
        <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M9 5l7 7-7 7"
          />
        </svg>
      </div>
    </div>
  </button>
</template>
