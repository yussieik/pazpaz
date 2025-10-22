<template>
  <button
    :type="type"
    :disabled="disabled || loading"
    :class="buttonClasses"
    @click="handleClick"
  >
    <!-- Loading Spinner -->
    <span v-if="loading" class="mr-2 flex-shrink-0">
      <svg
        class="h-5 w-5 animate-spin"
        fill="none"
        viewBox="0 0 24 24"
        aria-hidden="true"
      >
        <circle
          class="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          stroke-width="4"
        ></circle>
        <path
          class="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        ></path>
      </svg>
    </span>

    <!-- Icon (optional, left side) -->
    <span v-if="$slots.icon && !loading" class="mr-2 flex-shrink-0">
      <slot name="icon" />
    </span>

    <!-- Button Text -->
    <span>
      <slot />
    </span>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'

/**
 * BaseButton Component
 *
 * Reusable button component with micro-interactions and accessibility.
 *
 * Features:
 * - Smooth hover/focus/active state transitions
 * - Scale micro-interactions (hover: scale-102, active: scale-98)
 * - Loading state with spinner
 * - Disabled state with cursor and opacity changes
 * - Multiple variants (primary, secondary, danger, ghost)
 * - Multiple sizes (sm, md, lg)
 * - Full width option
 * - Icon slot support
 * - Respects prefers-reduced-motion
 *
 * Usage:
 *   <BaseButton variant="primary" @click="handleClick">
 *     Submit
 *   </BaseButton>
 *
 *   <BaseButton variant="secondary" loading>
 *     Loading...
 *   </BaseButton>
 *
 *   <BaseButton variant="danger" size="lg" full-width>
 *     <template #icon>
 *       <TrashIcon />
 *     </template>
 *     Delete
 *   </BaseButton>
 */

interface Props {
  type?: 'button' | 'submit' | 'reset'
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  disabled?: boolean
  loading?: boolean
  fullWidth?: boolean
}

interface Emits {
  (e: 'click', event: MouseEvent): void
}

const props = withDefaults(defineProps<Props>(), {
  type: 'button',
  variant: 'primary',
  size: 'md',
  disabled: false,
  loading: false,
  fullWidth: false,
})

const emit = defineEmits<Emits>()

/**
 * Compute button classes based on props
 */
const buttonClasses = computed(() => {
  const classes = [
    // Base styles
    'inline-flex items-center justify-center',
    'rounded-lg font-semibold',
    'transition-all duration-200 ease-in-out',
    'focus:outline-none focus:ring-2 focus:ring-offset-2',

    // Micro-interactions (hover and active states)
    // Only apply scale transforms when not disabled
    !props.disabled && !props.loading && 'transform hover:scale-102 active:scale-98',

    // Disabled state
    (props.disabled || props.loading) && 'cursor-not-allowed opacity-50',
  ]

  // Variant-specific styles
  switch (props.variant) {
    case 'primary':
      classes.push(
        'bg-emerald-600 text-white',
        'hover:bg-emerald-700 hover:shadow-lg',
        'focus:ring-emerald-500',
        'disabled:bg-slate-300 disabled:hover:bg-slate-300 disabled:hover:shadow-none'
      )
      break
    case 'secondary':
      classes.push(
        'bg-slate-200 text-slate-800',
        'hover:bg-slate-300 hover:shadow-md',
        'focus:ring-slate-500',
        'disabled:bg-slate-100 disabled:hover:bg-slate-100 disabled:hover:shadow-none'
      )
      break
    case 'danger':
      classes.push(
        'bg-red-600 text-white',
        'hover:bg-red-700 hover:shadow-lg',
        'focus:ring-red-500',
        'disabled:bg-red-300 disabled:hover:bg-red-300 disabled:hover:shadow-none'
      )
      break
    case 'ghost':
      classes.push(
        'bg-transparent text-slate-700 border border-slate-300',
        'hover:bg-slate-50 hover:border-slate-400',
        'focus:ring-slate-400',
        'disabled:bg-transparent disabled:hover:bg-transparent disabled:hover:border-slate-300'
      )
      break
  }

  // Size-specific styles
  switch (props.size) {
    case 'sm':
      classes.push('px-3 py-1.5 text-sm')
      break
    case 'md':
      classes.push('px-4 py-2.5 text-base')
      break
    case 'lg':
      classes.push('px-6 py-3 text-lg')
      break
  }

  // Full width
  if (props.fullWidth) {
    classes.push('w-full')
  }

  return classes.filter(Boolean).join(' ')
})

/**
 * Handle click event
 */
function handleClick(event: MouseEvent) {
  if (!props.disabled && !props.loading) {
    emit('click', event)
  }
}
</script>

<style scoped>
/* Respect user's motion preferences */
@media (prefers-reduced-motion: reduce) {
  button {
    transition-duration: 1ms !important;
    transform: none !important;
  }

  button:hover {
    transform: none !important;
  }

  button:active {
    transform: none !important;
  }
}
</style>
