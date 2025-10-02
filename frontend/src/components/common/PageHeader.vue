<script setup lang="ts">
/**
 * PageHeader Component
 *
 * Standardized header for list views (Calendar, Clients, Settings)
 * with consistent spacing, typography, and responsive behavior.
 *
 * Design Pattern:
 * - Title and metadata stacked vertically for better scannability
 * - Actions slot for buttons (right-aligned on desktop, full-width on mobile)
 * - Optional search/filter slot below header
 * - Responsive: vertical stack on mobile, side-by-side on desktop
 *
 * Typography:
 * - Title: text-2xl font-semibold tracking-tight text-slate-900
 * - Metadata: text-sm text-slate-600 with mt-1.5 spacing
 *
 * Accessibility:
 * - Semantic <header> tag
 * - aria-live="polite" on metadata for dynamic updates
 * - Proper heading hierarchy (h1)
 */

interface Props {
  title: string
  metadata?: string
  loading?: boolean
}

defineProps<Props>()
</script>

<template>
  <header class="mb-6">
    <!-- Title Row with Actions -->
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div class="flex-1">
        <h1 class="text-2xl font-semibold tracking-tight text-slate-900">
          {{ title }}
        </h1>
        <p
          v-if="metadata && !loading"
          class="mt-1.5 text-sm text-slate-600"
          aria-live="polite"
          aria-atomic="true"
        >
          {{ metadata }}
        </p>
      </div>

      <!-- Actions Slot (right-aligned on desktop, full-width on mobile) -->
      <div v-if="$slots.actions" class="w-full flex-shrink-0 sm:w-auto">
        <slot name="actions" />
      </div>
    </div>

    <!-- Optional Search/Filter Row -->
    <div v-if="$slots.search" class="mt-4">
      <slot name="search" />
    </div>
  </header>
</template>
