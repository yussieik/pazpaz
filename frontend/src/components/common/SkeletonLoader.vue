<script setup lang="ts">
/**
 * SkeletonLoader Component
 *
 * Reusable skeleton loading placeholder that matches the shape of actual content.
 *
 * Features:
 * - Multiple preset types (card, list, text, attachment, timeline)
 * - Customizable width, height, and count
 * - Smooth pulse animation
 * - No layout shift (dimensions match real content)
 *
 * Usage:
 *   <SkeletonLoader type="card" :count="3" />
 *   <SkeletonLoader type="attachment" />
 *   <SkeletonLoader type="text" width="w-3/4" height="h-4" />
 */

interface Props {
  type?: 'card' | 'list' | 'text' | 'attachment' | 'timeline'
  width?: string
  height?: string
  count?: number
  rounded?: 'sm' | 'md' | 'lg' | 'full'
}

const props = withDefaults(defineProps<Props>(), {
  type: 'text',
  width: 'w-full',
  height: 'h-4',
  count: 1,
  rounded: 'md',
})

const roundedClass = {
  sm: 'rounded-sm',
  md: 'rounded-md',
  lg: 'rounded-lg',
  full: 'rounded-full',
}[props.rounded]
</script>

<template>
  <div class="skeleton-loader" aria-busy="true" aria-live="polite">
    <!-- Text Skeleton -->
    <template v-if="type === 'text'">
      <div
        v-for="i in count"
        :key="i"
        :class="[
          'animate-pulse bg-slate-200',
          width,
          height,
          roundedClass,
          i < count ? 'mb-2' : '',
        ]"
      ></div>
    </template>

    <!-- Card Skeleton -->
    <template v-else-if="type === 'card'">
      <div
        v-for="i in count"
        :key="i"
        :class="['rounded-lg border border-slate-200 bg-white p-4', i < count ? 'mb-4' : '']"
      >
        <div class="animate-pulse space-y-3">
          <div class="h-4 w-3/4 rounded bg-slate-200"></div>
          <div class="h-3 w-1/2 rounded bg-slate-200"></div>
          <div class="h-3 w-2/3 rounded bg-slate-200"></div>
        </div>
      </div>
    </template>

    <!-- List Skeleton -->
    <template v-else-if="type === 'list'">
      <div
        v-for="i in count"
        :key="i"
        :class="['flex items-center gap-3 p-3', i < count ? 'border-b border-slate-200' : '']"
      >
        <div class="animate-pulse flex items-center gap-3 flex-1">
          <div class="h-10 w-10 rounded-full bg-slate-200"></div>
          <div class="flex-1 space-y-2">
            <div class="h-4 w-1/2 rounded bg-slate-200"></div>
            <div class="h-3 w-1/3 rounded bg-slate-200"></div>
          </div>
        </div>
      </div>
    </template>

    <!-- Attachment Skeleton -->
    <template v-else-if="type === 'attachment'">
      <div
        v-for="i in count"
        :key="i"
        :class="[
          'flex items-center gap-3 rounded-lg border border-slate-200 bg-white p-3',
          i < count ? 'mb-2' : '',
        ]"
      >
        <div class="animate-pulse flex items-center gap-3 flex-1">
          <div class="h-16 w-16 flex-shrink-0 rounded bg-slate-200"></div>
          <div class="flex-1 space-y-2">
            <div class="h-4 w-48 rounded bg-slate-200"></div>
            <div class="h-3 w-32 rounded bg-slate-200"></div>
          </div>
          <div class="h-8 w-16 rounded bg-slate-200"></div>
        </div>
      </div>
    </template>

    <!-- Timeline Skeleton -->
    <template v-else-if="type === 'timeline'">
      <div
        v-for="i in count"
        :key="i"
        :class="['relative pl-8 pb-8', i === count ? 'pb-0' : '']"
      >
        <div class="animate-pulse">
          <!-- Timeline dot -->
          <div class="absolute left-0 top-1 h-3 w-3 rounded-full bg-slate-200"></div>
          <!-- Timeline line -->
          <div
            v-if="i < count"
            class="absolute left-1.5 top-4 bottom-0 w-0.5 bg-slate-200"
          ></div>
          <!-- Content -->
          <div class="space-y-2">
            <div class="h-4 w-32 rounded bg-slate-200"></div>
            <div class="rounded-lg border border-slate-200 bg-white p-4">
              <div class="space-y-2">
                <div class="h-4 w-3/4 rounded bg-slate-200"></div>
                <div class="h-3 w-1/2 rounded bg-slate-200"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- Screen reader announcement -->
    <span class="sr-only">Loading content...</span>
  </div>
</template>

<style scoped>
/* Ensure smooth animation */
.skeleton-loader {
  min-height: 20px; /* Prevent layout shift */
}

/* Screen reader only utility */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}
</style>
