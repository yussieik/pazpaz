<script setup lang="ts">
import ActivityItem, { type Activity } from './ActivityItem.vue'

interface Props {
  activities: Activity[]
  loading?: boolean
}

withDefaults(defineProps<Props>(), {
  loading: false,
})
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
    <div v-else class="space-y-4">
      <ActivityItem
        v-for="activity in activities"
        :key="activity.id"
        :activity="activity"
      />
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
