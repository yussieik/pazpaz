<script setup lang="ts">
/**
 * Mobile Action Toolbar
 *
 * Floating action toolbar for mobile appointment quick actions.
 * Appears at bottom of screen when an appointment is selected on mobile (≤640px).
 *
 * Features:
 * - Teleports to body for proper z-index layering
 * - Slide-up animation with backdrop
 * - Large touch targets (48px height)
 * - Complete, Delete, and Directions actions
 * - Accessibility: screen reader labels, reduced motion support
 *
 * Design:
 * - Backdrop: Semi-transparent black overlay
 * - Toolbar: White with shadow, fixed at bottom (80px from bottom)
 * - Buttons: Side-by-side with 12px gap
 *   - Directions: Icon-only, blue, map pin icon
 *   - Complete: 120px × 48px, green, checkmark icon
 *   - Delete: 120px × 48px, red, trash icon
 */

import { computed } from 'vue'

interface Props {
  visible: boolean
  appointmentId: string | null
  appointmentAddress: string | null | undefined
  appointmentLocationType: 'clinic' | 'home' | 'online' | null
  canComplete: boolean
}

interface Emits {
  (e: 'complete'): void
  (e: 'delete'): void
  (e: 'close'): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

// Show directions button only for physical locations with address
const showDirections = computed(() => {
  return props.appointmentAddress && props.appointmentLocationType !== 'online'
})

function handleDirections() {
  if (!props.appointmentAddress) return
  const url = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(props.appointmentAddress)}`
  window.open(url, '_blank', 'noopener,noreferrer')
}

function handleBackdropClick() {
  emit('close')
}

function handleComplete() {
  emit('complete')
}

function handleDelete() {
  emit('delete')
}
</script>

<template>
  <Teleport to="body">
    <!-- Backdrop - separate from transition, appears instantly -->
    <div
      v-if="visible"
      class="fixed inset-0 bg-black/20"
      style="z-index: 9999"
      @click="handleBackdropClick"
      aria-hidden="true"
    ></div>

    <!-- Floating Toolbar - with slide-up animation -->
    <Transition name="toolbar-slide">
      <div
        v-if="visible"
        class="fixed bottom-20 left-1/2 flex -translate-x-1/2 gap-3 rounded-lg bg-white px-4 py-3 shadow-2xl"
        style="z-index: 10000"
        role="toolbar"
        aria-label="Appointment quick actions"
      >
        <!-- Directions Button (icon-only) -->
        <button
          v-if="showDirections"
          type="button"
          class="flex h-12 w-12 items-center justify-center rounded-lg bg-blue-500 text-white shadow-sm transition-colors hover:bg-blue-600 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:outline-none active:bg-blue-700"
          @click="handleDirections"
          aria-label="Get directions in Google Maps"
        >
          <!-- Map Pin Icon -->
          <svg
            class="h-5 w-5 flex-shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
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
        </button>

        <!-- Complete Button -->
        <button
          v-if="canComplete"
          type="button"
          class="flex h-12 w-[120px] items-center justify-center gap-2 rounded-lg bg-emerald-500 text-base font-semibold text-white shadow-sm transition-colors hover:bg-emerald-600 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none active:bg-emerald-700"
          @click="handleComplete"
          aria-label="Mark appointment as attended"
        >
          <!-- Checkmark Icon -->
          <svg
            class="h-5 w-5 flex-shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M5 13l4 4L19 7"
            />
          </svg>
          <span>Complete</span>
        </button>

        <!-- Delete Button -->
        <button
          type="button"
          class="flex h-12 w-[120px] items-center justify-center gap-2 rounded-lg bg-red-500 text-base font-semibold text-white shadow-sm transition-colors hover:bg-red-600 focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2 focus-visible:outline-none active:bg-red-700"
          @click="handleDelete"
          aria-label="Delete appointment"
        >
          <!-- Trash Icon -->
          <svg
            class="h-5 w-5 flex-shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
            />
          </svg>
          <span>Delete</span>
        </button>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Toolbar slide-up animation - only toolbar slides, backdrop appears instantly */
.toolbar-slide-enter-active {
  transition:
    transform 250ms cubic-bezier(0.4, 0, 0.2, 1),
    opacity 200ms ease-in-out;
}

.toolbar-slide-leave-active {
  transition:
    transform 200ms cubic-bezier(0.4, 0, 0.2, 1),
    opacity 150ms ease-in-out;
}

.toolbar-slide-enter-from {
  transform: translate(-50%, calc(100% + 80px));
  opacity: 0;
}

.toolbar-slide-leave-to {
  transform: translate(-50%, calc(100% + 80px));
  opacity: 0;
}

/* Respect reduced motion preference */
@media (prefers-reduced-motion: reduce) {
  .toolbar-slide-enter-active,
  .toolbar-slide-leave-active {
    transition: none;
  }
}
</style>
