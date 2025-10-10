<script setup lang="ts">
/**
 * LoadingSpinner Component
 *
 * Reusable loading spinner with customizable size and color
 * Consolidates 16+ duplicate spinner implementations across the codebase
 *
 * Usage:
 *   <LoadingSpinner size="md" color="emerald" />
 *   <LoadingSpinner size="sm" color="slate" />
 */

interface Props {
  size?: 'sm' | 'md' | 'lg'
  color?: 'emerald' | 'slate' | 'blue' | 'red'
}

const props = withDefaults(defineProps<Props>(), {
  size: 'md',
  color: 'slate',
})

const sizeClasses = {
  sm: 'h-4 w-4',
  md: 'h-5 w-5',
  lg: 'h-8 w-8',
}

const colorClasses = {
  emerald: 'text-emerald-600',
  slate: 'text-slate-400',
  blue: 'text-blue-600',
  red: 'text-red-600',
}
</script>

<template>
  <svg
    :class="[sizeClasses[size], colorClasses[color], 'animate-spin']"
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    viewBox="0 0 24 24"
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
</template>
