<script setup lang="ts">
/**
 * AgentChatInterface Component
 *
 * Main chat interface for AI clinical documentation assistant
 * Displays message history and input form for queries
 *
 * Features:
 * - Message history with auto-scroll
 * - Input form with validation
 * - Loading states
 * - Error handling
 * - Rate limiting feedback
 * - RTL support via i18n
 * - Client scoping for queries
 */

import { ref, computed, nextTick, watch } from 'vue'
import { useI18n } from '@/composables/useI18n'
import { useAIAgent } from '@/composables/useAIAgent'
import AgentMessageBubble from './AgentMessageBubble.vue'

interface Props {
  clientId?: string
}

const props = defineProps<Props>()
const { t } = useI18n()
const { messages, isLoading, error, sendQuery, clearMessages } = useAIAgent()

const queryInput = ref('')
const messagesContainer = ref<HTMLDivElement | null>(null)

// Validation
const isQueryValid = computed(() => {
  return queryInput.value.trim().length > 0 && queryInput.value.length <= 500
})

const canSubmit = computed(() => {
  return isQueryValid.value && !isLoading.value
})

// Auto-scroll to bottom when new messages arrive
watch(
  () => messages.value.length,
  async () => {
    await nextTick()
    scrollToBottom()
  }
)

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

async function handleSubmit() {
  if (!canSubmit.value) return

  const query = queryInput.value.trim()
  queryInput.value = ''

  try {
    await sendQuery({
      query,
      client_id: props.clientId,
      max_results: 5,
      min_similarity: 0.3,
    })
  } catch (err) {
    // Error is already handled in composable
    console.error('Failed to send query:', err)
  }
}

function handleClearHistory() {
  if (confirm(t('aiAgent.confirmClearHistory'))) {
    clearMessages()
  }
}
</script>

<template>
  <div class="flex h-full flex-col bg-slate-50">
    <!-- Header (minimal - just clear action) -->
    <div
      v-if="messages.length > 0"
      class="flex items-center justify-end border-b border-slate-200 bg-white px-4 py-2"
    >
      <!-- Clear history button with inline count -->
      <button
        type="button"
        class="flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm text-slate-600 transition-colors hover:bg-slate-100 focus:ring-2 focus:ring-emerald-500 focus:outline-none"
        @click="handleClearHistory"
      >
        <span class="text-xs text-slate-400">{{ Math.floor(messages.length / 2) }}</span>
        <span class="font-medium">{{ $t('aiAgent.clearHistory') }}</span>
      </button>
    </div>

    <!-- Messages container with subtle background pattern -->
    <div
      ref="messagesContainer"
      class="flex-1 space-y-6 overflow-y-auto px-4 py-6"
      style="
        background-image: radial-gradient(
          circle at 1px 1px,
          rgb(203 213 225 / 0.15) 1px,
          transparent 0
        );
        background-size: 24px 24px;
      "
    >
      <!-- Empty state (enhanced) -->
      <div v-if="messages.length === 0" class="flex h-full items-center justify-center">
        <div class="max-w-lg rounded-2xl bg-white p-8 shadow-sm">
          <!-- Animated icon -->
          <div class="mb-6 flex justify-center">
            <div
              class="flex h-16 w-16 animate-pulse items-center justify-center rounded-full bg-gradient-to-br from-emerald-100 to-cyan-100"
            >
              <svg
                class="h-8 w-8 text-emerald-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
                />
              </svg>
            </div>
          </div>

          <h3 class="mb-2 text-center text-xl font-semibold text-slate-900">
            {{ $t('aiAgent.emptyState.title') }}
          </h3>
          <p class="mb-6 text-center text-slate-600">
            {{ $t('aiAgent.emptyState.description') }}
          </p>

          <!-- Example queries -->
          <div class="space-y-3">
            <p class="text-sm font-medium text-slate-700">
              {{ $t('aiAgent.emptyState.examplesTitle') }}
            </p>
            <div class="space-y-2">
              <div
                class="w-full rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-start text-sm text-slate-700"
              >
                <span class="mr-2 text-slate-400">→</span>
                {{ $t('aiAgent.emptyState.example1') }}
              </div>
              <div
                class="w-full rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-start text-sm text-slate-700"
              >
                <span class="mr-2 text-slate-400">→</span>
                {{ $t('aiAgent.emptyState.example2') }}
              </div>
              <div
                class="w-full rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 text-start text-sm text-slate-700"
              >
                <span class="mr-2 text-slate-400">→</span>
                {{ $t('aiAgent.emptyState.example3') }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Messages -->
      <AgentMessageBubble
        v-for="message in messages"
        :key="message.id"
        :message="message"
      />

      <!-- Loading indicator (enhanced) -->
      <div v-if="isLoading" class="flex justify-start">
        <div
          class="flex items-center gap-3 rounded-2xl rounded-bl-sm border border-slate-100 bg-white px-5 py-4 shadow-sm"
        >
          <!-- Three-dot animation -->
          <div class="flex gap-1.5">
            <span
              class="h-2 w-2 animate-bounce rounded-full bg-emerald-500"
              style="animation-delay: 0s"
            />
            <span
              class="h-2 w-2 animate-bounce rounded-full bg-emerald-500"
              style="animation-delay: 0.2s"
            />
            <span
              class="h-2 w-2 animate-bounce rounded-full bg-emerald-500"
              style="animation-delay: 0.4s"
            />
          </div>
          <span class="text-sm text-slate-600">{{ $t('aiAgent.thinking') }}</span>
        </div>
      </div>
    </div>

    <!-- Input form (enhanced with better visual separation) -->
    <div class="border-t border-slate-200 bg-white p-4 shadow-lg">
      <!-- Error message -->
      <div
        v-if="error"
        class="mb-3 flex items-start gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-800"
      >
        <svg
          class="mt-0.5 h-4 w-4 flex-shrink-0"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <span>{{ error }}</span>
      </div>

      <form class="flex gap-3" @submit.prevent="handleSubmit">
        <div class="flex-1">
          <div class="relative">
            <textarea
              v-model="queryInput"
              :placeholder="$t('aiAgent.inputPlaceholder')"
              :disabled="isLoading"
              rows="2"
              maxlength="500"
              class="w-full resize-none rounded-xl border-2 border-slate-200 px-4 py-3 text-sm transition-all focus:border-emerald-400 focus:ring-4 focus:ring-emerald-100 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-500"
              @keydown.enter.exact.prevent="handleSubmit"
            />
            <!-- Character count -->
            <div
              class="absolute bottom-2 right-3 text-xs"
              :class="
                queryInput.length > 450 ? 'text-amber-600 font-medium' : 'text-slate-400'
              "
            >
              {{ queryInput.length }}/500
            </div>
          </div>
        </div>

        <!-- Send button with icon -->
        <button
          type="submit"
          :disabled="!canSubmit"
          class="flex h-auto items-center gap-2 self-start rounded-xl bg-emerald-500 px-5 py-3 font-medium text-white shadow-sm transition-all hover:bg-emerald-600 hover:shadow-md focus:ring-4 focus:ring-emerald-200 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none"
        >
          <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
            />
          </svg>
          <span>{{ $t('aiAgent.send') }}</span>
        </button>
      </form>

      <!-- Keyboard shortcut hint -->
      <p class="mt-2 text-center text-xs text-slate-500">
        Press Enter to send · Shift+Enter for new line
      </p>
    </div>
  </div>
</template>
