<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useClientsStore } from '@/stores/clients'
import { useAppointmentsStore } from '@/stores/appointments'
import { useScreenReader } from '@/composables/useScreenReader'
import { formatDate } from '@/utils/calendar/dateFormatters'
import type { AppointmentListItem, AppointmentFormData } from '@/types/calendar'
import { onKeyStroke } from '@vueuse/core'
import { format } from 'date-fns'
import AppointmentFormModal from '@/components/calendar/AppointmentFormModal.vue'
import AppointmentSuccessToast from '@/components/common/AppointmentSuccessToast.vue'

const route = useRoute()
const router = useRouter()
const clientsStore = useClientsStore()
const appointmentsStore = useAppointmentsStore()

// Screen reader announcements
const { announcement, announce } = useScreenReader()

// Local state
const activeTab = ref<'overview' | 'history' | 'plan-of-care' | 'files'>('overview')

// Button refs for keyboard feedback
const editButtonRef = ref<HTMLButtonElement | null>(null)
const scheduleButtonRef = ref<HTMLButtonElement | null>(null)

// Modal state for scheduling appointments
const showScheduleModal = ref(false)

// Success toast state
const showSuccessToast = ref(false)
const successToastData = ref({
  datetime: '',
  appointmentId: '',
})

// Success toast actions
const successToastActions = computed(() => [
  {
    label: 'View in Calendar',
    handler: () => handleViewInCalendar(successToastData.value.appointmentId),
  },
  {
    label: 'View Details',
    handler: () => handleViewDetails(successToastData.value.appointmentId),
  },
])

// Handlers for success toast actions
function handleViewInCalendar(appointmentId: string) {
  showSuccessToast.value = false
  router.push({
    path: '/',
    query: { appointment: appointmentId },
  })
}

function handleViewDetails(appointmentId: string) {
  showSuccessToast.value = false
  // For now, navigate to calendar with appointment selected
  // In the future, we could open the Details Modal directly
  handleViewInCalendar(appointmentId)
}

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
 * Keyboard shortcuts handler for Client Detail page
 * Implements P0 shortcuts: Tab switching (1-4), Edit (e), New Note (n), Schedule (s)
 */
function handleKeydown(e: KeyboardEvent) {
  // Don't trigger shortcuts when typing in input fields
  if (isTypingInInput(e)) return

  // Only process shortcuts when client data is loaded
  if (!client.value) return

  // Tab switching (1-4)
  if (['1', '2', '3', '4'].includes(e.key)) {
    e.preventDefault()
    const tabMap: Record<string, 'overview' | 'history' | 'plan-of-care' | 'files'> = {
      '1': 'overview',
      '2': 'history',
      '3': 'plan-of-care',
      '4': 'files',
    }
    const tabLabels: Record<string, string> = {
      '1': 'Overview',
      '2': 'History',
      '3': 'Plan of Care',
      '4': 'Files',
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

  // New session note (n)
  if (e.key === 'n') {
    e.preventDefault()
    newSessionNote()
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
  // TODO (M3): Open edit client modal
}

function newSessionNote() {
  // TODO (M4): Open session note creation modal
  // Placeholder for now - feature coming in M4
  announce('Session notes feature coming soon')
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

    // Show success toast
    showSuccessToast.value = true
    successToastData.value = {
      datetime: format(new Date(newAppt.scheduled_start), "MMM d 'at' h:mm a"),
      appointmentId: newAppt.id,
    }

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
  <div class="container mx-auto px-4 py-8">
    <!-- Screen Reader Announcements -->
    <div role="status" aria-live="polite" aria-atomic="true" class="sr-only">
      {{ announcement }}
    </div>

    <!-- Back Button (H6: Smart Navigation + P1-5: Escape Key Hint) -->
    <button
      @click="backDestination.action"
      data-focus-target="back-button"
      class="group mb-4 inline-flex items-center gap-2 text-sm font-medium text-slate-600 transition-colors hover:text-slate-900"
    >
      <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M15 19l-7-7 7-7"
        />
      </svg>
      <span>{{ backDestination.label }}</span>
      <kbd
        class="ml-2 rounded border border-slate-300 bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-500 opacity-0 transition-opacity group-hover:opacity-100"
      >
        Esc
      </kbd>
    </button>

    <!-- Enhanced Appointment Context Banner -->
    <div
      v-if="sourceAppointment"
      class="mb-6 rounded-lg border-l-4 border-blue-500 bg-blue-50 p-4 shadow-sm"
    >
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <!-- Icon -->
          <div
            class="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-600"
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
                d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
          </div>

          <!-- Content -->
          <div>
            <p class="text-sm font-semibold text-blue-900">Viewing from appointment</p>
            <p class="text-sm text-blue-700">
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
        <div class="flex items-center gap-2">
          <button
            @click="backDestination.action()"
            class="inline-flex items-center gap-2 rounded-lg border border-blue-300 bg-white px-3 py-2 text-sm font-medium text-blue-700 transition-colors hover:bg-blue-50"
          >
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M10 19l-7-7m0 0l7-7m-7 7h18"
              />
            </svg>
            Back to Appointment
            <kbd
              class="ml-1 rounded bg-blue-100 px-1.5 py-0.5 font-mono text-xs text-blue-700"
            >
              Esc
            </kbd>
          </button>
          <button
            @click="dismissBanner"
            class="rounded-lg p-2 text-blue-400 transition-colors hover:bg-blue-100 hover:text-blue-600"
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
          class="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-emerald-600 border-r-transparent"
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
              class="mt-1 inline-flex items-center gap-2 text-lg font-bold text-red-700 hover:text-red-800 focus:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2"
            >
              <svg
                class="h-5 w-5"
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
              {{ client.emergency_contact_phone }}
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
              class="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-2xl font-semibold text-emerald-700"
            >
              {{ client.first_name[0] }}{{ client.last_name[0] }}
            </div>
            <div class="flex-1">
              <h1 class="text-3xl font-bold tracking-tight text-slate-900">
                {{ client.full_name }}
              </h1>
              <div class="mt-1 space-y-0.5 text-sm text-slate-600">
                <p v-if="client.email">{{ client.email }}</p>
                <p v-if="client.phone">{{ client.phone }}</p>
              </div>
            </div>
          </div>

          <!-- Action Buttons -->
          <div class="flex gap-2">
            <button
              ref="editButtonRef"
              @click="editClient"
              class="group relative inline-flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition-all hover:bg-slate-50 focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 focus:outline-none"
            >
              Edit
              <kbd
                class="ml-1 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-500 opacity-0 transition-opacity group-hover:opacity-100"
              >
                e
              </kbd>
            </button>
            <button
              ref="scheduleButtonRef"
              @click="scheduleAppointment"
              class="group relative inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-all hover:bg-emerald-700 focus:ring-2 focus:ring-emerald-500/20 focus:outline-none"
            >
              <svg
                class="h-4 w-4"
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
                class="ml-1 rounded bg-emerald-700 px-1.5 py-0.5 font-mono text-xs text-emerald-100 opacity-0 transition-opacity group-hover:opacity-100"
              >
                s
              </kbd>
            </button>
          </div>
        </div>
      </header>

      <!-- Tabs -->
      <div class="mb-6 border-b border-slate-200">
        <nav class="flex space-x-8" aria-label="Tabs">
          <button
            @click="activeTab = 'overview'"
            :class="[
              'border-b-2 px-1 py-4 text-sm font-medium transition-colors',
              activeTab === 'overview'
                ? 'border-emerald-600 text-emerald-600'
                : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700',
            ]"
          >
            Overview
            <kbd
              :class="[
                'ml-1 font-mono text-xs',
                activeTab === 'overview' ? 'opacity-60' : 'opacity-40',
              ]"
            >
              1
            </kbd>
          </button>
          <button
            @click="activeTab = 'history'"
            :class="[
              'border-b-2 px-1 py-4 text-sm font-medium transition-colors',
              activeTab === 'history'
                ? 'border-emerald-600 text-emerald-600'
                : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700',
            ]"
          >
            History
            <kbd
              :class="[
                'ml-1 font-mono text-xs',
                activeTab === 'history' ? 'opacity-60' : 'opacity-40',
              ]"
            >
              2
            </kbd>
          </button>
          <button
            @click="activeTab = 'plan-of-care'"
            :class="[
              'border-b-2 px-1 py-4 text-sm font-medium transition-colors',
              activeTab === 'plan-of-care'
                ? 'border-emerald-600 text-emerald-600'
                : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700',
            ]"
          >
            Plan of Care
            <kbd
              :class="[
                'ml-1 font-mono text-xs',
                activeTab === 'plan-of-care' ? 'opacity-60' : 'opacity-40',
              ]"
            >
              3
            </kbd>
          </button>
          <button
            @click="activeTab = 'files'"
            :class="[
              'border-b-2 px-1 py-4 text-sm font-medium transition-colors',
              activeTab === 'files'
                ? 'border-emerald-600 text-emerald-600'
                : 'border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700',
            ]"
          >
            Files
            <kbd
              :class="[
                'ml-1 font-mono text-xs',
                activeTab === 'files' ? 'opacity-60' : 'opacity-40',
              ]"
            >
              4
            </kbd>
          </button>
        </nav>
      </div>

      <!-- Tab Content -->
      <div class="rounded-lg border border-slate-200 bg-white p-6">
        <!-- Overview Tab -->
        <div v-if="activeTab === 'overview'">
          <h2 class="mb-4 text-lg font-semibold text-slate-900">Client Information</h2>
          <dl class="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <dt class="text-sm font-medium text-slate-500">Date of Birth</dt>
              <dd class="mt-1 text-sm text-slate-900">
                {{
                  client.date_of_birth
                    ? new Date(client.date_of_birth).toLocaleDateString()
                    : 'Not provided'
                }}
              </dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-slate-500">Address</dt>
              <dd class="mt-1 text-sm text-slate-900">
                {{ client.address || 'Not provided' }}
              </dd>
            </div>
            <div>
              <dt class="text-sm font-medium text-slate-500">Emergency Contact</dt>
              <dd class="mt-1 text-sm text-slate-900">
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

          <div v-if="client.medical_history" class="mt-6">
            <h3 class="text-sm font-medium text-slate-500">Medical History</h3>
            <p class="mt-2 text-sm whitespace-pre-wrap text-slate-900">
              {{ client.medical_history }}
            </p>
          </div>

          <div v-if="client.notes" class="mt-6">
            <h3 class="text-sm font-medium text-slate-500">Notes</h3>
            <p class="mt-2 text-sm whitespace-pre-wrap text-slate-900">
              {{ client.notes }}
            </p>
          </div>
        </div>

        <!-- History Tab -->
        <div v-else-if="activeTab === 'history'">
          <h2 class="mb-4 text-lg font-semibold text-slate-900">Treatment History</h2>
          <p class="text-sm text-slate-600">
            Coming in M4 - Chronological timeline of appointments and sessions
          </p>
        </div>

        <!-- Plan of Care Tab -->
        <div v-else-if="activeTab === 'plan-of-care'">
          <h2 class="mb-4 text-lg font-semibold text-slate-900">Plan of Care</h2>
          <p class="text-sm text-slate-600">
            Coming in M4 - Treatment plans, goals, and milestones
          </p>
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

    <!-- Schedule Appointment Modal -->
    <AppointmentFormModal
      :visible="showScheduleModal"
      mode="create"
      :prefill-client-id="client?.id ?? null"
      @update:visible="showScheduleModal = $event"
      @submit="handleScheduleAppointment"
    />

    <!-- Success Toast -->
    <AppointmentSuccessToast
      v-model:visible="showSuccessToast"
      message="Appointment scheduled"
      :datetime="successToastData.datetime"
      :actions="successToastActions"
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
