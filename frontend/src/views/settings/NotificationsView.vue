<script setup lang="ts">
/**
 * Notifications Settings View
 *
 * Notification preferences settings page.
 * Features:
 * - Notification settings with auto-save
 * - Master toggle for all email notifications
 * - Progressive disclosure (show time pickers only when enabled)
 * - Mobile responsive design
 * - Uses reusable SettingsCard component for consistency
 */

import { onMounted, computed } from 'vue'
import ToggleSwitch from '@/components/common/ToggleSwitch.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import SettingsCard from '@/components/settings/SettingsCard.vue'
import { useNotificationSettings } from '@/composables/useNotificationSettings'
import { REMINDER_MINUTE_OPTIONS } from '@/types/notification-settings'

const { settings, isLoading, error, loadSettings } = useNotificationSettings()

/**
 * Load settings on mount
 */
onMounted(async () => {
  await loadSettings()
})

/**
 * Check if settings container should be shown (master toggle is on)
 */
const showSettingsContainer = computed(() => settings.value?.email_enabled ?? false)

/**
 * Day of week configuration
 */
const weekDays = [
  { value: 0, label: 'Sunday', shortLabel: 'S' },
  { value: 1, label: 'Monday', shortLabel: 'M' },
  { value: 2, label: 'Tuesday', shortLabel: 'T' },
  { value: 3, label: 'Wednesday', shortLabel: 'W' },
  { value: 4, label: 'Thursday', shortLabel: 'T' },
  { value: 5, label: 'Friday', shortLabel: 'F' },
  { value: 6, label: 'Saturday', shortLabel: 'S' },
]

/**
 * Check if a specific day is selected
 */
function isDaySelected(dayValue: number): boolean {
  return settings.value?.digest_days?.includes(dayValue) ?? false
}

/**
 * Toggle day selection
 * Prevents removing the last day (at least one day must be selected)
 */
function toggleDay(dayValue: number): void {
  if (!settings.value) return

  const days = [...(settings.value.digest_days || [])]
  const index = days.indexOf(dayValue)

  if (index === -1) {
    // Add day
    days.push(dayValue)
    days.sort((a, b) => a - b) // Keep sorted
  } else {
    // Remove day (but prevent removing last day)
    if (days.length > 1) {
      days.splice(index, 1)
    }
    // If trying to remove last day, do nothing
  }

  settings.value.digest_days = days
}

/**
 * Select weekdays only (Monday-Friday)
 */
function selectWeekdays(): void {
  if (!settings.value) return
  settings.value.digest_days = [1, 2, 3, 4, 5]
}

/**
 * Select all days (Sunday-Saturday)
 */
function selectAllDays(): void {
  if (!settings.value) return
  settings.value.digest_days = [0, 1, 2, 3, 4, 5, 6]
}
</script>

<template>
  <div>
    <!-- Loading State -->
    <div v-if="isLoading" class="flex items-center justify-center py-12">
      <LoadingSpinner />
    </div>

    <!-- Error State -->
    <div
      v-else-if="error"
      class="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800"
    >
      <strong>Error:</strong> {{ error }}
    </div>

    <!-- Notification Settings -->
    <div v-else-if="settings">
      <!-- Master Toggle Card -->
      <SettingsCard
        title="Email Notifications"
        description="Stay on top of your schedule with automated email reminders and daily summaries"
        class="mb-8"
      >
        <template #icon>
          <svg
            class="h-6 w-6 text-slate-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
            />
          </svg>
        </template>

        <template #toggle>
          <ToggleSwitch
            v-model="settings.email_enabled"
            label="Enable email notifications"
            description="Master toggle for all email notifications"
          />
        </template>

        <template #warning>
          <!-- Warning Banner when master toggle is off -->
          <div
            v-if="!settings.email_enabled"
            class="rounded-md bg-amber-50 p-3 text-sm text-amber-800"
          >
            <div class="flex items-center gap-2">
              <svg
                class="h-5 w-5 flex-shrink-0"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path
                  fill-rule="evenodd"
                  d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                  clip-rule="evenodd"
                />
              </svg>
              <span>All email notifications are currently disabled</span>
            </div>
          </div>
        </template>
      </SettingsCard>

      <!-- Settings Container (hidden when master toggle is off) -->
      <div
        v-if="showSettingsContainer"
        class="space-y-8 transition-opacity duration-200"
      >
        <!-- Daily Digest Group -->
        <SettingsCard
          title="Daily Digest"
          description="Receive a morning summary of today's appointments"
          :expanded="settings.digest_enabled"
        >
          <template #toggle>
            <ToggleSwitch
              v-model="settings.digest_enabled"
              label="Enable daily digest"
            />
          </template>

          <template #content>
            <div class="space-y-4">
              <!-- Send Time -->
              <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
                <label class="text-sm font-medium text-slate-900">Send at</label>
                <input
                  v-model="settings.digest_time"
                  type="time"
                  class="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-100"
                />
              </div>

              <!-- Day Selector -->
              <div class="flex flex-col gap-3">
                <div class="flex items-center justify-between">
                  <label class="text-sm font-medium text-slate-900">Send on</label>

                  <!-- Quick Actions -->
                  <div class="flex gap-2 text-xs">
                    <button
                      type="button"
                      class="text-emerald-600 hover:text-emerald-700 focus:underline focus:outline-none"
                      @click="selectWeekdays"
                    >
                      Weekdays only
                    </button>
                    <span class="text-slate-300">|</span>
                    <button
                      type="button"
                      class="text-emerald-600 hover:text-emerald-700 focus:underline focus:outline-none"
                      @click="selectAllDays"
                    >
                      Every day
                    </button>
                  </div>
                </div>

                <!-- Day Toggle Buttons -->
                <div class="grid grid-cols-7 gap-2">
                  <button
                    v-for="day in weekDays"
                    :key="day.value"
                    type="button"
                    :class="[
                      'flex h-10 items-center justify-center rounded-md border text-sm font-medium transition-colors',
                      'focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 focus:outline-none',
                      isDaySelected(day.value)
                        ? 'border-emerald-600 bg-emerald-600 text-white hover:bg-emerald-700'
                        : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400 hover:bg-slate-50',
                    ]"
                    :aria-label="`${day.label}, ${isDaySelected(day.value) ? 'selected' : 'not selected'}`"
                    @click="toggleDay(day.value)"
                  >
                    <span class="hidden sm:inline">{{ day.label }}</span>
                    <span class="sm:hidden">{{ day.shortLabel }}</span>
                  </button>
                </div>

                <!-- Warning State (no days selected) -->
                <div
                  v-if="settings.digest_days?.length === 0"
                  class="flex items-start gap-2 rounded-md bg-amber-50 p-3 text-sm text-amber-800"
                >
                  <svg
                    class="h-5 w-5 flex-shrink-0"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fill-rule="evenodd"
                      d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                      clip-rule="evenodd"
                    />
                  </svg>
                  <span>Select at least one day to receive the daily digest</span>
                </div>
              </div>
            </div>
          </template>
        </SettingsCard>

        <!-- Appointment Reminders Group -->
        <SettingsCard
          title="Appointment Reminders"
          description="Get notified before each appointment starts"
          :expanded="settings.reminder_enabled"
        >
          <template #toggle>
            <ToggleSwitch
              v-model="settings.reminder_enabled"
              label="Enable appointment reminders"
            />
          </template>

          <template #content>
            <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
              <label class="text-sm font-medium text-slate-900">Remind me</label>
              <select
                v-model.number="settings.reminder_minutes"
                class="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-100"
              >
                <option
                  v-for="option in REMINDER_MINUTE_OPTIONS"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </option>
              </select>
            </div>
          </template>
        </SettingsCard>

        <!-- Session Notes Reminders Group -->
        <SettingsCard
          title="Session Notes Reminder"
          description="Daily reminder to complete unfinished session notes"
          :expanded="settings.notes_reminder_enabled"
        >
          <template #toggle>
            <ToggleSwitch
              v-model="settings.notes_reminder_enabled"
              label="Enable session notes reminder"
            />
          </template>

          <template #content>
            <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
              <label class="text-sm font-medium text-slate-900">Send at</label>
              <input
                v-model="settings.notes_reminder_time"
                type="time"
                class="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-100"
              />
            </div>
          </template>
        </SettingsCard>
      </div>
    </div>
  </div>
</template>
