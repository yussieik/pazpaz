<script setup lang="ts">
import { watch } from 'vue'

interface Props {
  visible: boolean
  message: string
  clientName?: string
  datetime?: string
  actions?: Array<{ label: string; handler: () => void }>
}

interface Emits {
  (e: 'update:visible', value: boolean): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

function close() {
  emit('update:visible', false)
}

// Auto-dismiss after 8 seconds
watch(
  () => props.visible,
  (isVisible) => {
    if (isVisible) {
      setTimeout(() => {
        close()
      }, 8000)
    }
  }
)
</script>

<template>
  <Transition name="toast-slide">
    <div
      v-if="visible"
      class="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-gray-900 px-4 py-3 text-white shadow-2xl"
      role="status"
      aria-live="polite"
    >
      <div class="flex items-center gap-3">
        <!-- Success Icon -->
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
            d="M5 13l4 4L19 7"
          />
        </svg>

        <!-- Message -->
        <div class="flex-1">
          <p class="text-sm font-medium">{{ message }}</p>
          <p v-if="clientName && datetime" class="mt-0.5 text-xs text-gray-300">
            {{ clientName }} • {{ datetime }}
          </p>
        </div>

        <!-- Actions -->
        <div class="flex items-center gap-2">
          <button
            v-for="action in actions"
            :key="action.label"
            @click="action.handler"
            class="rounded-md bg-white/10 px-3 py-1.5 text-sm font-medium transition-colors hover:bg-white/20"
          >
            {{ action.label }}
          </button>
          <button
            @click="close"
            class="rounded-lg p-1 transition-colors hover:bg-white/10"
            aria-label="Dismiss"
          >
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.toast-slide-enter-active,
.toast-slide-leave-active {
  transition: all 0.3s ease-out;
}

.toast-slide-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(1rem);
}

.toast-slide-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(1rem);
}
</style>
