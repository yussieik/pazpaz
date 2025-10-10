<script setup lang="ts">
import { computed } from 'vue'
import { formatDistanceToNow } from 'date-fns'

interface Props {
  amendmentCount: number
  amendedAt: string | null
  showHistory?: boolean
}

interface Emits {
  (e: 'view-history'): void
}

const props = withDefaults(defineProps<Props>(), {
  showHistory: true,
})

const emit = defineEmits<Emits>()

const shouldShow = computed(() => {
  return props.amendmentCount > 0 && props.amendedAt !== null
})

const amendmentText = computed(() => {
  if (!props.amendedAt) return ''
  const timeAgo = formatDistanceToNow(new Date(props.amendedAt), { addSuffix: true })
  const times = props.amendmentCount === 1 ? 'time' : 'times'
  return `Amended ${props.amendmentCount} ${times} (last: ${timeAgo})`
})
</script>

<template>
  <div v-if="shouldShow" class="rounded-lg border-l-4 border-amber-400 bg-amber-50 p-4">
    <div class="flex items-start justify-between gap-3">
      <div class="flex gap-3">
        <svg
          class="h-5 w-5 flex-shrink-0 text-amber-500"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
          />
        </svg>
        <div class="flex-1">
          <p class="text-sm font-medium text-amber-800">
            {{ amendmentText }}
          </p>
          <button
            v-if="showHistory"
            @click="emit('view-history')"
            class="mt-1 text-sm text-emerald-600 underline hover:text-emerald-700 focus:outline-none focus-visible:rounded focus-visible:ring-2 focus-visible:ring-emerald-500"
          >
            View Amendment History
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
