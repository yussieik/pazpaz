<script setup lang="ts">
/**
 * Directions Button
 *
 * Simple link to Google Maps directions for a given address.
 * Opens in new tab, works on mobile (opens Google Maps app if installed).
 *
 * Features:
 * - External link (no API, no data sharing until click)
 * - Responsive: Icon + text on desktop, icon-only on mobile
 * - Accessible: ARIA labels, keyboard navigation
 *
 * Usage:
 * <DirectionsButton
 *   :address="client.address"
 *   size="sm"
 *   :show-label="true"
 * />
 */

import { computed } from 'vue'

interface Props {
  address: string | null | undefined
  size?: 'sm' | 'md'
  showLabel?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  size: 'sm',
  showLabel: true,
})

const directionsUrl = computed(() => {
  if (!props.address) return '#'

  const params = new URLSearchParams({
    api: '1',
    destination: props.address,
  })

  return `https://www.google.com/maps/dir/?${params.toString()}`
})

const ariaLabel = computed(() => {
  return `Get directions to ${props.address} in Google Maps`
})
</script>

<template>
  <a
    v-if="address"
    :href="directionsUrl"
    target="_blank"
    rel="noopener noreferrer"
    :aria-label="ariaLabel"
    :title="`Get directions in Google Maps (G)`"
    :class="[
      'inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-blue-600 transition-colors hover:text-blue-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2',
      size === 'sm' ? 'text-sm' : 'text-base',
    ]"
  >
    <!-- Map Pin Icon -->
    <svg
      :class="['flex-shrink-0', size === 'sm' ? 'h-4 w-4' : 'h-5 w-5']"
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
      />
      <path
        stroke-linecap="round"
        stroke-linejoin="round"
        stroke-width="2"
        d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
      />
    </svg>

    <!-- Label (hidden on mobile if showLabel is configured) -->
    <span v-if="showLabel" :class="['sm:inline', size === 'sm' ? 'hidden' : '']">
      Directions
    </span>
  </a>
</template>

<style scoped>
/* Respect reduced motion preference */
@media (prefers-reduced-motion: reduce) {
  a {
    transition: none !important;
  }
}
</style>
