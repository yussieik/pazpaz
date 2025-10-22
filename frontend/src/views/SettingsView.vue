<script setup lang="ts">
/**
 * Settings View
 *
 * Main settings page for PazPaz with notification preferences.
 * Features:
 * - Notification settings with auto-save
 * - Master toggle for all email notifications
 * - Progressive disclosure (show time pickers only when enabled)
 * - Mobile responsive design
 */

import { onMounted, computed } from 'vue'
import ToggleSwitch from '@/components/common/ToggleSwitch.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
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
</script>

<template>
  <div class="container mx-auto px-4 py-8 sm:px-6 lg:px-8">
    <!-- Page Header -->
    <div class="mb-8">
      <h1 class="text-2xl font-semibold text-slate-900">Settings</h1>
      <p class="mt-1 text-sm text-slate-600">
        Manage your account preferences and notification settings
      </p>
    </div>

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
    <div v-else-if="settings" class="mx-auto max-w-4xl">

      <!-- Master Toggle Card -->
      <div class="mb-8 rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div class="flex items-start justify-between gap-4">
          <div class="flex items-start gap-4">
            <!-- Mail Icon -->
            <div class="flex-shrink-0">
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
            </div>

            <!-- Title and Description -->
            <div>
              <h2 class="text-base font-semibold text-slate-900">Email Notifications</h2>
              <p class="mt-1 text-sm text-slate-600">
                Receive email updates about appointments, clients, and session notes
              </p>
            </div>
          </div>

          <!-- Master Toggle -->
          <div class="flex-shrink-0">
            <ToggleSwitch
              v-model="settings.email_enabled"
              label="Enable email notifications"
              description="Master toggle for all email notifications"
            />
          </div>
        </div>

        <!-- Warning Banner when master toggle is off -->
        <div
          v-if="!settings.email_enabled"
          class="mt-4 rounded-md bg-amber-50 p-3 text-sm text-amber-800"
        >
          <div class="flex items-center gap-2">
            <svg class="h-5 w-5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path
                fill-rule="evenodd"
                d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                clip-rule="evenodd"
              />
            </svg>
            <span>All email notifications are currently disabled</span>
          </div>
        </div>
      </div>

      <!-- Settings Container (hidden when master toggle is off) -->
      <div
        v-if="showSettingsContainer"
        class="space-y-8 transition-opacity duration-200"
      >
        <!-- Event Notifications Group -->
        <div class="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <h3 class="mb-4 text-sm font-semibold text-slate-900">Event Notifications</h3>
          <div class="space-y-3">
            <!-- New appointment booked -->
            <div class="flex items-center justify-between">
              <div>
                <label class="text-sm font-medium text-slate-900">New appointment booked</label>
                <p class="text-xs text-slate-600">
                  When a client books a new appointment
                </p>
              </div>
              <ToggleSwitch
                v-model="settings.notify_appointment_booked"
                
                label="Notify when appointment booked"
              />
            </div>

            <!-- Appointment cancelled -->
            <div class="flex items-center justify-between">
              <div>
                <label class="text-sm font-medium text-slate-900">Appointment cancelled</label>
                <p class="text-xs text-slate-600">
                  When an appointment is cancelled
                </p>
              </div>
              <ToggleSwitch
                v-model="settings.notify_appointment_cancelled"
                
                label="Notify when appointment cancelled"
              />
            </div>

            <!-- Appointment rescheduled -->
            <div class="flex items-center justify-between">
              <div>
                <label class="text-sm font-medium text-slate-900">Appointment rescheduled</label>
                <p class="text-xs text-slate-600">
                  When an appointment is moved to a new time
                </p>
              </div>
              <ToggleSwitch
                v-model="settings.notify_appointment_rescheduled"
                
                label="Notify when appointment rescheduled"
              />
            </div>

            <!-- Client confirmed -->
            <div class="flex items-center justify-between">
              <div>
                <label class="text-sm font-medium text-slate-900">Client confirmed</label>
                <p class="text-xs text-slate-600">
                  When a client confirms their appointment
                </p>
              </div>
              <ToggleSwitch
                v-model="settings.notify_appointment_confirmed"
                
                label="Notify when client confirms appointment"
              />
            </div>
          </div>
        </div>

        <!-- Daily Digest Group -->
        <div class="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <div class="mb-4 flex items-center justify-between">
            <div>
              <h3 class="text-sm font-semibold text-slate-900">Daily Digest</h3>
              <p class="text-xs text-slate-600">
                Daily summary of upcoming appointments
              </p>
            </div>
            <ToggleSwitch
              v-model="settings.digest_enabled"
              
              label="Enable daily digest"
            />
          </div>

          <!-- Time Picker (conditional) -->
          <div
            v-if="settings.digest_enabled"
            class="mt-4 space-y-3 rounded-md bg-slate-50 p-4"
          >
            <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
              <label class="text-sm font-medium text-slate-900">Send at</label>
              <input
                v-model="settings.digest_time"
                type="time"
                
                class="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:cursor-not-allowed disabled:bg-slate-100"
              />
            </div>

            <div class="flex items-center gap-2">
              <input
                id="skip-weekends"
                v-model="settings.digest_skip_weekends"
                type="checkbox"
                
                class="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-2 focus:ring-emerald-500 disabled:cursor-not-allowed"
              />
              <label for="skip-weekends" class="text-sm text-slate-900">
                Skip weekends
              </label>
            </div>
          </div>
        </div>

        <!-- Appointment Reminders Group -->
        <div class="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <div class="mb-4 flex items-center justify-between">
            <div>
              <h3 class="text-sm font-semibold text-slate-900">Appointment Reminders</h3>
              <p class="text-xs text-slate-600">
                Remind yourself before appointments start
              </p>
            </div>
            <ToggleSwitch
              v-model="settings.reminder_enabled"
              
              label="Enable appointment reminders"
            />
          </div>

          <!-- Time Before Dropdown (conditional) -->
          <div
            v-if="settings.reminder_enabled"
            class="mt-4 rounded-md bg-slate-50 p-4"
          >
            <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
              <label class="text-sm font-medium text-slate-900">Remind me</label>
              <select
                v-model.number="settings.reminder_minutes"
                
                class="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:cursor-not-allowed disabled:bg-slate-100"
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
          </div>
        </div>

        <!-- Session Notes Reminders Group -->
        <div class="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
          <div class="mb-4 flex items-center justify-between">
            <div>
              <h3 class="text-sm font-semibold text-slate-900">Session Notes Reminder</h3>
              <p class="text-xs text-slate-600">
                Daily reminder to complete pending session notes
              </p>
            </div>
            <ToggleSwitch
              v-model="settings.notes_reminder_enabled"
              
              label="Enable session notes reminder"
            />
          </div>

          <!-- Time Picker (conditional) -->
          <div
            v-if="settings.notes_reminder_enabled"
            class="mt-4 rounded-md bg-slate-50 p-4"
          >
            <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
              <label class="text-sm font-medium text-slate-900">Send at</label>
              <input
                v-model="settings.notes_reminder_time"
                type="time"
                
                class="rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:cursor-not-allowed disabled:bg-slate-100"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
