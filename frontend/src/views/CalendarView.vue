<script setup lang="ts">
import { ref, computed } from 'vue'
import { useAppointmentsStore } from '@/stores/appointments'
import FullCalendar from '@fullcalendar/vue3'
import type { AppointmentListItem } from '@/types/calendar'
import { useCalendar } from '@/composables/useCalendar'
import { useCalendarEvents } from '@/composables/useCalendarEvents'
import { useCalendarKeyboardShortcuts } from '@/composables/useCalendarKeyboardShortcuts'
import { useCalendarLoading } from '@/composables/useCalendarLoading'
import CalendarToolbar from '@/components/calendar/CalendarToolbar.vue'
import AppointmentDetailsModal from '@/components/calendar/AppointmentDetailsModal.vue'
import CalendarLoadingState from '@/components/calendar/CalendarLoadingState.vue'

/**
 * Calendar View - appointment scheduling with weekly/day/month views
 *
 * TODO: Add appointment creation/editing modal
 * TODO: Implement drag-and-drop rescheduling
 * TODO: Add conflict detection
 */

const appointmentsStore = useAppointmentsStore()
const calendarRef = ref<InstanceType<typeof FullCalendar>>()

// Calendar state and navigation
const {
  currentView,
  currentDate,
  formattedDateRange,
  changeView,
  handlePrev,
  handleNext,
  handleToday,
  buildCalendarOptions,
} = useCalendar()

// Calendar events and selection
const { selectedAppointment, calendarEvents, handleEventClick } = useCalendarEvents()

// Debounced loading state
const { showLoadingSpinner } = useCalendarLoading()

// Keyboard shortcuts
useCalendarKeyboardShortcuts({
  onToday: handleToday,
  onPrevious: handlePrev,
  onNext: handleNext,
  onChangeView: changeView,
  onCreateAppointment: createNewAppointment,
  selectedAppointment,
})

// Build calendar options with events and handlers
const calendarOptions = computed(() =>
  buildCalendarOptions(calendarEvents.value, handleEventClick)
)

/**
 * Placeholder action handlers
 */
function viewClientDetails(_clientId: string) {
  // TODO: Navigate to client profile
}

function editAppointment(_appointment: AppointmentListItem) {
  // TODO: Open edit modal
  selectedAppointment.value = null
}

function startSessionNotes(_appointment: AppointmentListItem) {
  // TODO: Navigate to session notes
  selectedAppointment.value = null
}

function cancelAppointment(_appointment: AppointmentListItem) {
  // TODO: Show confirmation dialog
  selectedAppointment.value = null
}

function createNewAppointment() {
  // TODO: Open create appointment modal
}
</script>

<template>
  <div class="container mx-auto px-4 py-8">
    <!-- Header -->
    <header class="mb-6">
      <h1 class="mb-2 text-3xl font-bold text-gray-900">Calendar</h1>
      <p class="text-gray-600">Weekly appointment schedule</p>
    </header>

    <!-- Loading State (Only show for initial load with no appointments) -->
    <CalendarLoadingState
      v-if="showLoadingSpinner && appointmentsStore.appointments.length === 0"
    />

    <!-- Error State -->
    <div
      v-else-if="appointmentsStore.error"
      class="rounded-lg border border-red-200 bg-red-50 p-4 text-red-800"
    >
      <p class="font-semibold">Error loading appointments</p>
      <p class="mt-1 text-sm">{{ appointmentsStore.error }}</p>
    </div>

    <!-- Calendar View -->
    <div
      v-else
      class="calendar-card-wrapper relative rounded-lg border border-gray-200 bg-white shadow-sm"
    >
      <!-- Toolbar -->
      <CalendarToolbar
        :current-view="currentView"
        :formatted-date-range="formattedDateRange"
        @update:view="changeView"
        @previous="handlePrev"
        @next="handleNext"
        @today="handleToday"
        @create-appointment="createNewAppointment"
      />

      <!-- Calendar Content Area (Fixed Height Container) -->
      <div class="calendar-content-area">
        <!-- FullCalendar Component with Transition -->
        <div class="calendar-container relative p-4">
          <Transition name="calendar-fade" mode="out-in">
            <FullCalendar
              ref="calendarRef"
              :key="`${currentView}-${currentDate.toISOString()}`"
              :options="calendarOptions"
            />
          </Transition>
        </div>
      </div>
    </div>

    <!-- Appointment Detail Modal -->
    <AppointmentDetailsModal
      :appointment="selectedAppointment"
      :visible="!!selectedAppointment"
      @update:visible="selectedAppointment = null"
      @edit="editAppointment"
      @start-session-notes="startSessionNotes"
      @cancel="cancelAppointment"
      @view-client="viewClientDetails"
    />
  </div>
</template>

<style>
/* Calendar Transition Animations */
.calendar-fade-enter-active,
.calendar-fade-leave-active {
  transition: opacity 150ms ease-in-out;
}

.calendar-fade-enter-from {
  opacity: 0;
}

.calendar-fade-leave-to {
  opacity: 0;
}

/* Respect user's motion preferences for accessibility */
@media (prefers-reduced-motion: reduce) {
  .calendar-fade-enter-active,
  .calendar-fade-leave-active {
    transition: none;
  }
}

/**
 * Fixed Layout System for Calendar Transitions
 *
 * Architecture:
 * 1. calendar-content-area: Fixed height container (700px) - consistent across all views
 * 2. calendar-container: Positioned relatively within content area
 *
 * This ensures smooth transitions between calendar views without layout shifts.
 * The fixed height prevents the container from resizing when switching between Day/Week/Month views.
 */

/* Main content area with consistent fixed height for all views */
.calendar-content-area {
  position: relative;
  height: 700px; /* Fixed height - no resizing between views */
}

/* Calendar container */
.calendar-container {
  position: relative;
  z-index: 1;
}

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
