<script setup lang="ts">
/**
 * AutosaveBanner Component
 *
 * Contextual banner for autosave exceptions (offline mode, sync errors)
 * Only shows when user needs to know or take action (99% invisible)
 *
 * Usage:
 *   <AutosaveBanner
 *     :visible="showBanner"
 *     :severity="bannerSeverity"
 *     :message="bannerMessage"
 *     :description="bannerDescription"
 *     :actions="bannerActions"
 *   />
 */
import { computed } from 'vue'
import IconWarning from '@/components/icons/IconWarning.vue'
import IconXCircle from '@/components/icons/IconXCircle.vue'

interface Action {
  label: string
  onClick: () => void
}

interface Props {
  visible: boolean
  severity: 'warning' | 'error'
  message: string
  description?: string
  actions?: Action[]
}

const props = withDefaults(defineProps<Props>(), {
  actions: () => [],
})

const icon = computed(() => (props.severity === 'error' ? IconXCircle : IconWarning))

const bannerClasses = computed(() => [
  'sticky top-0 z-10 border-b px-6 py-3',
  props.severity === 'warning'
    ? 'bg-amber-50 border-amber-200 text-amber-800'
    : 'bg-red-50 border-red-200 text-red-800',
])

const iconColor = computed(() =>
  props.severity === 'warning' ? 'text-amber-600' : 'text-red-600'
)
</script>

<template>
  <Transition name="slide-down">
    <div
      v-if="visible"
      :class="bannerClasses"
      role="alert"
      :aria-live="severity === 'error' ? 'assertive' : 'polite'"
    >
      <div class="flex items-start gap-3">
        <!-- Icon -->
        <component :is="icon" :class="iconColor" class="mt-0.5 flex-shrink-0" />

        <!-- Content -->
        <div class="min-w-0 flex-1">
          <p class="text-sm font-medium">{{ message }}</p>
          <p v-if="description" class="mt-1 text-sm opacity-90">
            {{ description }}
          </p>
        </div>

        <!-- Actions -->
        <div v-if="actions.length" class="flex flex-shrink-0 gap-2">
          <button
            v-for="action in actions"
            :key="action.label"
            @click="action.onClick"
            class="text-sm font-medium hover:underline focus:underline focus:outline-none"
          >
            {{ action.label }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.slide-down-enter-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.slide-down-leave-active {
  transition: all 0.2s ease-in;
}

.slide-down-enter-from {
  opacity: 0;
  transform: translateY(-100%);
}

.slide-down-leave-to {
  opacity: 0;
  transform: translateY(-100%);
}

@media (prefers-reduced-motion: reduce) {
  .slide-down-enter-active,
  .slide-down-leave-active {
    transition: none;
  }

  .slide-down-enter-from,
  .slide-down-leave-to {
    transform: none;
  }
}
</style>
