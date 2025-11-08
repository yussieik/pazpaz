<script setup lang="ts">
/**
 * AgentMessageBubble Component
 *
 * Displays a single message bubble in the AI chat interface
 * Supports user and assistant messages with different styling
 *
 * Features:
 * - User vs Assistant styling
 * - Citation cards for assistant responses
 * - Timestamp display
 * - RTL support via i18n
 * - Error state styling
 */

import { computed, ref } from 'vue'
import { useI18n } from '@/composables/useI18n'
import type { AgentMessage } from '@/composables/useAIAgent'
import AgentCitationCard from './AgentCitationCard.vue'
import { renderMarkdown } from '@/utils/markdown'

interface Props {
  message: AgentMessage
}

const props = defineProps<Props>()
const { isRTL } = useI18n()

// Citations collapse state
const citationsExpanded = ref(false)

// Format timestamp
const formattedTime = computed(() => {
  return props.message.timestamp.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  })
})

// Check if message is an error
const isError = computed(() => {
  return props.message.role === 'assistant' && props.message.id.startsWith('error-')
})

// Alignment classes based on role and RTL
const alignmentClasses = computed(() => {
  if (props.message.role === 'user') {
    return isRTL.value ? 'justify-start' : 'justify-end'
  }
  return isRTL.value ? 'justify-end' : 'justify-start'
})

// Bubble classes based on role and error state
const bubbleClasses = computed(() => {
  if (isError.value) {
    return 'bg-red-50 border-red-200 text-red-800'
  }
  if (props.message.role === 'user') {
    return 'bg-emerald-500 text-white'
  }
  return 'bg-white text-slate-900'
})

// Rendered content for assistant messages (with markdown)
const renderedContent = computed(() => {
  if (props.message.role === 'assistant' && !isError.value) {
    return renderMarkdown(props.message.content)
  }
  return props.message.content
})

// Container width classes
const containerWidthClasses = computed(() => {
  if (props.message.role === 'user') {
    return 'max-w-[85%] sm:max-w-[75%] lg:max-w-[65%]'
  }
  // Assistant messages can be wider for detailed clinical info
  return 'max-w-full'
})

// Bubble padding classes
const bubblePaddingClasses = computed(() => {
  if (props.message.role === 'user') {
    return 'px-4 py-3'
  }
  // More padding for assistant messages with formatted content
  return 'px-5 py-4'
})
</script>

<template>
  <div :class="['flex w-full', alignmentClasses]">
    <div :class="['space-y-3', containerWidthClasses]">
      <!-- Message bubble -->
      <div
        :class="[
          'rounded-2xl shadow-sm transition-all duration-200 border',
          bubbleClasses,
          bubblePaddingClasses,
          message.role === 'user' ? 'rounded-br-sm border-transparent' : 'rounded-bl-sm border-slate-200',
        ]"
      >
        <!-- User messages: simple text -->
        <p
          v-if="message.role === 'user'"
          class="text-sm leading-relaxed whitespace-pre-wrap"
        >
          {{ message.content }}
        </p>

        <!-- Assistant messages: rendered markdown with clinical styling -->
        <div
          v-else-if="!isError"
          class="prose prose-clinical prose-sm max-w-none"
          v-html="renderedContent"
        />

        <!-- Error messages: plain text with error styling -->
        <p v-else class="text-sm leading-relaxed">
          {{ message.content }}
        </p>
      </div>

      <!-- Timestamp and metadata -->
      <div
        :class="[
          'flex items-center gap-2 px-2 text-xs text-slate-500',
          message.role === 'user' ? 'justify-end' : 'justify-start',
        ]"
      >
        <span>{{ formattedTime }}</span>
        <span
          v-if="message.processing_time_ms && message.role === 'assistant'"
          class="text-slate-400"
        >
          · {{ Math.round(message.processing_time_ms) }}ms
        </span>
      </div>

      <!-- Citations section - collapsible -->
      <div
        v-if="message.role === 'assistant' && message.citations?.length"
        class="space-y-2"
      >
        <!-- Section header - clickable to expand/collapse -->
        <button
          type="button"
          class="flex w-full items-center gap-2 px-2 transition-colors hover:bg-slate-50 focus:outline-none"
          @click="citationsExpanded = !citationsExpanded"
        >
          <!-- Chevron icon -->
          <svg
            class="h-3.5 w-3.5 flex-shrink-0 text-slate-400 transition-transform"
            :class="{ 'rotate-90': citationsExpanded }"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M9 5l7 7-7 7"
            />
          </svg>

          <div class="h-px flex-1 bg-slate-200" />
          <span class="text-xs font-medium text-slate-600">
            {{ $t('aiAgent.citations.title') }}
            <span class="ml-1 text-slate-400">({{ message.citations.length }})</span>
          </span>
          <div class="h-px flex-1 bg-slate-200" />
        </button>

        <!-- Citation cards grid (2 columns on larger screens) - collapsible -->
        <div
          v-show="citationsExpanded"
          class="grid gap-2 sm:grid-cols-2"
        >
          <AgentCitationCard
            v-for="citation in message.citations"
            :key="citation.type === 'session' ? citation.session_id : citation.client_id"
            :citation="citation"
          />
        </div>
      </div>
    </div>
  </div>
</template>
