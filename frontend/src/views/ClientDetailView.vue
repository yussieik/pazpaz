<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useClientsStore } from '@/stores/clients'
import { useAppointmentsStore } from '@/stores/appointments'
import { useScreenReader } from '@/composables/useScreenReader'
import { useToast } from '@/composables/useToast'
import { formatDate } from '@/utils/calendar/dateFormatters'
import type { AppointmentListItem, AppointmentFormData } from '@/types/calendar'
import { onKeyStroke } from '@vueuse/core'
import { format } from 'date-fns'
import AppointmentFormModal from '@/components/calendar/AppointmentFormModal.vue'
import ClientFormModal from '@/components/clients/ClientFormModal.vue'
import SessionTimeline from '@/components/client/SessionTimeline.vue'
import DeletedNotesSection from '@/components/sessions/DeletedNotesSection.vue'
import type { ClientCreate } from '@/types/client'

const route = useRoute()
const router = useRouter()
const clientsStore = useClientsStore()
const appointmentsStore = useAppointmentsStore()

// Screen reader announcements
const { announcement, announce } = useScreenReader()

// Toast notifications
const { showAppointmentSuccess, showSuccess, showError } = useToast()

// Local state
const activeTab = ref<'overview' | 'history' | 'files'>('overview')
const showEditModal = ref(false)

// Button refs for keyboard feedback
const editButtonRef = ref<HTMLButtonElement | null>(null)
const scheduleButtonRef = ref<HTMLButtonElement | null>(null)

// Component refs
const sessionTimelineRef = ref<InstanceType<typeof SessionTimeline> | null>(null)
const deletedNotesSectionRef = ref<InstanceType<typeof DeletedNotesSection> | null>(
  null
)

// State for badge pulse trigger
const triggerBadgePulse = ref(false)

// Modal state for scheduling appointments
const showScheduleModal = ref(false)

// Appointment context from navigation state (H1: Contextual Banner)
// Try multiple sources for reliable state passing across different scenarios
const getAppointmentFromState = (): AppointmentListItem | null => {
  // Priority 1: Check history.state (works in browser)
  if (history.state?.appointment) {
    return history.state.appointment as AppointmentListItem
  }

  // Priority 2: Check router state (works in tests)
  // TypeScript safe access to state property
  const routerState = (
    router.currentRoute.value as unknown as {
      state?: { appointment?: AppointmentListItem }
    }
  ).state
  if (routerState?.appointment) {
    return routerState.appointment
  }

  // Priority 3: Check sessionStorage with SHORT timeout (30 seconds only)
  // This is ONLY for direct navigation from appointment modal -> client profile
  // After 30 seconds, the context expires and banner won't show
  const contextStr = sessionStorage.getItem('navigationContext')
  if (contextStr) {
    try {
      const context = JSON.parse(contextStr)
      // Short timeout: 30 seconds (30000ms)
      // This ensures if user navigates away and comes back, banner doesn't persist
      if (context.type === 'appointment' && Date.now() - context.timestamp < 30000) {
        // Clear immediately on read to prevent showing on subsequent navigations
        sessionStorage.removeItem('navigationContext')
        return context.appointment as AppointmentListItem
      } else {
        // Expired - clear it
        sessionStorage.removeItem('navigationContext')
      }
    } catch {
      // Invalid JSON in sessionStorage - clear it
      sessionStorage.removeItem('navigationContext')
    }
  }

  return null
}

const sourceAppointment = ref<AppointmentListItem | null>(null)

// Watch for route changes to pick up appointment state
// Run immediately to capture state on component mount
watch(
  () => (router.currentRoute.value as unknown as { state?: unknown }).state,
  () => {
    const appointment = getAppointmentFromState()
    // Only update if we found an appointment (don't clear existing value)
    if (appointment) {
      sourceAppointment.value = appointment
    }
  },
  { immediate: true, deep: true }
)

// Also check in onMounted (timing issue - history.state might not be ready immediately)
onMounted(() => {
  // Try to get appointment from state
  const appointment = getAppointmentFromState()
  if (appointment) {
    sourceAppointment.value = appointment
  } else {
    // Clear sessionStorage if we're navigating directly (not from appointment)
    // This prevents stale "Viewing from appointment" banner
    sessionStorage.removeItem('navigationContext')
  }

  // Focus the back button when coming from appointment modal (P0-1: Focus Management)
  if (sourceAppointment.value) {
    nextTick(() => {
      const backButton = document.querySelector(
        '[data-focus-target="back-button"]'
      ) as HTMLElement
      backButton?.focus()
    })
  }

  // Handle tab query parameter (e.g., from SessionView back navigation)
  const tabParam = route.query.tab as string | undefined
  if (tabParam && ['overview', 'history', 'files'].includes(tabParam)) {
    activeTab.value = tabParam as 'overview' | 'history' | 'files'
  }

  // Fetch client data
  clientsStore.fetchClient(clientId.value)

  // Register keyboard shortcuts listener
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

const clientId = computed(() => route.params.id as string)
const client = computed(() => clientsStore.currentClient)

// H6: Smart back navigation
const backDestination = computed(() => {
  // Priority 1: Check if we have appointment context in history.state
  if (sourceAppointment.value) {
    return {
      label: 'Back to Appointment',
      action: () =>
        router.push({
          path: '/',
          query: { appointment: sourceAppointment.value!.id },
        }),
    }
  }

  // Priority 2: Check if we came from clients list (using router meta)
  const previousRoute = route.meta.from as string | undefined

  if (previousRoute === '/clients') {
    return {
      label: 'Back to Clients',
      action: () => router.push('/clients'),
    }
  }

  // Priority 3: Default to calendar (therapist's main view)
  return {
    label: 'Back to Calendar',
    action: () => router.push('/'),
  }
})

/**
 * Helper function to check if user is typing in an input field
 * Prevents keyboard shortcuts from triggering while user is typing
 */
function isTypingInInput(e: KeyboardEvent): boolean {
  const target = e.target as HTMLElement
  return (
    target.tagName === 'INPUT' ||
    target.tagName === 'TEXTAREA' ||
    target.isContentEditable
  )
}

/**
 * Triggers visual feedback by briefly focusing the button
 * Same pattern as calendar view keyboard shortcuts
 */
function triggerButtonFeedback(button: HTMLButtonElement | null) {
  if (!button) return
  button.focus()
  setTimeout(() => button.blur(), 150)
}

/**
 * Handle session note restoration
 * Refreshes the session timeline when a note is restored from deleted section
 */
async function handleSessionRestored() {
  // Refresh the session timeline to show the restored session
  if (sessionTimelineRef.value) {
    await sessionTimelineRef.value.refresh()
  } else {
    console.warn('[ClientDetailView] sessionTimelineRef is null, cannot refresh')
  }
}

/**
 * Handle session deletion from timeline
 * Refreshes the deleted notes section to show newly deleted note
 */
async function handleSessionDeleted() {
  // Refresh deleted notes section if it has a refresh method
  if (deletedNotesSectionRef.value) {
    // The DeletedNotesSection will auto-refresh on mount
    // or we can force a re-fetch if needed
  }
}

/**
 * Handle badge pulse trigger when session deleted and section collapsed
 */
function handleBadgePulse() {
  // Trigger pulse animation
  triggerBadgePulse.value = true
  // Reset after animation completes
  setTimeout(() => {
    triggerBadgePulse.value = false
  }, 600)
}

/**
 * Keyboard shortcuts handler for Client Detail page
 * Implements P0 shortcuts: Tab switching (1-4), Edit (e), Schedule (s)
 */
function handleKeydown(e: KeyboardEvent) {
  // Don't trigger shortcuts when typing in input fields
  if (isTypingInInput(e)) return

  // Only process shortcuts when client data is loaded
  if (!client.value) return

  // Tab switching (1-3)
  if (['1', '2', '3'].includes(e.key)) {
    e.preventDefault()
    const tabMap: Record<string, 'overview' | 'history' | 'files'> = {
      '1': 'overview',
      '2': 'history',
      '3': 'files',
    }
    const tabLabels: Record<string, string> = {
      '1': 'Overview',
      '2': 'History',
      '3': 'Files',
    }
    const newTab = tabMap[e.key]
    if (newTab) {
      activeTab.value = newTab
      announce(`${tabLabels[e.key]} tab selected`)
    }
    return
  }

  // Edit client (e)
  if (e.key === 'e') {
    e.preventDefault()
    editClient()
    triggerButtonFeedback(editButtonRef.value)
    announce('Edit client')
    return
  }

  // Schedule appointment (s)
  if (e.key === 's') {
    e.preventDefault()
    scheduleAppointment()
    triggerButtonFeedback(scheduleButtonRef.value)
    announce('Schedule appointment')
    return
  }
}

// P1-5: Add Escape key shortcut for back navigation
onKeyStroke('Escape', (e) => {
  // Don't trigger if schedule modal is open (let modal handle Escape)
  if (showScheduleModal.value) return

  // Only trigger if not typing in input field
  const target = e.target as HTMLElement
  if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return

  e.preventDefault()
  backDestination.value.action()
})

function dismissBanner() {
  sourceAppointment.value = null
}

function editClient() {
  if (!client.value) return
  showEditModal.value = true
  announce(`Edit ${client.value.first_name} ${client.value.last_name}`)
}

async function handleEditClient(data: ClientCreate) {
  if (!client.value) return

  // Store original client data for rollback on error
  const originalClient = { ...client.value }

  try {
    // Optimistic update: instant UI
    Object.assign(client.value, data)

    // Close modal immediately for smooth UX
    showEditModal.value = false

    // Show success toast
    showSuccess(`${data.first_name} ${data.last_name} updated successfully`)
    announce('Client information updated')

    // Background API call
    await clientsStore.updateClient(clientId.value, data)

    // Silent background sync to ensure consistency
    await clientsStore.fetchClient(clientId.value)
  } catch (error) {
    console.error('Failed to update client:', error)

    // Rollback on error
    if (client.value) {
      Object.assign(client.value, originalClient)
    }

    // Show error and re-open modal
    showEditModal.value = true
    showError('Failed to update client. Please try again.')
    announce('Failed to update client. Please try again.')
  }
}

function scheduleAppointment() {
  if (!client.value) return

  // Open modal with client pre-filled
  showScheduleModal.value = true

  // Screen reader announcement
  announce(
    `Schedule appointment for ${client.value.first_name} ${client.value.last_name}`
  )
}

async function handleScheduleAppointment(data: AppointmentFormData) {
  try {
    // Create appointment via store
    const newAppt = await appointmentsStore.createAppointment({
      client_id: data.client_id,
      scheduled_start: new Date(data.scheduled_start).toISOString(),
      scheduled_end: new Date(data.scheduled_end).toISOString(),
      location_type: data.location_type,
      location_details: data.location_details || null,
      notes: data.notes || null,
    })

    // Close modal
    showScheduleModal.value = false

    // Show success toast with rich content
    showAppointmentSuccess('Appointment scheduled', {
      datetime: format(new Date(newAppt.scheduled_start), "MMM d 'at' h:mm a"),
      actions: [
        {
          label: 'View in Calendar',
          onClick: () => {
            router.push({
              path: '/',
              query: { appointment: newAppt.id },
            })
          },
        },
      ],
    })

    // Screen reader announcement
    announce('Appointment scheduled successfully')

    // Refresh client data to update appointment count in History tab
    await clientsStore.fetchClient(clientId.value)
  } catch (error) {
    console.error('Failed to schedule appointment:', error)
    // Keep modal open on error so user can retry
    // Modal will handle error display
    announce('Failed to schedule appointment. Please try again.')
  }
}
</script>

<template>
  <div class="container mx-auto px-5 py-6 sm:px-4 sm:py-8">
    <!-- Screen Reader Announcements -->
    <div role="status" aria-live="polite" aria-atomic="true" class="sr-only">
      {{ announcement }}
    </div>

    <!-- Back Button (H6: Smart Navigation + P1-5: Escape Key Hint) -->
    <button
      @click="backDestination.action"
      data-focus-target="back-button"
      class="group mb-4 -ml-2 inline-flex min-h-[44px] items-center gap-2 px-2 text-sm font-medium text-slate-600 transition-colors hover:text-slate-900 sm:ml-0 sm:min-h-0 sm:px-0"
    >
      <svg
        class="h-5 w-5 flex-shrink-0 sm:h-4 sm:w-4"
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
      <span>{{ backDestination.label }}</span>
      <kbd
        class="ml-2 hidden rounded border border-slate-300 bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-500 opacity-0 transition-opacity group-hover:opacity-100 sm:inline"
      >
        Esc
      </kbd>
    </button>

    <!-- Enhanced Appointment Context Banner -->
    <div
      v-if="sourceAppointment"
      class="mb-6 rounded-lg border-l-4 border-blue-500 bg-blue-50 p-4 shadow-sm"
    >
      <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div class="flex items-center gap-3">
          <!-- Icon -->
          <div
            class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-blue-600 sm:h-10 sm:w-10"
          >
            <svg
              class="h-4 w-4 text-white sm:h-6 sm:w-6"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
          </div>

          <!-- Content -->
          <div class="min-w-0 flex-1">
            <p class="text-sm font-semibold text-blue-900">Viewing from appointment</p>
            <p class="truncate text-xs text-blue-700 sm:text-sm">
              {{ formatDate(sourceAppointment.scheduled_start, "MMM d 'at' h:mm a") }}
              •
              {{
                sourceAppointment.location_type === 'clinic'
                  ? 'Clinic'
                  : sourceAppointment.location_type === 'home'
                    ? 'Home Visit'
                    : 'Telehealth'
              }}
            </p>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex w-full items-center gap-2 sm:w-auto">
          <button
            @click="backDestination.action()"
            class="inline-flex min-h-[44px] flex-1 items-center justify-center gap-2 rounded-lg border border-blue-300 bg-white px-3 py-2.5 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-50 sm:flex-none"
          >
            <svg
              class="h-4 w-4 flex-shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M10 19l-7-7m0 0l7-7m-7 7h18"
              />
            </svg>
            <span class="hidden sm:inline">Back to Appointment</span>
            <span class="inline sm:hidden">Back</span>
            <kbd
              class="ml-1 hidden rounded bg-blue-100 px-1.5 py-0.5 font-mono text-xs text-blue-700 sm:inline"
            >
              Esc
            </kbd>
          </button>
          <button
            @click="dismissBanner"
            class="min-h-[44px] min-w-[44px] rounded-lg p-2.5 text-blue-400 transition-colors hover:bg-blue-100 hover:text-blue-600"
            aria-label="Dismiss banner"
          >
            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="clientsStore.loading" class="flex items-center justify-center py-12">
      <div class="text-center">
        <div
          class="inline-block h-10 w-10 animate-spin rounded-full border-4 border-solid border-emerald-600 border-r-transparent sm:h-8 sm:w-8"
        ></div>
        <p class="mt-4 text-sm text-slate-600">Loading client...</p>
      </div>
    </div>

    <!-- Error State -->
    <div
      v-else-if="clientsStore.error"
      class="rounded-lg border border-red-200 bg-red-50 p-4 text-red-800"
    >
      <p class="font-semibold">Error loading client</p>
      <p class="mt-1 text-sm">{{ clientsStore.error }}</p>
    </div>

    <!-- Client Profile -->
    <div v-else-if="client">
      <!-- P0-3: Emergency Contact Card (Safety Critical) -->
      <div
        v-if="
          client && (client.emergency_contact_name || client.emergency_contact_phone)
        "
        class="mb-4 rounded-lg border-2 border-red-300 bg-red-50 p-4"
        role="region"
        aria-label="Emergency contact information"
        id="emergency-contact-card"
      >
        <div class="flex items-start gap-3">
          <div
            class="flex h-10 w-10 items-center justify-center rounded-full bg-red-600"
          >
            <svg
              class="h-6 w-6 text-white"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"
              />
            </svg>
          </div>
          <div class="flex-1">
            <p class="text-sm font-semibold tracking-wide text-red-800 uppercase">
              Emergency Contact
            </p>
            <p class="mt-1 text-lg font-semibold text-red-900">
              {{ client.emergency_contact_name }}
            </p>
            <a
              v-if="client.emergency_contact_phone"
              :href="`tel:${client.emergency_contact_phone}`"
              class="mt-1 inline-flex min-h-[44px] items-center gap-2 text-base font-bold text-red-700 hover:text-red-800 focus:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2 sm:text-lg"
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
                  d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"
                />
              </svg>
              <span class="break-all sm:break-normal">{{
                client.emergency_contact_phone
              }}</span>
            </a>
          </div>
        </div>
      </div>

      <!-- Hero Header -->
      <header class="mb-6 rounded-lg border border-slate-200 bg-white p-6">
        <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <!-- Client Info -->
          <div class="flex items-start gap-4">
            <div
              class="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-emerald-100 text-xl font-semibold text-emerald-700 sm:h-16 sm:w-16 sm:text-2xl"
            >
              {{ client.first_name[0] }}{{ client.last_name[0] }}
            </div>
            <div class="min-w-0 flex-1">
              <h1 class="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
                {{ client.full_name }}
              </h1>
              <div class="mt-1 space-y-0.5 text-sm text-slate-600">
                <p v-if="client.email" class="truncate">{{ client.email }}</p>
                <p v-if="client.phone">{{ client.phone }}</p>
              </div>
            </div>
          </div>

          <!-- Action Buttons -->
          <div class="flex w-full gap-2 sm:w-auto">
            <button
              ref="editButtonRef"
              @click="editClient"
              class="group relative inline-flex min-h-[44px] flex-1 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition-all hover:bg-slate-50 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 focus:outline-none sm:flex-none"
            >
              Edit
              <kbd
                class="ml-1 hidden rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-500 opacity-0 transition-opacity group-hover:opacity-100 sm:inline"
              >
                e
              </kbd>
            </button>
            <button
              ref="scheduleButtonRef"
              @click="scheduleAppointment"
              class="group relative inline-flex min-h-[44px] flex-1 items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white transition-all hover:bg-emerald-700 focus:ring-2 focus:ring-emerald-500/20 focus:outline-none sm:flex-none"
            >
              <svg
                class="h-4 w-4 flex-shrink-0"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
                />
              </svg>
              Schedule
              <kbd
                class="ml-1 hidden rounded bg-emerald-700 px-1.5 py-0.5 font-mono text-xs text-emerald-100 opacity-0 transition-opacity group-hover:opacity-100 sm:inline"
              >
                s
              </kbd>
            </button>
          </div>
        </div>
      </header>

      <!-- Tabs -->
      <div class="mb-6 border-b border-slate-200">
        <nav class="flex space-x-4 sm:space-x-8" aria-label="Tabs">
          <button
            @click="activeTab = 'overview'"
            :class="[
              'border-b-2 px-3 py-4 text-sm font-medium transition-colors sm:px-1',
              activeTab === 'overview'
                ? 'border-emerald-600 text-emerald-600'
                : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700',
            ]"
          >
            <span class="flex items-center gap-1.5">
              Overview
              <kbd
                :class="[
                  'hidden font-mono text-xs sm:inline',
                  activeTab === 'overview'
                    ? 'rounded bg-emerald-100 px-1.5 py-0.5 text-emerald-700'
                    : 'rounded bg-slate-100 px-1.5 py-0.5 text-slate-500',
                ]"
              >
                1
              </kbd>
            </span>
          </button>
          <button
            @click="activeTab = 'history'"
            :class="[
              'border-b-2 px-3 py-4 text-sm font-medium transition-colors sm:px-1',
              activeTab === 'history'
                ? 'border-emerald-600 text-emerald-600'
                : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700',
            ]"
          >
            <span class="flex items-center gap-1.5">
              History
              <kbd
                :class="[
                  'hidden font-mono text-xs sm:inline',
                  activeTab === 'history'
                    ? 'rounded bg-emerald-100 px-1.5 py-0.5 text-emerald-700'
                    : 'rounded bg-slate-100 px-1.5 py-0.5 text-slate-500',
                ]"
              >
                2
              </kbd>
            </span>
          </button>
          <button
            @click="activeTab = 'files'"
            :class="[
              'border-b-2 px-3 py-4 text-sm font-medium transition-colors sm:px-1',
              activeTab === 'files'
                ? 'border-emerald-600 text-emerald-600'
                : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700',
            ]"
          >
            <span class="flex items-center gap-1.5">
              Files
              <kbd
                :class="[
                  'hidden font-mono text-xs sm:inline',
                  activeTab === 'files'
                    ? 'rounded bg-emerald-100 px-1.5 py-0.5 text-emerald-700'
                    : 'rounded bg-slate-100 px-1.5 py-0.5 text-slate-500',
                ]"
              >
                3
              </kbd>
            </span>
          </button>
        </nav>
      </div>

      <!-- Tab Content -->
      <div class="rounded-lg border border-slate-200 bg-white p-6">
        <!-- Overview Tab -->
        <div v-if="activeTab === 'overview'">
          <h2 class="mb-4 text-lg font-semibold text-slate-900">Client Information</h2>
          <dl class="grid grid-cols-1 gap-6 sm:grid-cols-2 sm:gap-4">
            <div class="border-b border-slate-100 pb-4 sm:border-b-0 sm:pb-0">
              <dt class="text-sm font-medium text-slate-500">Date of Birth</dt>
              <dd class="mt-1.5 text-base text-slate-900 sm:text-sm">
                {{
                  client.date_of_birth
                    ? new Date(client.date_of_birth).toLocaleDateString()
                    : 'Not provided'
                }}
              </dd>
            </div>
            <div class="border-b border-slate-100 pb-4 sm:border-b-0 sm:pb-0">
              <dt class="text-sm font-medium text-slate-500">Address</dt>
              <dd class="mt-1.5 text-base text-slate-900 sm:text-sm">
                {{ client.address || 'Not provided' }}
              </dd>
            </div>
            <div class="border-b border-slate-100 pb-4 sm:border-b-0 sm:pb-0">
              <dt class="text-sm font-medium text-slate-500">Emergency Contact</dt>
              <dd class="mt-1.5 text-base text-slate-900 sm:text-sm">
                {{ client.emergency_contact_name || 'Not provided' }}
                <span
                  v-if="client.emergency_contact_phone"
                  class="block text-slate-600"
                >
                  {{ client.emergency_contact_phone }}
                </span>
              </dd>
            </div>
          </dl>

          <div v-if="client.medical_history" class="mt-8 sm:mt-6">
            <h3 class="mb-2 text-sm font-semibold text-slate-700">Medical History</h3>
            <div class="rounded-lg bg-slate-50 p-4">
              <p
                class="text-base leading-relaxed whitespace-pre-wrap text-slate-900 sm:text-sm"
              >
                {{ client.medical_history }}
              </p>
            </div>
          </div>

          <div v-if="client.notes" class="mt-8 sm:mt-6">
            <h3 class="mb-2 text-sm font-semibold text-slate-700">Notes</h3>
            <div class="rounded-lg bg-slate-50 p-4">
              <p
                class="text-base leading-relaxed whitespace-pre-wrap text-slate-900 sm:text-sm"
              >
                {{ client.notes }}
              </p>
            </div>
          </div>
        </div>

        <!-- History Tab -->
        <div v-else-if="activeTab === 'history'" class="space-y-6">
          <h2 class="mb-4 text-lg font-semibold text-slate-900">Treatment History</h2>

          <!-- Session Timeline -->
          <SessionTimeline
            v-if="client"
            :client-id="client.id"
            ref="sessionTimelineRef"
            @session-deleted="handleSessionDeleted"
            @trigger-badge-pulse="handleBadgePulse"
          />

          <!-- Deleted Notes Section -->
          <DeletedNotesSection
            v-if="client"
            :client-id="client.id"
            :trigger-pulse="triggerBadgePulse"
            ref="deletedNotesSectionRef"
            @restored="handleSessionRestored"
          />
        </div>

        <!-- Files Tab -->
        <div v-else-if="activeTab === 'files'">
          <h2 class="mb-4 text-lg font-semibold text-slate-900">Files & Documents</h2>
          <p class="text-sm text-slate-600">
            Coming in M4 - Uploaded documents, consent forms, images
          </p>
        </div>
      </div>
    </div>

    <!-- Edit Client Modal -->
    <ClientFormModal
      :visible="showEditModal"
      mode="edit"
      :client="client"
      @update:visible="showEditModal = $event"
      @submit="handleEditClient"
    />

    <!-- Schedule Appointment Modal -->
    <AppointmentFormModal
      :visible="showScheduleModal"
      mode="create"
      :prefill-client-id="client?.id ?? null"
      @update:visible="showScheduleModal = $event"
      @submit="handleScheduleAppointment"
    />
  </div>
</template>

<style scoped>
/* Screen reader only class */
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border-width: 0;
}
</style>
