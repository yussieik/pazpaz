<script setup lang="ts">
import { ref } from 'vue'
import type { ViewType } from '@/types/calendar'

interface Props {
  currentView: ViewType
  formattedDateRange: string
  appointmentSummary?: string | null
  loading?: boolean
}

interface Emits {
  (e: 'update:view', view: ViewType): void
  (e: 'previous'): void
  (e: 'next'): void
  (e: 'today'): void
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
})

const emit = defineEmits<Emits>()

// Template refs for button elements (for keyboard shortcut visual feedback)
const todayButtonRef = ref<HTMLButtonElement>()
const previousButtonRef = ref<HTMLButtonElement>()
const nextButtonRef = ref<HTMLButtonElement>()
const weekButtonRef = ref<HTMLButtonElement>()
const dayButtonRef = ref<HTMLButtonElement>()
const monthButtonRef = ref<HTMLButtonElement>()

// Expose refs for parent component to access
defineExpose({
  todayButtonRef,
  previousButtonRef,
  nextButtonRef,
  weekButtonRef,
  dayButtonRef,
  monthButtonRef,
})
</script>

<template>
  <div class="relative border-b border-slate-200 bg-white px-6 py-3.5">
    <!-- Loading bar -->
    <div
      v-if="props.loading"
      class="absolute top-0 right-0 left-0 h-0.5 animate-pulse bg-emerald-600"
      aria-hidden="true"
    ></div>

    <!-- Single-row layout -->
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <!-- Left: Navigation and Date -->
      <div
        class="flex items-center gap-4"
        :class="{ 'pointer-events-none opacity-50': props.loading }"
      >
        <button
          ref="todayButtonRef"
          @click="emit('today')"
          class="min-h-[44px] rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none"
        >
          Today
        </button>

        <div class="flex items-center gap-0.5">
          <button
            ref="previousButtonRef"
            @click="emit('previous')"
            class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2.5 text-slate-600 transition-colors hover:bg-slate-100 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none sm:min-h-0 sm:min-w-0 sm:p-2"
            aria-label="Previous period"
          >
            <svg
              class="h-5 w-5 flex-shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M15 19l-7-7 7-7"
              />
            </svg>
          </button>
          <button
            ref="nextButtonRef"
            @click="emit('next')"
            class="flex min-h-[44px] min-w-[44px] items-center justify-center rounded-lg p-2.5 text-slate-600 transition-colors hover:bg-slate-100 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none sm:min-h-0 sm:min-w-0 sm:p-2"
            aria-label="Next period"
          >
            <svg
              class="h-5 w-5 flex-shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M9 5l7 7-7 7"
              />
            </svg>
          </button>
        </div>

        <div class="h-6 w-px bg-slate-300" aria-hidden="true"></div>

        <h2
          class="flex flex-col gap-1 text-lg font-semibold text-slate-900 sm:flex-row sm:items-baseline sm:gap-2"
        >
          <span>{{ formattedDateRange }}</span>
          <span
            v-if="appointmentSummary"
            class="text-sm font-medium text-slate-600"
            aria-live="polite"
            :aria-label="`${appointmentSummary} in this period`"
          >
            <span class="hidden text-slate-400 sm:inline" aria-hidden="true">·</span>
            {{ appointmentSummary }}
          </span>
        </h2>
      </div>

      <!-- Right: View Switcher -->
      <div class="flex items-center justify-center gap-3 sm:justify-end">
        <div
          class="inline-flex items-center"
          role="group"
          aria-label="Calendar view switcher"
        >
          <!-- Week Button -->
          <button
            ref="weekButtonRef"
            @click="emit('update:view', 'timeGridWeek')"
            :class="[
              'min-h-[44px] min-w-[44px] px-3 py-2 text-sm font-medium transition-all duration-150 ease-in-out',
              'border-y border-l first:rounded-l-md last:rounded-r-md',
              'focus-visible:z-10 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none',
              currentView === 'timeGridWeek'
                ? 'z-10 border-2 border-slate-900 bg-white font-semibold text-slate-900 shadow-sm'
                : 'border-slate-200 bg-transparent text-slate-600 hover:bg-slate-50 hover:text-slate-900',
            ]"
            :aria-pressed="currentView === 'timeGridWeek'"
            aria-label="Switch to Week view"
          >
            <span class="hidden sm:inline">Week</span>
            <span class="sm:hidden">W</span>
          </button>

          <!-- Day Button -->
          <button
            ref="dayButtonRef"
            @click="emit('update:view', 'timeGridDay')"
            :class="[
              'min-h-[44px] min-w-[44px] px-3 py-2 text-sm font-medium transition-all duration-150 ease-in-out',
              'border-y border-l',
              'focus-visible:z-10 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none',
              currentView === 'timeGridDay'
                ? 'z-10 border-2 border-slate-900 bg-white font-semibold text-slate-900 shadow-sm'
                : 'border-slate-200 bg-transparent text-slate-600 hover:bg-slate-50 hover:text-slate-900',
            ]"
            :aria-pressed="currentView === 'timeGridDay'"
            aria-label="Switch to Day view"
          >
            <span class="hidden sm:inline">Day</span>
            <span class="sm:hidden">D</span>
          </button>

          <!-- Month Button -->
          <button
            ref="monthButtonRef"
            @click="emit('update:view', 'dayGridMonth')"
            :class="[
              'min-h-[44px] min-w-[44px] px-3 py-2 text-sm font-medium transition-all duration-150 ease-in-out',
              'rounded-r-md border',
              'focus-visible:z-10 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none',
              currentView === 'dayGridMonth'
                ? 'z-10 border-2 border-slate-900 bg-white font-semibold text-slate-900 shadow-sm'
                : 'border-slate-200 bg-transparent text-slate-600 hover:bg-slate-50 hover:text-slate-900',
            ]"
            :aria-pressed="currentView === 'dayGridMonth'"
            aria-label="Switch to Month view"
          >
            <span class="hidden sm:inline">Month</span>
            <span class="sm:hidden">M</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
