<script setup lang="ts">
import ActivityItem, { type Activity } from './ActivityItem.vue'

interface Props {
  activities: Activity[]
  loading?: boolean
  totalCount?: number
  hasMore?: boolean
  displayedCount?: number
}

withDefaults(defineProps<Props>(), {
  loading: false,
  totalCount: 0,
  hasMore: false,
  displayedCount: 0,
})

const emit = defineEmits<{
  loadMore: []
}>()
</script>

<template>
  <div
    class="rounded-xl border border-slate-200 bg-white p-6"
    role="region"
    aria-label="Recent activity timeline"
  >
    <h3 class="mb-4 text-lg font-semibold text-slate-900">Recent Activity</h3>

    <!-- Loading State -->
    <div v-if="loading" class="space-y-4">
      <div v-for="i in 5" :key="i" class="flex gap-3">
        <div
          class="h-8 w-8 flex-shrink-0 animate-pulse rounded-full bg-slate-200"
        ></div>
        <div class="flex-1 space-y-2 pt-1">
          <div class="h-4 w-3/4 animate-pulse rounded bg-slate-200"></div>
          <div class="h-3 w-1/4 animate-pulse rounded bg-slate-200"></div>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-else-if="activities.length === 0" class="py-8 text-center">
      <svg
        class="mx-auto h-12 w-12 text-slate-400"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        aria-hidden="true"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
      <p class="mt-2 text-sm text-slate-600">No recent activity</p>
    </div>

    <!-- Activity List -->
    <div v-else>
      <div class="space-y-4">
        <ActivityItem
          v-for="activity in activities"
          :key="activity.id"
          :activity="activity"
        />
      </div>

      <!-- Load More Button -->
      <button
        v-if="hasMore"
        @click="emit('loadMore')"
        :disabled="loading"
        class="mt-6 w-full rounded-lg border-2 border-emerald-600 bg-white px-4 py-3 text-sm font-semibold text-emerald-600 transition hover:bg-emerald-50 focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
        aria-label="Load more activity events"
      >
        <span v-if="loading" class="flex items-center justify-center gap-2">
          <svg
            class="h-4 w-4 animate-spin"
            xmlns="http://www.w3.org/2000/svg"
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
          Loading...
        </span>
        <span v-else>Load More (20 older events)</span>
      </button>

      <!-- Progress Indicator -->
      <p
        v-if="totalCount > 0"
        class="mt-3 text-center text-xs text-slate-500 sm:text-sm"
      >
        Showing {{ displayedCount }} of {{ totalCount }} events from the last 90 days
      </p>
    </div>
  </div>
</template>

<style scoped>
/* Respect user's motion preferences for accessibility */
@media (prefers-reduced-motion: reduce) {
  .animate-pulse {
    animation: none !important;
  }
}
</style>
