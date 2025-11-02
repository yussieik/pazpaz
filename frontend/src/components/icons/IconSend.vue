<script setup lang="ts">
interface Props {
  /**
   * CSS class for the SVG element
   * @default "h-5 w-5"
   */
  class?: string
}

withDefaults(defineProps<Props>(), {
  class: 'h-5 w-5',
})
</script>

<template>
  <svg :class="$props.class" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path
      stroke-linecap="round"
      stroke-linejoin="round"
      stroke-width="2"
      d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
    />
  </svg>
</template>
