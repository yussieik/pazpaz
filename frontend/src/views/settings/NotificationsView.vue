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
import { useI18n } from '@/composables/useI18n'
import ToggleSwitch from '@/components/common/ToggleSwitch.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import SettingsCard from '@/components/settings/SettingsCard.vue'
import { useNotificationSettings } from '@/composables/useNotificationSettings'

const { t } = useI18n()
const { settings, isLoading, error, loadSettings } = useNotificationSettings()

/**
 * Reminder minute options (computed to support i18n)
 */
const reminderMinuteOptions = computed(() => [
  { value: 15, label: t('settings.notifications.appointmentReminders.minutes15') },
  { value: 30, label: t('settings.notifications.appointmentReminders.minutes30') },
  { value: 60, label: t('settings.notifications.appointmentReminders.minutes60') },
  { value: 120, label: t('settings.notifications.appointmentReminders.minutes120') },
  { value: 1440, label: t('settings.notifications.appointmentReminders.minutes1440') },
])

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
 * Day of week configuration (computed to support i18n)
 */
const weekDays = computed(() => [
  { value: 0, label: t('settings.notifications.weekDays.sunday'), shortLabel: t('settings.notifications.weekDays.sundayShort') },
  { value: 1, label: t('settings.notifications.weekDays.monday'), shortLabel: t('settings.notifications.weekDays.mondayShort') },
  { value: 2, label: t('settings.notifications.weekDays.tuesday'), shortLabel: t('settings.notifications.weekDays.tuesdayShort') },
  { value: 3, label: t('settings.notifications.weekDays.wednesday'), shortLabel: t('settings.notifications.weekDays.wednesdayShort') },
  { value: 4, label: t('settings.notifications.weekDays.thursday'), shortLabel: t('settings.notifications.weekDays.thursdayShort') },
  { value: 5, label: t('settings.notifications.weekDays.friday'), shortLabel: t('settings.notifications.weekDays.fridayShort') },
  { value: 6, label: t('settings.notifications.weekDays.saturday'), shortLabel: t('settings.notifications.weekDays.saturdayShort') },
])

/**
 * Check if a specific day is selected for today's digest
 */
function isDaySelected(dayValue: number): boolean {
  return settings.value?.digest_days?.includes(dayValue) ?? false
}

/**
 * Toggle day selection for today's digest
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
 * Select weekdays only (Monday-Friday) for today's digest
 */
function selectWeekdays(): void {
  if (!settings.value) return
  settings.value.digest_days = [1, 2, 3, 4, 5]
}

/**
 * Select all days (Sunday-Saturday) for today's digest
 */
function selectAllDays(): void {
  if (!settings.value) return
  settings.value.digest_days = [0, 1, 2, 3, 4, 5, 6]
}

/**
 * Check if a specific day is selected for tomorrow's digest
 */
function isTomorrowDaySelected(dayValue: number): boolean {
  return settings.value?.tomorrow_digest_days?.includes(dayValue) ?? false
}

/**
 * Toggle day selection for tomorrow's digest
 * Prevents removing the last day (at least one day must be selected)
 */
function toggleTomorrowDay(dayValue: number): void {
  if (!settings.value) return

  const days = [...(settings.value.tomorrow_digest_days || [])]
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

  settings.value.tomorrow_digest_days = days
}

/**
 * Select weekdays only (Sunday-Thursday) for tomorrow's digest
 * Sunday-Thursday sends digest for Monday-Friday
 */
function selectTomorrowWeekdays(): void {
  if (!settings.value) return
  settings.value.tomorrow_digest_days = [0, 1, 2, 3, 4]
}

/**
 * Select all days (Sunday-Saturday) for tomorrow's digest
 */
function selectTomorrowAllDays(): void {
  if (!settings.value) return
  settings.value.tomorrow_digest_days = [0, 1, 2, 3, 4, 5, 6]
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
      <strong>{{ t('settings.notifications.errorPrefix') }}</strong> {{ error }}
    </div>

    <!-- Notification Settings -->
    <div v-else-if="settings">
      <!-- Master Toggle Card -->
      <SettingsCard
        :title="t('settings.notifications.masterToggle.title')"
        :description="t('settings.notifications.masterToggle.description')"
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
            :label="t('settings.notifications.masterToggle.label')"
            :description="t('settings.notifications.masterToggle.labelDescription')"
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
              <span>{{ t('settings.notifications.masterToggle.warningDisabled') }}</span>
            </div>
          </div>
        </template>
      </SettingsCard>

      <!-- Settings Container (hidden when master toggle is off) -->
      <div
        v-if="showSettingsContainer"
        class="space-y-8 transition-opacity duration-200"
      >
        <!-- Today's Schedule Group -->
        <SettingsCard
          :title="t('settings.notifications.todayDigest.title')"
          :description="t('settings.notifications.todayDigest.description')"
          :expanded="settings.digest_enabled"
        >
          <template #toggle>
            <ToggleSwitch
              v-model="settings.digest_enabled"
              :label="t('settings.notifications.todayDigest.label')"
            />
          </template>

          <template #content>
            <div class="space-y-4">
              <!-- Send Time -->
              <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
                <label class="text-sm font-medium text-slate-900">{{
                  t('settings.notifications.todayDigest.sendAtLabel')
                }}</label>
                <input
                  v-model="settings.digest_time"
                  type="time"
                  class="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-100"
                />
              </div>

              <!-- Day Selector -->
              <div class="flex flex-col gap-3">
                <div class="flex items-center justify-between">
                  <label class="text-sm font-medium text-slate-900">{{
                    t('settings.notifications.todayDigest.sendOnLabel')
                  }}</label>

                  <!-- Quick Actions -->
                  <div class="flex gap-2 text-xs">
                    <button
                      type="button"
                      class="text-emerald-600 hover:text-emerald-700 focus:underline focus:outline-none"
                      @click="selectWeekdays"
                    >
                      {{ t('settings.notifications.todayDigest.weekdaysOnly') }}
                    </button>
                    <span class="text-slate-300">|</span>
                    <button
                      type="button"
                      class="text-emerald-600 hover:text-emerald-700 focus:underline focus:outline-none"
                      @click="selectAllDays"
                    >
                      {{ t('settings.notifications.todayDigest.everyDay') }}
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
                    :aria-label="
                      t('settings.notifications.dayStatus.ariaLabel', {
                        day: day.label,
                        status: isDaySelected(day.value)
                          ? t('settings.notifications.dayStatus.selected')
                          : t('settings.notifications.dayStatus.notSelected'),
                      })
                    "
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
                  <span>{{ t('settings.notifications.todayDigest.warningNoDays') }}</span>
                </div>
              </div>
            </div>
          </template>
        </SettingsCard>

        <!-- Tomorrow's Schedule Group -->
        <SettingsCard
          :title="t('settings.notifications.tomorrowDigest.title')"
          :description="t('settings.notifications.tomorrowDigest.description')"
          :expanded="settings.tomorrow_digest_enabled"
        >
          <template #toggle>
            <ToggleSwitch
              v-model="settings.tomorrow_digest_enabled"
              :label="t('settings.notifications.tomorrowDigest.label')"
            />
          </template>

          <template #content>
            <div class="space-y-4">
              <!-- Send Time -->
              <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
                <label class="text-sm font-medium text-slate-900">{{
                  t('settings.notifications.tomorrowDigest.sendAtLabel')
                }}</label>
                <input
                  v-model="settings.tomorrow_digest_time"
                  type="time"
                  class="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-100"
                />
              </div>

              <!-- Day Selector -->
              <div class="flex flex-col gap-3">
                <div class="flex items-center justify-between">
                  <label class="text-sm font-medium text-slate-900">{{
                    t('settings.notifications.tomorrowDigest.sendOnLabel')
                  }}</label>

                  <!-- Quick Actions -->
                  <div class="flex gap-2 text-xs">
                    <button
                      type="button"
                      class="text-emerald-600 hover:text-emerald-700 focus:underline focus:outline-none"
                      @click="selectTomorrowWeekdays"
                    >
                      {{ t('settings.notifications.tomorrowDigest.weekdaysOnly') }}
                    </button>
                    <span class="text-slate-300">|</span>
                    <button
                      type="button"
                      class="text-emerald-600 hover:text-emerald-700 focus:underline focus:outline-none"
                      @click="selectTomorrowAllDays"
                    >
                      {{ t('settings.notifications.tomorrowDigest.everyDay') }}
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
                      isTomorrowDaySelected(day.value)
                        ? 'border-emerald-600 bg-emerald-600 text-white hover:bg-emerald-700'
                        : 'border-slate-300 bg-white text-slate-700 hover:border-slate-400 hover:bg-slate-50',
                    ]"
                    :aria-label="
                      t('settings.notifications.dayStatus.ariaLabel', {
                        day: day.label,
                        status: isTomorrowDaySelected(day.value)
                          ? t('settings.notifications.dayStatus.selected')
                          : t('settings.notifications.dayStatus.notSelected'),
                      })
                    "
                    @click="toggleTomorrowDay(day.value)"
                  >
                    <span class="hidden sm:inline">{{ day.label }}</span>
                    <span class="sm:hidden">{{ day.shortLabel }}</span>
                  </button>
                </div>

                <!-- Warning State (no days selected) -->
                <div
                  v-if="settings.tomorrow_digest_days?.length === 0"
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
                  <span>{{ t('settings.notifications.tomorrowDigest.warningNoDays') }}</span>
                </div>
              </div>
            </div>
          </template>
        </SettingsCard>

        <!-- Appointment Reminders Group -->
        <SettingsCard
          :title="t('settings.notifications.appointmentReminders.title')"
          :description="t('settings.notifications.appointmentReminders.description')"
          :expanded="settings.reminder_enabled"
        >
          <template #toggle>
            <ToggleSwitch
              v-model="settings.reminder_enabled"
              :label="t('settings.notifications.appointmentReminders.label')"
            />
          </template>

          <template #content>
            <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
              <label class="text-sm font-medium text-slate-900">{{
                t('settings.notifications.appointmentReminders.remindMeLabel')
              }}</label>
              <select
                v-model.number="settings.reminder_minutes"
                class="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500 focus:outline-none disabled:cursor-not-allowed disabled:bg-slate-100"
              >
                <option
                  v-for="option in reminderMinuteOptions"
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
          :title="t('settings.notifications.sessionNotesReminder.title')"
          :description="t('settings.notifications.sessionNotesReminder.description')"
          :expanded="settings.notes_reminder_enabled"
        >
          <template #toggle>
            <ToggleSwitch
              v-model="settings.notes_reminder_enabled"
              :label="t('settings.notifications.sessionNotesReminder.label')"
            />
          </template>

          <template #content>
            <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
              <label class="text-sm font-medium text-slate-900">{{
                t('settings.notifications.sessionNotesReminder.sendAtLabel')
              }}</label>
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
