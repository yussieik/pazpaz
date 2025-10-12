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
      d="M15 19l-7-7 7-7"
    />
  </svg>
</template>
