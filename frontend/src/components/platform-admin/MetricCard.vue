<script setup lang="ts">
interface Props {
  title: string
  value: number | string
  change?: number
  changeType?: 'increase' | 'decrease'
  icon?: 'workspaces' | 'users' | 'invitations' | 'blacklist'
  loading?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  change: undefined,
  changeType: undefined,
  icon: undefined,
  loading: false,
})

const iconPaths: Record<string, string> = {
  workspaces:
    'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
  users:
    'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z',
  invitations:
    'M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z',
  blacklist:
    'M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636',
}

const changeColor =
  props.changeType === 'increase' ? 'text-emerald-600' : 'text-red-600'
const changeIcon =
  props.changeType === 'increase'
    ? 'M5 10l7-7m0 0l7 7m-7-7v18'
    : 'M19 14l-7 7m0 0l-7-7m7 7V3'
</script>

<template>
  <div
    class="rounded-xl border border-slate-200 bg-white p-6 transition hover:shadow-md"
    role="region"
    :aria-label="`${title} metric`"
  >
    <div class="flex items-start justify-between">
      <div class="flex-1">
        <p class="text-sm font-medium text-slate-600">{{ title }}</p>

        <!-- Loading State -->
        <div v-if="loading" class="mt-2">
          <div class="h-10 w-24 animate-pulse rounded bg-slate-200"></div>
        </div>

        <!-- Value -->
        <div v-else>
          <p class="mt-2 text-4xl font-bold text-slate-900">{{ value }}</p>

          <!-- Change Indicator -->
          <div v-if="change !== undefined" class="mt-2 flex items-center text-sm">
            <svg
              :class="[changeColor, 'mr-1 h-4 w-4']"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                :d="changeIcon"
              />
            </svg>
            <span :class="[changeColor, 'font-medium']"> {{ Math.abs(change) }}% </span>
            <span class="ml-1 text-slate-600">vs last month</span>
          </div>
        </div>
      </div>

      <!-- Icon -->
      <div
        v-if="icon"
        class="flex h-12 w-12 items-center justify-center rounded-lg bg-emerald-100"
        aria-hidden="true"
      >
        <svg
          class="h-6 w-6 text-emerald-600"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            :d="iconPaths[icon]"
          />
        </svg>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Respect user's motion preferences for accessibility */
@media (prefers-reduced-motion: reduce) {
  .transition,
  .animate-pulse {
    animation: none !important;
    transition: none !important;
  }
}
</style>
