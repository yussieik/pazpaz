<script setup lang="ts">
interface Props {
  /**
   * CSS class for the SVG element
   * @default "h-4 w-4"
   */
  class?: string
}

withDefaults(defineProps<Props>(), {
  class: 'h-4 w-4',
})
</script>

<template>
  <svg
    :class="$props.class"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    viewBox="0 0 24 24"
    xmlns="http://www.w3.org/2000/svg"
  >
    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
  </svg>
</template>
