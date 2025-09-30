<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useAppointmentsStore } from '@/stores/appointments'
import FullCalendar from '@fullcalendar/vue3'
import type {
  CalendarOptions,
  EventInput,
  EventClickArg,
  Calendar,
} from '@fullcalendar/core'
import timeGridPlugin from '@fullcalendar/timegrid'
import dayGridPlugin from '@fullcalendar/daygrid'
import interactionPlugin from '@fullcalendar/interaction'
import type { paths } from '@/api/schema'

type AppointmentResponse =
  paths['/api/v1/appointments']['get']['responses']['200']['content']['application/json']
type AppointmentListItem = AppointmentResponse['items'][0]

/**
 * Calendar View
 *
 * Weekly calendar view for appointment scheduling.
 * Uses FullCalendar for drag-and-drop appointment management.
 *
 * Features:
 * - Weekly/day/month view toggle
 * - Date navigation (prev/next/today)
 * - Appointment display with color coding
 * - Click to view appointment details
 * - Responsive design
 *
 * TODO: Add appointment creation/editing modal
 * TODO: Implement drag-and-drop rescheduling
 * TODO: Add conflict detection
 */

const appointmentsStore = useAppointmentsStore()
const calendarRef = ref<InstanceType<typeof FullCalendar>>()
const calendarApi = ref<Calendar | null>(null)
const currentView = ref<'timeGridWeek' | 'timeGridDay' | 'dayGridMonth'>('timeGridWeek')
const currentDateRange = ref<{ start: Date; end: Date }>({
  start: new Date(),
  end: new Date(),
})

// Track last fetched date range to prevent duplicate fetches
const lastFetchedRange = ref<{ start: string; end: string } | null>(null)

// Selected appointment for detail modal
const selectedAppointment = ref<AppointmentListItem | null>(null)
const showAppointmentModal = ref(false)

/**
 * Transform appointments from store to FullCalendar events
 */
const calendarEvents = computed<EventInput[]>(() => {
  return appointmentsStore.appointments.map((appointment) => ({
    id: appointment.id,
    title: `Client: ${appointment.client_id.slice(0, 8)}`,
    start: appointment.scheduled_start,
    end: appointment.scheduled_end,
    backgroundColor: getStatusColor(appointment.status),
    borderColor: getStatusColor(appointment.status),
    extendedProps: {
      status: appointment.status,
      location_type: appointment.location_type,
      location_details: appointment.location_details,
      notes: appointment.notes,
      client_id: appointment.client_id,
    },
  }))
})

/**
 * Get color based on appointment status
 */
function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    scheduled: '#3b82f6', // blue-500
    confirmed: '#10b981', // green-500
    in_progress: '#f59e0b', // amber-500
    completed: '#6b7280', // gray-500
    cancelled: '#ef4444', // red-500
    no_show: '#dc2626', // red-600
  }
  return colors[status] || '#3b82f6'
}

/**
 * FullCalendar configuration
 */
const calendarOptions = computed<CalendarOptions>(() => ({
  plugins: [timeGridPlugin, dayGridPlugin, interactionPlugin],
  initialView: currentView.value,
  headerToolbar: false, // Custom header toolbar
  height: 'auto',
  slotMinTime: '08:00:00',
  slotMaxTime: '20:00:00',
  slotDuration: '00:30:00',
  allDaySlot: false,
  nowIndicator: true,
  editable: false, // TODO: Enable drag-and-drop later
  selectable: false, // TODO: Enable selection for creating appointments
  selectMirror: true,
  dayMaxEvents: true,
  weekends: true,
  events: calendarEvents.value,
  eventClick: handleEventClick,
  datesSet: handleDatesSet,
  eventTimeFormat: {
    hour: '2-digit',
    minute: '2-digit',
    meridiem: 'short',
  },
  slotLabelFormat: {
    hour: '2-digit',
    minute: '2-digit',
    meridiem: 'short',
  },
}))

/**
 * Handle date range changes (when user navigates)
 * This callback fires on initial render AND whenever the date range changes
 */
function handleDatesSet(dateInfo: { start: Date; end: Date }) {
  currentDateRange.value = {
    start: dateInfo.start,
    end: dateInfo.end,
  }

  // Fetch appointments for the new date range
  const startDate = dateInfo.start.toISOString().split('T')[0]
  const endDate = dateInfo.end.toISOString().split('T')[0]

  // Guard: Only fetch if date range has changed
  if (
    lastFetchedRange.value?.start === startDate &&
    lastFetchedRange.value?.end === endDate
  ) {
    console.log('Skipping duplicate fetch for same date range:', { startDate, endDate })
    return
  }

  // Update last fetched range before making the API call
  // Guard: Ensure dates are defined
  if (!startDate || !endDate) {
    console.warn('Date range contains undefined values:', { startDate, endDate })
    return
  }
  lastFetchedRange.value = { start: startDate, end: endDate }

  console.log('Fetching appointments for date range:', { startDate, endDate })
  appointmentsStore.fetchAppointments(startDate, endDate)
}

/**
 * Initialize calendar on component mount
 *
 * Note: We don't need to fetch appointments here because FullCalendar's
 * datesSet callback will fire immediately after initialization and handle
 * the initial fetch. This prevents duplicate API calls.
 *
 * We store a reference to the Calendar API for use in navigation handlers.
 */
onMounted(async () => {
  // Store calendar API reference for navigation
  // Use nextTick to ensure FullCalendar is fully mounted and rendered
  await nextTick()
  if (calendarRef.value) {
    calendarApi.value = calendarRef.value.getApi()
  } else {
    console.error('Calendar ref is undefined - navigation buttons will not work')
  }
})

/**
 * Handle event click - show appointment details
 */
function handleEventClick(clickInfo: EventClickArg) {
  const appointmentId = clickInfo.event.id
  const appointment = appointmentsStore.appointments.find((a) => a.id === appointmentId)
  if (appointment) {
    selectedAppointment.value = appointment
    showAppointmentModal.value = true
  }
}

/**
 * Close appointment detail modal
 */
function closeAppointmentModal() {
  showAppointmentModal.value = false
  selectedAppointment.value = null
}

/**
 * Navigation: Go to previous period
 */
function handlePrev() {
  if (calendarApi.value) {
    calendarApi.value.prev()
  } else {
    console.warn('Calendar API not initialized yet')
  }
}

/**
 * Navigation: Go to next period
 */
function handleNext() {
  if (calendarApi.value) {
    calendarApi.value.next()
  } else {
    console.warn('Calendar API not initialized yet')
  }
}

/**
 * Navigation: Go to today
 */
function handleToday() {
  if (calendarApi.value) {
    calendarApi.value.today()
  } else {
    console.warn('Calendar API not initialized yet')
  }
}

/**
 * Change calendar view
 */
function changeView(view: 'timeGridWeek' | 'timeGridDay' | 'dayGridMonth') {
  currentView.value = view
  if (calendarApi.value) {
    calendarApi.value.changeView(view)
  } else {
    console.warn('Calendar API not initialized yet')
  }
}

/**
 * Format date range for display
 */
const dateRangeText = computed(() => {
  const options: Intl.DateTimeFormatOptions = {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  }
  const start = currentDateRange.value.start.toLocaleDateString('en-US', options)
  const end = currentDateRange.value.end.toLocaleDateString('en-US', options)
  return currentView.value === 'timeGridDay' ? start : `${start} - ${end}`
})

/**
 * Format appointment time for display
 */
function formatAppointmentTime(start: string, end: string): string {
  const startDate = new Date(start)
  const endDate = new Date(end)
  const options: Intl.DateTimeFormatOptions = {
    hour: '2-digit',
    minute: '2-digit',
  }
  return `${startDate.toLocaleTimeString('en-US', options)} - ${endDate.toLocaleTimeString('en-US', options)}`
}

/**
 * Get status badge styling
 */
function getStatusBadgeClass(status: string): string {
  const classes: Record<string, string> = {
    scheduled: 'bg-blue-100 text-blue-800',
    confirmed: 'bg-green-100 text-green-800',
    in_progress: 'bg-amber-100 text-amber-800',
    completed: 'bg-gray-100 text-gray-800',
    cancelled: 'bg-red-100 text-red-800',
    no_show: 'bg-red-100 text-red-800',
  }
  return classes[status] || 'bg-blue-100 text-blue-800'
}
</script>

<template>
  <div class="container mx-auto px-4 py-8">
    <!-- Header -->
    <header class="mb-6">
      <h1 class="mb-2 text-3xl font-bold text-gray-900">Calendar</h1>
      <p class="text-gray-600">Weekly appointment schedule</p>
    </header>

    <!-- Loading State -->
    <div
      v-if="appointmentsStore.loading && appointmentsStore.appointments.length === 0"
      class="flex h-96 items-center justify-center rounded-lg border border-gray-200 bg-white shadow-sm"
    >
      <div class="text-center">
        <div
          class="mb-4 inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent"
        ></div>
        <p class="text-gray-600">Loading appointments...</p>
      </div>
    </div>

    <!-- Error State -->
    <div
      v-else-if="appointmentsStore.error"
      class="rounded-lg border border-red-200 bg-red-50 p-4 text-red-800"
    >
      <p class="font-semibold">Error loading appointments</p>
      <p class="mt-1 text-sm">{{ appointmentsStore.error }}</p>
    </div>

    <!-- Calendar View -->
    <div v-else class="rounded-lg border border-gray-200 bg-white shadow-sm">
      <!-- Custom Toolbar -->
      <div class="border-b border-gray-200 p-4">
        <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <!-- Date Navigation -->
          <div class="flex items-center gap-2">
            <button
              @click="handleToday"
              class="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              Today
            </button>
            <div class="flex gap-1">
              <button
                @click="handlePrev"
                class="rounded-md border border-gray-300 bg-white p-2 text-gray-700 hover:bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                aria-label="Previous period"
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
                    d="M15 19l-7-7 7-7"
                  />
                </svg>
              </button>
              <button
                @click="handleNext"
                class="rounded-md border border-gray-300 bg-white p-2 text-gray-700 hover:bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                aria-label="Next period"
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
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              </button>
            </div>
            <span class="ml-2 text-lg font-semibold text-gray-900">
              {{ dateRangeText }}
            </span>
          </div>

          <!-- View Switcher -->
          <div class="flex gap-1 rounded-md border border-gray-300 bg-gray-50 p-1">
            <button
              @click="changeView('timeGridDay')"
              :class="[
                'rounded px-3 py-1.5 text-sm font-medium transition-colors',
                currentView === 'timeGridDay'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900',
              ]"
            >
              Day
            </button>
            <button
              @click="changeView('timeGridWeek')"
              :class="[
                'rounded px-3 py-1.5 text-sm font-medium transition-colors',
                currentView === 'timeGridWeek'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900',
              ]"
            >
              Week
            </button>
            <button
              @click="changeView('dayGridMonth')"
              :class="[
                'rounded px-3 py-1.5 text-sm font-medium transition-colors',
                currentView === 'dayGridMonth'
                  ? 'bg-white text-gray-900 shadow-sm'
                  : 'text-gray-600 hover:text-gray-900',
              ]"
            >
              Month
            </button>
          </div>
        </div>
      </div>

      <!-- FullCalendar Component -->
      <div class="p-4">
        <FullCalendar ref="calendarRef" :options="calendarOptions" />

        <!-- Empty State Overlay -->
        <div
          v-if="
            !appointmentsStore.loading && appointmentsStore.appointments.length === 0
          "
          class="mt-8 py-12 text-center"
        >
          <svg
            class="mx-auto h-12 w-12 text-gray-400"
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
          <h3 class="mt-4 text-lg font-medium text-gray-900">
            No appointments scheduled
          </h3>
          <p class="mt-2 text-sm text-gray-500">
            Get started by creating your first appointment.
          </p>
        </div>
      </div>
    </div>

    <!-- Appointment Detail Modal -->
    <Teleport to="body">
      <div
        v-if="showAppointmentModal && selectedAppointment"
        class="bg-opacity-50 fixed inset-0 z-50 flex items-center justify-center bg-black p-4"
        @click.self="closeAppointmentModal"
      >
        <div class="w-full max-w-lg rounded-lg bg-white shadow-xl">
          <!-- Modal Header -->
          <div
            class="flex items-center justify-between border-b border-gray-200 px-6 py-4"
          >
            <h2 class="text-xl font-semibold text-gray-900">Appointment Details</h2>
            <button
              @click="closeAppointmentModal"
              class="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              aria-label="Close modal"
            >
              <svg
                class="h-6 w-6"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>

          <!-- Modal Body -->
          <div class="px-6 py-4">
            <dl class="space-y-4">
              <!-- Time -->
              <div>
                <dt class="text-sm font-medium text-gray-500">Time</dt>
                <dd class="mt-1 text-base text-gray-900">
                  {{
                    formatAppointmentTime(
                      selectedAppointment.scheduled_start,
                      selectedAppointment.scheduled_end
                    )
                  }}
                </dd>
                <dd class="mt-1 text-sm text-gray-500">
                  {{
                    new Date(selectedAppointment.scheduled_start).toLocaleDateString(
                      'en-US',
                      {
                        weekday: 'long',
                        year: 'numeric',
                        month: 'long',
                        day: 'numeric',
                      }
                    )
                  }}
                </dd>
              </div>

              <!-- Status -->
              <div>
                <dt class="text-sm font-medium text-gray-500">Status</dt>
                <dd class="mt-1">
                  <span
                    :class="[
                      'inline-flex rounded-full px-3 py-1 text-xs font-semibold capitalize',
                      getStatusBadgeClass(selectedAppointment.status),
                    ]"
                  >
                    {{ selectedAppointment.status.replace('_', ' ') }}
                  </span>
                </dd>
              </div>

              <!-- Location -->
              <div>
                <dt class="text-sm font-medium text-gray-500">Location</dt>
                <dd class="mt-1 text-base text-gray-900 capitalize">
                  {{ selectedAppointment.location_type.replace('_', ' ') }}
                </dd>
                <dd
                  v-if="selectedAppointment.location_details"
                  class="mt-1 text-sm text-gray-500"
                >
                  {{ selectedAppointment.location_details }}
                </dd>
              </div>

              <!-- Client ID -->
              <div>
                <dt class="text-sm font-medium text-gray-500">Client ID</dt>
                <dd class="mt-1 font-mono text-sm text-gray-900">
                  {{ selectedAppointment.client_id }}
                </dd>
              </div>

              <!-- Notes -->
              <div v-if="selectedAppointment.notes">
                <dt class="text-sm font-medium text-gray-500">Notes</dt>
                <dd class="mt-1 text-base text-gray-900">
                  {{ selectedAppointment.notes }}
                </dd>
              </div>
            </dl>
          </div>

          <!-- Modal Footer -->
          <div class="flex justify-end gap-3 border-t border-gray-200 px-6 py-4">
            <button
              @click="closeAppointmentModal"
              class="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 focus:ring-2 focus:ring-blue-500 focus:outline-none"
            >
              Close
            </button>
            <!-- TODO: Add Edit and Delete buttons -->
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style>
/* FullCalendar custom styling to match PazPaz design */
:root {
  --fc-border-color: #e5e7eb;
  --fc-button-bg-color: #3b82f6;
  --fc-button-border-color: #3b82f6;
  --fc-button-hover-bg-color: #2563eb;
  --fc-button-hover-border-color: #2563eb;
  --fc-button-active-bg-color: #1d4ed8;
  --fc-button-active-border-color: #1d4ed8;
  --fc-today-bg-color: #eff6ff;
}

.fc {
  font-family: inherit;
}

.fc-theme-standard td,
.fc-theme-standard th {
  border-color: #e5e7eb;
}

.fc-scrollgrid {
  border-color: #e5e7eb !important;
}

.fc-col-header-cell {
  background-color: #f9fafb;
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.75rem;
  letter-spacing: 0.05em;
  color: #6b7280;
}

.fc-timegrid-slot {
  height: 3rem;
}

.fc-timegrid-slot-label {
  color: #6b7280;
  font-size: 0.875rem;
}

.fc-event {
  border-radius: 0.375rem;
  padding: 2px 4px;
  font-size: 0.875rem;
  cursor: pointer;
  transition: opacity 0.2s;
}

.fc-event:hover {
  opacity: 0.9;
}

.fc-event-title {
  font-weight: 500;
}

.fc-daygrid-event {
  white-space: normal;
}

/* Responsive adjustments */
@media (max-width: 640px) {
  .fc-header-toolbar {
    flex-direction: column;
    gap: 0.5rem;
  }

  .fc-toolbar-chunk {
    width: 100%;
    display: flex;
    justify-content: center;
  }
}
</style>
