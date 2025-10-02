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
    <div class="flex items-center justify-between gap-6">
      <!-- Left: Navigation and Date -->
      <div
        class="flex items-center gap-4"
        :class="{ 'pointer-events-none opacity-50': props.loading }"
      >
        <button
          ref="todayButtonRef"
          @click="emit('today')"
          class="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none"
        >
          Today
        </button>

        <div class="flex items-center gap-0.5">
          <button
            ref="previousButtonRef"
            @click="emit('previous')"
            class="rounded-lg p-2 text-slate-600 transition-colors hover:bg-slate-100 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none"
            aria-label="Previous period"
          >
            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
            class="rounded-lg p-2 text-slate-600 transition-colors hover:bg-slate-100 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none"
            aria-label="Next period"
          >
            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
      <div class="flex items-center gap-3">
        <div
          class="inline-flex gap-0.5 rounded-lg bg-slate-100 p-0.5"
          role="group"
          aria-label="Calendar view switcher"
        >
          <button
            ref="weekButtonRef"
            @click="emit('update:view', 'timeGridWeek')"
            :class="[
              'rounded-md px-3.5 py-1.5 text-sm font-medium transition-all duration-150 ease-in-out focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none',
              currentView === 'timeGridWeek'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-600 hover:text-slate-900',
            ]"
            :aria-pressed="currentView === 'timeGridWeek'"
          >
            Week
          </button>
          <button
            ref="dayButtonRef"
            @click="emit('update:view', 'timeGridDay')"
            :class="[
              'rounded-md px-3.5 py-1.5 text-sm font-medium transition-all duration-150 ease-in-out focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none',
              currentView === 'timeGridDay'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-600 hover:text-slate-900',
            ]"
            :aria-pressed="currentView === 'timeGridDay'"
          >
            Day
          </button>
          <button
            ref="monthButtonRef"
            @click="emit('update:view', 'dayGridMonth')"
            :class="[
              'rounded-md px-3.5 py-1.5 text-sm font-medium transition-all duration-150 ease-in-out focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none',
              currentView === 'dayGridMonth'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-600 hover:text-slate-900',
            ]"
            :aria-pressed="currentView === 'dayGridMonth'"
          >
            Month
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
