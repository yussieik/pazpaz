<script setup lang="ts">
import type { ViewType } from '@/types/calendar'

interface Props {
  currentView: ViewType
  formattedDateRange: string
  loading?: boolean
}

interface Emits {
  (e: 'update:view', view: ViewType): void
  (e: 'previous'): void
  (e: 'next'): void
  (e: 'today'): void
  (e: 'createAppointment'): void
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
})

const emit = defineEmits<Emits>()
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
          @click="emit('today')"
          class="rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none"
        >
          Today
        </button>

        <div class="flex items-center gap-0.5">
          <button
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

        <h2 class="text-lg font-semibold text-slate-900">
          {{ formattedDateRange }}
        </h2>
      </div>

      <!-- Right: View Switcher and Primary Action -->
      <div class="flex items-center gap-3">
        <div
          class="inline-flex gap-0.5 rounded-lg bg-slate-100 p-0.5"
          role="group"
          aria-label="Calendar view switcher"
        >
          <button
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

        <button
          @click="emit('createAppointment')"
          class="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-emerald-700 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 4v16m8-8H4"
            />
          </svg>
          New Appointment
        </button>
      </div>
    </div>
  </div>
</template>
