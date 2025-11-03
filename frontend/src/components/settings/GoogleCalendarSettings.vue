<script setup lang="ts">
/**
 * Google Calendar Settings Component
 *
 * Manages Google Calendar OAuth integration for automatic appointment syncing.
 *
 * Features:
 * - OAuth flow via popup window
 * - Connection status display with last sync time
 * - Sync settings toggle (auto sync enable/disable)
 * - HIPAA warning about PHI in calendar events
 * - Disconnect integration with confirmation modal
 *
 * States:
 * - Not Connected: Shows connect button and HIPAA warning
 * - Connected: Shows settings, last sync, disconnect option
 *
 * OAuth Flow:
 * 1. User clicks "Connect to Google Calendar"
 * 2. Opens OAuth popup (600x700px)
 * 3. User authorizes in Google
 * 4. Backend handles callback, redirects to /settings?gcal=success
 * 5. Component polls status while popup open
 * 6. Shows success toast when connected
 */

import { ref, onMounted, computed } from 'vue'
import { useGoogleCalendarIntegration } from '@/composables/useGoogleCalendarIntegration'
import { useToast } from '@/composables/useToast'
import { useI18n } from '@/composables/useI18n'
import ToggleSwitch from '@/components/common/ToggleSwitch.vue'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'

const { t } = useI18n()

// State
const isWarningExpanded = ref(false)
const isConnecting = ref(false)
const showDisconnectModal = ref(false)

// Composables
const {
  isConnected,
  settings,
  lastSyncTime,
  isLoading,
  connect,
  disconnect,
  updateSettings,
  fetchStatus,
} = useGoogleCalendarIntegration()

const { showSuccess, showError } = useToast()

// Computed
const formattedLastSync = computed(() => {
  if (!lastSyncTime.value) return null

  const date = new Date(lastSyncTime.value)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  // Relative time
  if (diffMins < 1) return t('settings.googleCalendar.timeAgo.justNow')
  if (diffMins < 60)
    return t('settings.googleCalendar.timeAgo.minutesAgo', diffMins, { count: diffMins })
  if (diffHours < 24)
    return t('settings.googleCalendar.timeAgo.hoursAgo', diffHours, { count: diffHours })
  if (diffDays < 7)
    return t('settings.googleCalendar.timeAgo.daysAgo', diffDays, { count: diffDays })

  // Absolute date for older syncs
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  })
})

// Methods
function toggleWarning() {
  isWarningExpanded.value = !isWarningExpanded.value
}

async function handleConnect() {
  isConnecting.value = true

  try {
    // Get OAuth URL from backend
    const authUrl = await connect()

    // Open popup window
    const popup = window.open(
      authUrl,
      'GoogleCalendarAuth',
      'width=600,height=700,left=100,top=100,menubar=no,toolbar=no,location=no,status=no'
    )

    if (!popup) {
      showError(t('settings.googleCalendar.toasts.popupBlocked'))
      isConnecting.value = false
      return
    }

    // Poll for connection status while popup is open
    const pollInterval = setInterval(async () => {
      // Check if popup was closed
      if (popup.closed) {
        clearInterval(pollInterval)
        isConnecting.value = false

        // Fetch status to check if connection succeeded
        await fetchStatus()

        if (isConnected.value) {
          showSuccess(t('settings.googleCalendar.toasts.connectionSuccess'))
        } else {
          // User closed popup without completing auth (neutral message)
          showError(t('settings.googleCalendar.toasts.authCancelled'))
        }
      }
    }, 2000) // Poll every 2 seconds
  } catch (err) {
    console.error('[GoogleCalendar] OAuth error:', err)
    showError(t('settings.googleCalendar.toasts.connectionError'))
    isConnecting.value = false
  }
}

async function handleDisconnect() {
  try {
    await disconnect()
    showDisconnectModal.value = false
    showSuccess(t('settings.googleCalendar.toasts.disconnectSuccess'))
  } catch (err) {
    console.error('[GoogleCalendar] Disconnect error:', err)
    showError(t('settings.googleCalendar.toasts.disconnectError'))
  }
}

async function handleToggleAutoSync(enabled: boolean) {
  try {
    await updateSettings({ auto_sync_enabled: enabled })
    showSuccess(
      enabled
        ? t('settings.googleCalendar.toasts.autoSyncEnabled')
        : t('settings.googleCalendar.toasts.autoSyncPaused')
    )
  } catch (err) {
    console.error('[GoogleCalendar] Settings update error:', err)
    showError(t('settings.googleCalendar.toasts.settingsUpdateError'))
  }
}

async function handleToggleBaa(enabled: boolean) {
  try {
    await updateSettings({ has_google_baa: enabled })
    showSuccess(
      enabled
        ? t('settings.googleCalendar.toasts.baaConfirmationSaved')
        : t('settings.googleCalendar.toasts.baaConfirmationRemoved')
    )
  } catch (err: unknown) {
    console.error('[GoogleCalendar] Failed to update BAA status:', err)
    showError(t('settings.googleCalendar.toasts.baaUpdateError'))
  }
}

async function handleToggleNotifyClients(enabled: boolean) {
  try {
    await updateSettings({ notify_clients: enabled })
    showSuccess(
      enabled
        ? t('settings.googleCalendar.toasts.clientInvitationsEnabled')
        : t('settings.googleCalendar.toasts.clientInvitationsDisabled')
    )
  } catch (err: unknown) {
    console.error('[GoogleCalendar] Failed to update client invitations:', err)
    // Check if error is due to missing BAA
    if (
      err &&
      typeof err === 'object' &&
      'response' in err &&
      err.response &&
      typeof err.response === 'object' &&
      'status' in err.response &&
      err.response.status === 400 &&
      'data' in err.response &&
      err.response.data &&
      typeof err.response.data === 'object' &&
      'detail' in err.response.data &&
      typeof err.response.data.detail === 'string' &&
      err.response.data.detail.includes('BAA')
    ) {
      showError(t('settings.googleCalendar.toasts.clientInvitationsBaaRequired'))
    } else {
      showError(t('settings.googleCalendar.toasts.clientInvitationsUpdateError'))
    }
  }
}

// Lifecycle
onMounted(async () => {
  await fetchStatus()
})
</script>

<template>
  <div>
    <!-- Loading State -->
    <div
      v-if="isLoading && !isConnected"
      class="flex items-center justify-center py-12"
    >
      <LoadingSpinner />
    </div>

    <!-- NOT CONNECTED STATE -->
    <div
      v-else-if="!isConnected"
      class="max-w-2xl rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
    >
      <!-- Header -->
      <div class="flex items-start gap-4">
        <!-- Calendar Icon -->
        <div class="flex-shrink-0">
          <svg
            class="h-8 w-8 text-blue-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
            />
          </svg>
        </div>

        <div class="flex-1">
          <h2 class="text-lg font-semibold text-slate-900">
            {{ t('settings.googleCalendar.notConnected.title') }}
          </h2>
          <p class="mt-1 text-sm text-slate-600">
            {{ t('settings.googleCalendar.notConnected.description') }}
          </p>
        </div>
      </div>

      <!-- HIPAA Warning (Collapsible) -->
      <div class="mt-6 rounded-md border border-amber-200 bg-amber-50">
        <button
          type="button"
          class="flex w-full items-center justify-between gap-3 p-4 text-left focus:ring-2 focus:ring-amber-500 focus:ring-offset-2 focus:outline-none"
          :aria-expanded="isWarningExpanded"
          @click="toggleWarning"
        >
          <div class="flex items-start gap-3">
            <svg
              class="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-600"
              fill="currentColor"
              viewBox="0 0 20 20"
              aria-hidden="true"
            >
              <path
                fill-rule="evenodd"
                d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                clip-rule="evenodd"
              />
            </svg>
            <span class="text-sm font-medium text-amber-900">
              {{ t('settings.googleCalendar.notConnected.hipaaWarningTitle') }}
            </span>
          </div>
          <svg
            class="h-5 w-5 flex-shrink-0 text-amber-600 transition-transform"
            :class="{ 'rotate-180': isWarningExpanded }"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </button>

        <Transition
          enter-active-class="transition-all duration-200 ease-out"
          enter-from-class="opacity-0 max-h-0"
          enter-to-class="opacity-100 max-h-96"
          leave-active-class="transition-all duration-200 ease-in"
          leave-from-class="opacity-100 max-h-96"
          leave-to-class="opacity-0 max-h-0"
        >
          <div v-if="isWarningExpanded" class="overflow-hidden px-4 pb-4">
            <div class="space-y-3 text-sm text-amber-900">
              <p>
                {{ t('settings.googleCalendar.notConnected.hipaaWarningIntro') }}
              </p>
              <ul class="list-inside list-disc space-y-2 pl-2">
                <li>
                  {{ t('settings.googleCalendar.notConnected.hipaaPoint1') }}
                </li>
                <li>
                  {{ t('settings.googleCalendar.notConnected.hipaaPoint2') }}
                </li>
                <li>
                  {{ t('settings.googleCalendar.notConnected.hipaaPoint3') }}
                </li>
                <li>
                  {{ t('settings.googleCalendar.notConnected.hipaaPoint4') }}
                </li>
              </ul>
              <p class="text-xs text-amber-800">
                {{ t('settings.googleCalendar.notConnected.hipaaRecommendation') }}
              </p>
            </div>
          </div>
        </Transition>
      </div>

      <!-- Connect Button -->
      <div class="mt-6">
        <button
          type="button"
          :disabled="isConnecting"
          class="flex w-full items-center justify-center gap-2 rounded-md bg-blue-600 px-6 py-3 text-sm font-medium text-white transition-colors hover:bg-blue-700 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
          @click="handleConnect"
        >
          <svg
            v-if="!isConnecting"
            class="h-5 w-5"
            fill="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
            />
            <path
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
            />
            <path
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          <LoadingSpinner v-else class="h-5 w-5" />
          <span>{{
            isConnecting
              ? t('settings.googleCalendar.notConnected.connecting')
              : t('settings.googleCalendar.notConnected.connectButton')
          }}</span>
        </button>
      </div>
    </div>

    <!-- CONNECTED STATE -->
    <div v-else class="max-w-2xl space-y-6">
      <!-- Success Banner -->
      <div class="rounded-lg border border-green-200 bg-green-50 p-4">
        <div class="flex items-start gap-3">
          <svg
            class="h-6 w-6 flex-shrink-0 text-green-600"
            fill="currentColor"
            viewBox="0 0 20 20"
            aria-hidden="true"
          >
            <path
              fill-rule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
              clip-rule="evenodd"
            />
          </svg>
          <div class="flex-1">
            <h3 class="text-sm font-semibold text-green-900">
              {{ t('settings.googleCalendar.connected.successTitle') }}
            </h3>
            <p v-if="formattedLastSync" class="mt-1 text-xs text-green-700">
              {{ t('settings.googleCalendar.connected.lastSynced', { time: formattedLastSync }) }}
            </p>
          </div>
        </div>
      </div>

      <!-- Settings Card -->
      <div class="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <h3 class="text-base font-semibold text-slate-900">
          {{ t('settings.googleCalendar.connected.settingsTitle') }}
        </h3>

        <div class="mt-6 space-y-6">
          <!-- Auto Sync Toggle -->
          <div class="flex items-start justify-between gap-4">
            <div class="flex-1">
              <label class="text-sm font-medium text-slate-900">
                {{ t('settings.googleCalendar.connected.autoSyncLabel') }}
              </label>
              <p class="mt-1 text-sm text-slate-600">
                {{ t('settings.googleCalendar.connected.autoSyncDescription') }}
              </p>
            </div>
            <div class="flex-shrink-0">
              <ToggleSwitch
                :model-value="settings.auto_sync_enabled"
                :label="t('settings.googleCalendar.connected.autoSyncToggleLabel')"
                @update:model-value="handleToggleAutoSync"
              />
            </div>
          </div>

          <!-- Google Workspace BAA Confirmation -->
          <div class="border-t border-slate-200 pt-6">
            <div class="flex items-start gap-3">
              <input
                id="has-google-baa"
                :checked="settings.has_google_baa"
                type="checkbox"
                class="mt-1 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                @change="handleToggleBaa(($event.target as HTMLInputElement).checked)"
              />
              <div class="flex-1">
                <label for="has-google-baa" class="text-sm font-medium text-slate-900">
                  {{ t('settings.googleCalendar.connected.baaCheckboxLabel') }}
                </label>
                <p class="mt-1 text-sm text-slate-600">
                  {{
                    t('settings.googleCalendar.connected.baaCheckboxDescription', {
                      link: '',
                    })
                  }}
                  <a
                    href="https://support.google.com/a/answer/3407054"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="text-blue-600 underline hover:text-blue-700"
                  >
                    {{ t('settings.googleCalendar.connected.baaLinkText') }}
                  </a>
                </p>
              </div>
            </div>
          </div>

          <!-- Client Notifications Toggle -->
          <div class="border-t border-slate-200 pt-6">
            <div class="flex items-start justify-between gap-4">
              <div class="flex-1">
                <label class="text-sm font-medium text-slate-900">
                  {{ t('settings.googleCalendar.connected.clientNotificationsLabel') }}
                </label>
                <p class="mt-1 text-sm text-slate-600">
                  {{ t('settings.googleCalendar.connected.clientNotificationsDescription') }}
                </p>
                <p
                  v-if="!settings.has_google_baa"
                  class="mt-2 text-xs font-medium text-amber-700"
                >
                  {{ t('settings.googleCalendar.connected.clientNotificationsBaaWarning') }}
                </p>
              </div>
              <div class="flex-shrink-0">
                <ToggleSwitch
                  :model-value="settings.notify_clients"
                  :disabled="!settings.auto_sync_enabled || !settings.has_google_baa"
                  @update:model-value="handleToggleNotifyClients"
                />
              </div>
            </div>

            <!-- Privacy Notice (conditional, with transition) -->
            <Transition
              enter-active-class="transition-all duration-300 ease-out"
              enter-from-class="opacity-0 max-h-0"
              enter-to-class="opacity-100 max-h-32"
              leave-active-class="transition-all duration-200 ease-in"
              leave-from-class="opacity-100 max-h-32"
              leave-to-class="opacity-0 max-h-0"
            >
              <div
                v-if="settings.notify_clients"
                role="status"
                aria-live="polite"
                class="mt-4 overflow-hidden rounded-md border-l-2 border-amber-400 bg-amber-50/50 p-4"
              >
                <div class="flex items-start gap-3">
                  <svg
                    class="mt-0.5 h-5 w-5 flex-shrink-0 text-amber-600"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                    aria-hidden="true"
                  >
                    <path
                      fill-rule="evenodd"
                      d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z"
                      clip-rule="evenodd"
                    />
                  </svg>
                  <div class="flex-1">
                    <p class="text-xs font-medium text-slate-900">
                      {{ t('settings.googleCalendar.connected.privacyNoticeTitle') }}
                    </p>
                    <p class="mt-1 text-xs text-slate-700">
                      {{ t('settings.googleCalendar.connected.privacyNoticeDescription') }}
                    </p>
                  </div>
                </div>
              </div>
            </Transition>
          </div>

          <!-- Include Client Names (Future Feature) -->
          <!-- TODO: Uncomment when backend implements this setting -->
          <!--
          <div class="border-t border-slate-200 pt-6">
            <div class="flex items-start gap-3">
              <input
                id="include-names"
                v-model="settings.include_client_names"
                type="checkbox"
                class="mt-1 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
                @change="handleToggleIncludeNames"
              />
              <div class="flex-1">
                <label for="include-names" class="flex items-center gap-2 text-sm font-medium text-slate-900">
                  Include client names in calendar events
                  <button
                    type="button"
                    class="text-slate-400 hover:text-slate-600 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 rounded"
                    title="This will add client names to calendar event titles. Not HIPAA-compliant."
                  >
                    <svg class="h-4 w-4" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
                      <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd" />
                    </svg>
                  </button>
                </label>
                <p class="mt-1 text-sm text-slate-600">
                  <strong class="text-amber-700">Warning:</strong> This will expose PHI on a non-HIPAA compliant service.
                </p>
              </div>
            </div>
          </div>
          -->
        </div>
      </div>

      <!-- Disconnect Button -->
      <div class="flex justify-end">
        <button
          type="button"
          class="rounded-md border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-700 transition-colors hover:bg-red-50 focus:ring-2 focus:ring-red-500 focus:ring-offset-2 focus:outline-none"
          @click="showDisconnectModal = true"
        >
          {{ t('settings.googleCalendar.connected.disconnectButton') }}
        </button>
      </div>
    </div>

    <!-- Disconnect Confirmation Modal -->
    <Teleport to="body">
      <Transition name="modal-backdrop">
        <div
          v-if="showDisconnectModal"
          class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="disconnect-modal-title"
          aria-describedby="disconnect-modal-description"
          @click.self="showDisconnectModal = false"
          @keydown.esc="showDisconnectModal = false"
        >
          <Transition name="modal-content">
            <div
              v-if="showDisconnectModal"
              class="mx-4 w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl"
              role="alertdialog"
              tabindex="-1"
            >
              <!-- Warning Icon and Title -->
              <div class="mb-4 flex items-start">
                <svg
                  class="mt-0.5 mr-3 h-6 w-6 flex-shrink-0 text-amber-500"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                  aria-hidden="true"
                >
                  <path
                    fill-rule="evenodd"
                    d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z"
                    clip-rule="evenodd"
                  />
                </svg>
                <div class="flex-1">
                  <h3
                    id="disconnect-modal-title"
                    class="text-lg font-semibold text-slate-900"
                  >
                    {{ t('settings.googleCalendar.disconnectModal.title') }}
                  </h3>
                </div>
              </div>

              <!-- Description -->
              <div id="disconnect-modal-description" class="mb-6 text-slate-700">
                <p class="mb-3">
                  {{ t('settings.googleCalendar.disconnectModal.description') }}
                </p>
                <p class="text-sm text-slate-600">
                  {{ t('settings.googleCalendar.disconnectModal.existingEventsNote') }}
                </p>
              </div>

              <!-- Action Buttons -->
              <div class="flex gap-3">
                <button
                  type="button"
                  class="flex-1 rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 focus:outline-none"
                  @click="showDisconnectModal = false"
                >
                  {{ t('settings.googleCalendar.disconnectModal.cancelButton') }}
                </button>
                <button
                  type="button"
                  :disabled="isLoading"
                  class="flex-1 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-700 focus:ring-2 focus:ring-red-500 focus:ring-offset-2 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
                  @click="handleDisconnect"
                >
                  <span v-if="!isLoading">{{
                    t('settings.googleCalendar.disconnectModal.disconnectButton')
                  }}</span>
                  <LoadingSpinner v-else class="mx-auto h-4 w-4" />
                </button>
              </div>
            </div>
          </Transition>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<style scoped>
/* Modal transitions */
.modal-backdrop-enter-active,
.modal-backdrop-leave-active {
  transition: opacity 0.2s ease;
}

.modal-backdrop-enter-from,
.modal-backdrop-leave-to {
  opacity: 0;
}

.modal-content-enter-active,
.modal-content-leave-active {
  transition: all 0.3s ease;
}

.modal-content-enter-from {
  opacity: 0;
  transform: scale(0.95);
}

.modal-content-leave-to {
  opacity: 0;
  transform: scale(0.95);
}

/* Warning accordion transition helpers */
.max-h-0 {
  max-height: 0;
}

.max-h-32 {
  max-height: 8rem;
}

.max-h-96 {
  max-height: 24rem;
}
</style>
