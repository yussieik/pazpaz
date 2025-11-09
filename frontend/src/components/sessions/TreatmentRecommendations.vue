<script setup lang="ts">
/**
 * TreatmentRecommendations Component
 *
 * Displays AI-powered treatment recommendations based on SOAP note inputs.
 * Compact card design optimized for quick scanning and one-click insertion.
 *
 * Features:
 * - 1-2 recommendation cards with title, description, evidence badges
 * - "Use This" button to insert recommendation into Plan field
 * - Therapy type indicators (massage, physiotherapy, psychotherapy)
 * - Evidence badges showing workspace patterns, clinical guidelines, or hybrid
 * - Loading state with skeleton placeholders
 * - Error state with user-friendly messages
 * - Empty state with guidance
 *
 * Usage:
 *   <TreatmentRecommendations
 *     :recommendations="recommendations"
 *     :is-loading="isLoading"
 *     :error="error"
 *     @use-recommendation="handleUse"
 *   />
 *
 * Part of ADR 0002 - Treatment Recommendation Engine (Milestone 2)
 */

import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { TreatmentRecommendationItem } from '@/types/recommendations'
import { renderMarkdown } from '@/utils/markdown'

interface Props {
  recommendations: TreatmentRecommendationItem[]
  isLoading: boolean
  error: string | null
  therapyType?: string | null
  language?: string | null
  processingTimeMs?: number
}

interface Emits {
  (e: 'use-recommendation', recommendation: TreatmentRecommendationItem): void
  (e: 'close'): void
}

const props = withDefaults(defineProps<Props>(), {
  therapyType: null,
  language: null,
  processingTimeMs: 0,
})

const emit = defineEmits<Emits>()
const { t } = useI18n()

// Track which recommendation is being inserted
const insertingId = ref<string | null>(null)

/**
 * Handle "Use This" button click
 */
async function handleUseRecommendation(recommendation: TreatmentRecommendationItem) {
  insertingId.value = recommendation.recommendation_id

  // Brief delay for visual feedback
  await new Promise((resolve) => setTimeout(resolve, 300))

  emit('use-recommendation', recommendation)

  // Reset after insertion
  insertingId.value = null
}

/**
 * Get therapy type display name
 */
function getTherapyTypeLabel(type: string): string {
  const key = `treatmentRecommendations.therapyTypes.${type}`
  return t(key)
}

/**
 * Get evidence badge text
 */
function getEvidenceBadge(recommendation: TreatmentRecommendationItem): string {
  const { evidence_type, similar_cases_count } = recommendation

  if (evidence_type === 'workspace_patterns') {
    return t('treatmentRecommendations.evidence.workspacePatterns', {
      count: similar_cases_count,
    })
  } else if (evidence_type === 'clinical_guidelines') {
    return t('treatmentRecommendations.evidence.clinicalGuidelines')
  } else if (evidence_type === 'hybrid') {
    return t('treatmentRecommendations.evidence.hybrid', {
      count: similar_cases_count,
    })
  }

  return t('treatmentRecommendations.evidence.clinicalGuidelines')
}

/**
 * Get evidence badge color classes
 */
function getEvidenceBadgeClasses(evidenceType: string): string {
  const baseClasses =
    'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium'

  switch (evidenceType) {
    case 'workspace_patterns':
      return `${baseClasses} bg-amber-100 text-amber-800`
    case 'clinical_guidelines':
      return `${baseClasses} bg-indigo-100 text-indigo-800`
    case 'hybrid':
      return `${baseClasses} bg-teal-100 text-teal-800`
    default:
      return `${baseClasses} bg-gray-100 text-gray-800`
  }
}

/**
 * Formatted processing time
 */
const processingTimeFormatted = computed(() => {
  if (!props.processingTimeMs || props.processingTimeMs === 0) return null
  return t('treatmentRecommendations.processingTime', { time: props.processingTimeMs })
})

/**
 * Recommendation count text
 */
const recommendationCountText = computed(() => {
  const count = props.recommendations.length
  if (count === 0) return null
  return t('treatmentRecommendations.recommendationCount', { count })
})
</script>

<template>
  <!-- Container -->
  <div class="space-y-4">
    <!-- Header -->
    <div class="flex items-start justify-between">
      <div class="flex items-center gap-2.5">
        <!-- Lightbulb icon -->
        <svg
          class="h-6 w-6 flex-shrink-0 text-emerald-600"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
          />
        </svg>
        <div>
          <h3 class="text-xl font-bold text-slate-900">
            {{ t('treatmentRecommendations.title') }}
          </h3>
          <p v-if="recommendationCountText" class="mt-1 text-sm text-slate-600">
            {{ recommendationCountText }}
            <span v-if="processingTimeFormatted" class="text-slate-500">
              · {{ processingTimeFormatted }}
            </span>
          </p>
        </div>
      </div>
      <button
        @click="emit('close')"
        type="button"
        class="rounded-md p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
        :aria-label="t('treatmentRecommendations.closeButton')"
      >
        <svg
          class="h-5 w-5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M6 18L18 6M6 6l12 12"
          />
        </svg>
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="space-y-3">
      <div
        v-for="i in 2"
        :key="`skeleton-${i}`"
        class="animate-pulse rounded-lg border border-slate-200 bg-white p-4"
      >
        <div class="mb-3 flex items-center gap-2">
          <div class="h-5 w-20 rounded-full bg-slate-200"></div>
          <div class="h-5 w-32 rounded-full bg-slate-200"></div>
        </div>
        <div class="mb-2 h-6 w-3/4 rounded bg-slate-200"></div>
        <div class="mb-3 space-y-2">
          <div class="h-4 w-full rounded bg-slate-200"></div>
          <div class="h-4 w-full rounded bg-slate-200"></div>
          <div class="h-4 w-2/3 rounded bg-slate-200"></div>
        </div>
        <div class="h-9 w-24 rounded-md bg-slate-200"></div>
      </div>
    </div>

    <!-- Error State -->
    <div
      v-else-if="error"
      class="rounded-lg border border-red-200 bg-red-50 p-4"
      role="alert"
      aria-live="polite"
    >
      <div class="flex items-start gap-3">
        <svg
          class="h-5 w-5 flex-shrink-0 text-red-600"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <div class="flex-1">
          <p class="text-sm font-medium text-red-800">{{ error }}</p>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div
      v-else-if="recommendations.length === 0"
      class="rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 p-8 text-center"
    >
      <svg
        class="mx-auto h-12 w-12 text-slate-400"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        aria-hidden="true"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
        />
      </svg>
      <h4 class="mt-4 text-base font-semibold text-slate-900">
        {{ t('treatmentRecommendations.emptyState.title') }}
      </h4>
      <p class="mt-2 text-sm text-slate-600">
        {{ t('treatmentRecommendations.emptyState.description') }}
      </p>
    </div>

    <!-- Recommendations List -->
    <div v-else class="space-y-4">
      <div
        v-for="recommendation in recommendations"
        :key="recommendation.recommendation_id"
        :class="[
          'group relative overflow-hidden rounded-xl border border-slate-200 bg-gradient-to-br from-white to-slate-50/30 p-5 shadow-sm',
          'transition-all duration-200 ease-out',
          'hover:-translate-y-0.5 hover:border-emerald-300 hover:shadow-lg hover:shadow-emerald-100/50',
          'focus-within:ring-2 focus-within:ring-emerald-500/20 focus-within:ring-offset-2',
        ]"
      >
        <!-- Accent bar (appears on hover) -->
        <div
          class="absolute top-0 left-0 h-full w-1 bg-gradient-to-b from-emerald-500 to-emerald-600 opacity-0 transition-opacity duration-200 group-hover:opacity-100"
          aria-hidden="true"
        />

        <!-- Content with left padding for accent bar -->
        <div class="relative pl-0.5">
          <!-- Badges Row -->
          <div class="mb-4 flex flex-wrap items-center gap-2">
            <!-- Evidence badge with checkmark icon -->
            <span :class="getEvidenceBadgeClasses(recommendation.evidence_type)">
              <svg
                class="mr-1 inline h-3.5 w-3.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2.5"
                  d="M5 13l4 4L19 7"
                />
              </svg>
              {{ getEvidenceBadge(recommendation) }}
            </span>
            <!-- Therapy type badge (secondary style) -->
            <span class="inline-flex items-center gap-1 text-xs text-slate-600">
              <svg
                class="h-3.5 w-3.5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"
                />
              </svg>
              {{ getTherapyTypeLabel(recommendation.therapy_type) }}
            </span>
          </div>

          <!-- Title -->
          <h4 class="mb-3 text-base font-semibold text-slate-900">
            {{ recommendation.title }}
          </h4>

          <!-- Description with markdown rendering -->
          <div
            class="prose prose-clinical prose-sm mb-4 max-w-none text-sm leading-relaxed"
            v-html="renderMarkdown(recommendation.description)"
          />

          <!-- Action Button -->
          <button
            @click="handleUseRecommendation(recommendation)"
            :disabled="insertingId === recommendation.recommendation_id"
            type="button"
            :class="[
              'group/btn inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold',
              'transition-all duration-200 ease-out',
              'bg-emerald-600 text-white shadow-sm shadow-emerald-900/10',
              'hover:-translate-y-0.5 hover:bg-emerald-700 hover:shadow-md hover:shadow-emerald-900/20',
              'focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2',
              'disabled:translate-y-0 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-500 disabled:shadow-none',
            ]"
            :aria-label="`${t('treatmentRecommendations.useThisButton')} - ${recommendation.title}`"
          >
            <!-- Plus icon (shows when not loading) -->
            <svg
              v-if="insertingId !== recommendation.recommendation_id"
              class="h-4 w-4 transition-transform group-hover/btn:scale-110"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2.5"
                d="M12 4v16m8-8H4"
              />
            </svg>

            <!-- Loading spinner -->
            <svg v-else class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle
                class="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                stroke-width="4"
              />
              <path
                class="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>

            <span v-if="insertingId === recommendation.recommendation_id">
              {{ t('treatmentRecommendations.usingButton') }}
            </span>
            <span v-else>
              {{ t('treatmentRecommendations.useThisButton') }}
            </span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
