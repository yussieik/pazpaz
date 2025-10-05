<template>
  <Transition
    enter-active-class="transition-all duration-300 ease-out"
    leave-active-class="transition-all duration-200 ease-in"
    enter-from-class="translate-y-2 opacity-0"
    enter-to-class="translate-y-0 opacity-100"
    leave-from-class="translate-y-0 opacity-100"
    leave-to-class="translate-y-2 opacity-0"
  >
    <div
      v-if="show"
      class="fixed bottom-6 left-1/2 z-50 -translate-x-1/2"
      role="status"
      aria-live="polite"
    >
      <div
        class="relative flex items-center gap-4 rounded-lg bg-slate-900 px-4 py-3 shadow-2xl ring-1 ring-white/10"
      >
        <div class="flex items-center gap-3">
          <svg
            class="h-5 w-5 text-emerald-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <span class="text-sm font-medium text-white">
            {{ message }}
          </span>
        </div>

        <button
          @click="emit('undo')"
          class="rounded-md bg-white px-3 py-1.5 text-sm font-medium text-slate-900 transition-colors hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
        >
          Undo
        </button>

        <!-- Progress bar -->
        <div
          class="absolute bottom-0 left-0 h-0.5 w-full overflow-hidden rounded-b-lg bg-emerald-400/30"
        >
          <div
            class="undo-toast-progress h-full bg-emerald-400 transition-all ease-linear"
            :style="{ width: progress + '%', transitionDuration: progressDuration }"
          />
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    show: boolean
    message: string
    duration?: number
  }>(),
  {
    duration: 8000,
  }
)

const emit = defineEmits<{
  undo: []
  close: []
}>()

const progress = ref(100)
const progressDuration = ref('0ms')

watch(
  () => props.show,
  (isShown) => {
    if (isShown) {
      // Reset progress immediately
      progress.value = 100
      progressDuration.value = '0ms'

      // Start countdown animation on next frame
      requestAnimationFrame(() => {
        progressDuration.value = `${props.duration}ms`
        progress.value = 0
      })

      // Auto-close after duration
      setTimeout(() => {
        if (props.show) {
          emit('close')
        }
      }, props.duration)
    } else {
      // Reset when hidden
      progress.value = 100
      progressDuration.value = '0ms'
    }
  }
)
</script>
