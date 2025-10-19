<script setup lang="ts">
/**
 * AttachmentBadge Component
 *
 * Displays a paperclip icon badge showing attachment count on session cards.
 *
 * Features:
 * - Shows file count with paperclip icon
 * - Tooltip with file type breakdown
 * - Clickable to scroll to attachments section
 * - Fully keyboard accessible
 * - Mobile-optimized touch target (min 44px)
 *
 * Usage:
 *   <AttachmentBadge :count="3" :file-types="{ images: 2, pdfs: 1 }" @click="scrollToAttachments" />
 */

import { computed } from 'vue'

interface Props {
  count: number
  fileTypes?: { images: number; pdfs: number }
  size?: 'sm' | 'md'
}

interface Emits {
  (e: 'click'): void
}

const props = withDefaults(defineProps<Props>(), {
  size: 'md',
  fileTypes: undefined,
})

const emit = defineEmits<Emits>()

// Determine which icon to show based on file types
const badgeIcon = computed(() => {
  if (!props.fileTypes) return 'paperclip' // Default

  const { images, pdfs } = props.fileTypes

  if (images > 0 && pdfs === 0) return 'camera' // Images only
  if (pdfs > 0 && images === 0) return 'document' // PDFs only
  return 'paperclip' // Mixed types
})

// Generate tooltip text with file type breakdown
const tooltipText = computed(() => {
  if (!props.fileTypes || (!props.fileTypes.images && !props.fileTypes.pdfs)) {
    return `${props.count} file${props.count !== 1 ? 's' : ''}`
  }

  const parts: string[] = []
  if (props.fileTypes.images > 0) {
    parts.push(`${props.fileTypes.images} image${props.fileTypes.images !== 1 ? 's' : ''}`)
  }
  if (props.fileTypes.pdfs > 0) {
    parts.push(`${props.fileTypes.pdfs} PDF${props.fileTypes.pdfs !== 1 ? 's' : ''}`)
  }

  return parts.join(', ')
})

// Accessibility label
const ariaLabel = computed(() => {
  return `${props.count} attachment${props.count !== 1 ? 's' : ''}. Click to view attachments.`
})

// Size classes
const sizeClasses = computed(() => {
  if (props.size === 'sm') {
    return {
      container: 'min-h-[36px] min-w-[36px] px-2 py-1',
      icon: 'h-3 w-3',
      text: 'text-xs',
    }
  }
  return {
    container: 'min-h-[44px] min-w-[44px] px-2.5 py-1.5',
    icon: 'h-4 w-4',
    text: 'text-xs',
  }
})

function handleClick() {
  emit('click')
}

function handleKeyPress(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    emit('click')
  }
}
</script>

<template>
  <button
    v-if="count > 0"
    type="button"
    :class="[
      'group inline-flex items-center gap-1.5 rounded-lg bg-slate-100 font-medium text-slate-500 transition-all hover:bg-slate-200 hover:text-slate-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 focus:outline-none',
      sizeClasses.container,
      sizeClasses.text,
    ]"
    :aria-label="ariaLabel"
    :title="tooltipText"
    @click="handleClick"
    @keydown="handleKeyPress"
  >
    <!-- Camera Icon (Images Only) -->
    <svg
      v-if="badgeIcon === 'camera'"
      :class="['flex-shrink-0', sizeClasses.icon]"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      aria-hidden="true"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
      />
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"
      />
    </svg>

    <!-- Document Icon (PDFs Only) -->
    <svg
      v-else-if="badgeIcon === 'document'"
      :class="['flex-shrink-0', sizeClasses.icon]"
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

    <!-- Paperclip Icon (Mixed or Default) -->
    <svg
      v-else
      :class="['flex-shrink-0', sizeClasses.icon]"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      aria-hidden="true"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"
      />
    </svg>

    <!-- Count Badge -->
    <span class="font-semibold">{{ count }}</span>

    <!-- Tooltip on hover (desktop only) -->
    <span
      class="pointer-events-none absolute -top-8 left-1/2 z-20 hidden -translate-x-1/2 whitespace-nowrap rounded bg-slate-900 px-2 py-1 text-xs text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100 sm:block"
      aria-hidden="true"
    >
      {{ tooltipText }}
      <!-- Tooltip arrow -->
      <svg
        class="absolute top-full left-1/2 h-2 w-4 -translate-x-1/2 text-slate-900"
        viewBox="0 0 16 8"
      >
        <path fill="currentColor" d="M8 8L0 0h16z" />
      </svg>
    </span>
  </button>
</template>

<style scoped>
/* Make tooltip positioning context relative */
button {
  position: relative;
}

/* Smooth transitions */
button {
  transition:
    background-color 0.15s ease,
    color 0.15s ease,
    transform 0.1s ease;
}

/* Active state feedback */
button:active {
  transform: scale(0.95);
}
</style>
