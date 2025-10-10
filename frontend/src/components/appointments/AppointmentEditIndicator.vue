<script setup lang="ts">
import { computed } from 'vue'
import { formatDistanceToNow, format } from 'date-fns'

interface Props {
  editCount: number
  editedAt: string | null
}

const props = defineProps<Props>()

const shouldShow = computed(() => {
  return props.editCount > 0 && props.editedAt !== null
})

const editText = computed(() => {
  if (!props.editedAt) return ''
  const timeAgo = formatDistanceToNow(new Date(props.editedAt), { addSuffix: true })
  const times = props.editCount === 1 ? 'time' : 'times'
  return `Edited ${props.editCount} ${times} (last: ${timeAgo})`
})

const absoluteTime = computed(() => {
  if (!props.editedAt) return ''
  return format(new Date(props.editedAt), "MMM d, yyyy 'at' h:mm a")
})
</script>

<template>
  <div v-if="shouldShow" class="flex items-center gap-2 text-sm text-slate-500">
    <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
      />
    </svg>
    <span :title="absoluteTime">{{ editText }}</span>
  </div>
</template>
