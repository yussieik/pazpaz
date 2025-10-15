<script setup lang="ts">
/**
 * FloatingActionButton Component
 *
 * A reusable floating action button (FAB) for primary actions.
 * Positioned fixed in bottom-right corner with emerald brand color.
 *
 * Design Pattern:
 * - Fixed positioning (bottom-6 right-6)
 * - 56px circular button (comfortable touch target)
 * - Emerald brand color with hover effects
 * - Smooth scale and shadow transitions
 * - Full accessibility (aria-label, keyboard, reduced motion)
 *
 * Props:
 * - label (required): Screen reader text and aria-label
 * - title (optional): Tooltip text (e.g., "New Appointment (N)")
 *
 * Emits:
 * - click: Emitted when button is clicked
 *
 * Accessibility:
 * - Native button element for keyboard support
 * - aria-label for screen readers
 * - title for visual tooltip
 * - focus-visible ring for keyboard users
 * - Respects prefers-reduced-motion
 */

interface Props {
  label: string
  title?: string
}

defineProps<Props>()

const emit = defineEmits<{
  click: []
}>()

function handleClick() {
  emit('click')
}
</script>

<template>
  <button
    @click="handleClick"
    :aria-label="label"
    :title="title || label"
    class="fab-button fixed right-6 bottom-6 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-600 text-white shadow-lg transition-all duration-200 hover:scale-105 hover:bg-emerald-700 hover:shadow-xl focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none"
  >
    <!-- Default Plus Icon (can be overridden with slot) -->
    <slot>
      <svg
        class="h-6 w-6"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M12 4v16m8-8H4"
        />
      </svg>
    </slot>
  </button>
</template>

<style scoped>
/* Reduced motion support */
@media (prefers-reduced-motion: reduce) {
  .fab-button {
    transition: none !important;
  }

  .fab-button:hover {
    transform: none !important;
  }
}
</style>
