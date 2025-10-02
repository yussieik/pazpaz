<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppointmentsStore } from '@/stores/appointments'
import FullCalendar from '@fullcalendar/vue3'
import type { AppointmentListItem, AppointmentFormData } from '@/types/calendar'
import { useCalendar } from '@/composables/useCalendar'
import { useCalendarEvents } from '@/composables/useCalendarEvents'
import { useCalendarKeyboardShortcuts } from '@/composables/useCalendarKeyboardShortcuts'
import { useCalendarLoading } from '@/composables/useCalendarLoading'
import PageHeader from '@/components/common/PageHeader.vue'
import CalendarToolbar from '@/components/calendar/CalendarToolbar.vue'
import AppointmentDetailsModal from '@/components/calendar/AppointmentDetailsModal.vue'
import AppointmentFormModal from '@/components/calendar/AppointmentFormModal.vue'
import CancelAppointmentDialog from '@/components/calendar/CancelAppointmentDialog.vue'
import CalendarLoadingState from '@/components/calendar/CalendarLoadingState.vue'

/**
 * Calendar View - appointment scheduling with weekly/day/month views
 *
 * Implemented (M2):
 * - Appointment creation/editing modals
 * - Cancel appointment dialog
 *
 * TODO (M3): Implement drag-and-drop rescheduling
 * TODO (M3): Add conflict detection
 * TODO (M3): Wire up API calls for CRUD operations
 */

const route = useRoute()
const router = useRouter()
const appointmentsStore = useAppointmentsStore()
const calendarRef = ref<InstanceType<typeof FullCalendar>>()
const toolbarRef = ref<InstanceType<typeof CalendarToolbar>>()

// Modal/dialog state
const showCreateModal = ref(false)
const showEditModal = ref(false)
const showCancelDialog = ref(false)
const appointmentToEdit = ref<AppointmentListItem | null>(null)
const appointmentToCancel = ref<AppointmentListItem | null>(null)

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

// Button refs for keyboard shortcut visual feedback
const toolbarButtonRefs = computed(() => ({
  todayButton: toolbarRef.value?.todayButtonRef,
  previousButton: toolbarRef.value?.previousButtonRef,
  nextButton: toolbarRef.value?.nextButtonRef,
  weekButton: toolbarRef.value?.weekButtonRef,
  dayButton: toolbarRef.value?.dayButtonRef,
  monthButton: toolbarRef.value?.monthButtonRef,
}))

// Keyboard shortcuts with button visual feedback
useCalendarKeyboardShortcuts({
  onToday: handleToday,
  onPrevious: handlePrev,
  onNext: handleNext,
  onChangeView: changeView,
  onCreateAppointment: createNewAppointment,
  selectedAppointment,
  buttonRefs: toolbarButtonRefs,
})

// Build calendar options with events and handlers
const calendarOptions = computed(() =>
  buildCalendarOptions(calendarEvents.value, handleEventClick)
)

/**
 * Helper function to get visible date range based on current view
 */
function getVisibleDateRange(view: string, date: Date): { start: Date; end: Date } {
  const start = new Date(date)
  const end = new Date(date)

  switch (view) {
    case 'timeGridWeek':
      // Get Sunday of current week
      start.setDate(date.getDate() - date.getDay())
      start.setHours(0, 0, 0, 0)
      // Get Saturday of current week
      end.setDate(start.getDate() + 6)
      end.setHours(23, 59, 59, 999)
      break
    case 'timeGridDay':
      start.setHours(0, 0, 0, 0)
      end.setHours(23, 59, 59, 999)
      break
    case 'dayGridMonth':
      // First day of month
      start.setDate(1)
      start.setHours(0, 0, 0, 0)
      // Last day of month
      end.setMonth(date.getMonth() + 1, 0)
      end.setHours(23, 59, 59, 999)
      break
  }

  return { start, end }
}

/**
 * Helper function to check if appointment is within date range
 */
function isAppointmentInRange(
  appointment: AppointmentListItem,
  start: Date,
  end: Date
): boolean {
  const aptDate = new Date(appointment.scheduled_start)
  return aptDate >= start && aptDate <= end
}

/**
 * Appointment summary filtered by visible date range
 * Shows appointment count for currently visible calendar period (week/day/month)
 */
const appointmentSummary = computed(() => {
  const appointments = appointmentsStore.appointments

  if (appointments.length === 0) {
    return null
  }

  // Filter appointments by visible date range
  const { start, end } = getVisibleDateRange(currentView.value, currentDate.value)
  const visibleAppointments = appointments.filter((apt: AppointmentListItem) =>
    isAppointmentInRange(apt, start, end)
  )

  const appointmentCount = visibleAppointments.length

  // Don't show metadata if no appointments in visible range
  if (appointmentCount === 0) {
    return null
  }

  const parts = []
  parts.push(`${appointmentCount} appointment${appointmentCount === 1 ? '' : 's'}`)

  // TODO: Add conflict detection logic when implemented
  // const conflicts = detectConflicts(visibleAppointments)
  // if (conflicts > 0) parts.push(`${conflicts} conflict${conflicts === 1 ? '' : 's'}`)

  // TODO (M4): Add session notes status
  // const needsNotes = visibleAppointments.filter(a => a.status === 'completed' && !a.has_notes).length
  // if (needsNotes > 0) parts.push(`${needsNotes} session${needsNotes === 1 ? '' : 's'} need notes`)

  return parts.join(' · ') || null
})

/**
 * Action handlers for appointment modal
 */
function viewClientDetails(clientId: string) {
  const appointmentData = selectedAppointment.value

  // Store in sessionStorage for reliable state passing across navigation
  if (appointmentData) {
    sessionStorage.setItem(
      'navigationContext',
      JSON.stringify({
        type: 'appointment',
        appointment: appointmentData,
        timestamp: Date.now(),
      })
    )
  }

  // Navigate to client detail (will pick up appointment from sessionStorage)
  router.push({
    name: 'client-detail',
    params: { id: clientId },
  })

  // Close modal after navigation starts
  selectedAppointment.value = null
}

function editAppointment(appointment: AppointmentListItem) {
  selectedAppointment.value = null // Close detail modal
  appointmentToEdit.value = appointment
  showEditModal.value = true
}

function startSessionNotes(_appointment: AppointmentListItem) {
  selectedAppointment.value = null // Close modal
  // TODO (M4): Open session notes drawer
}

function cancelAppointment(appointment: AppointmentListItem) {
  selectedAppointment.value = null // Close detail modal
  appointmentToCancel.value = appointment
  showCancelDialog.value = true
}

function createNewAppointment() {
  showCreateModal.value = true
}

/**
 * Form submission handlers
 */
async function handleCreateAppointment(_data: AppointmentFormData) {
  // TODO (M3): Call API to create appointment
  showCreateModal.value = false
}

async function handleEditAppointment(data: AppointmentFormData) {
  if (!appointmentToEdit.value) return

  try {
    // Update appointment in store (calls API and updates local state)
    await appointmentsStore.updateAppointment(appointmentToEdit.value.id, data)

    // Close modal and clear edit state
    showEditModal.value = false
    appointmentToEdit.value = null

    // TODO (M3): Add success toast notification
  } catch (error) {
    console.error('Failed to update appointment:', error)
    // TODO (M3): Add error toast notification
    // Keep modal open on error so user can retry
  }
}

async function handleConfirmCancel() {
  // TODO (M3): Call API to delete appointment
  showCancelDialog.value = false
  appointmentToCancel.value = null
}

// Open appointment from query param (for "return to appointment" flow)
watch(
  () => route.query.appointment,
  (appointmentId) => {
    if (appointmentId && typeof appointmentId === 'string') {
      const appointment = appointmentsStore.appointments.find(
        (a: AppointmentListItem) => a.id === appointmentId
      )
      if (appointment) {
        selectedAppointment.value = appointment
      }
      // Clear query param
      router.replace({ query: {} })
    }
  },
  { immediate: true }
)
</script>

<template>
  <div class="container mx-auto px-4 py-8">
    <!-- Header -->
    <PageHeader title="Calendar">
      <template #actions>
        <button
          @click="createNewAppointment"
          class="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-emerald-700 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none sm:w-auto sm:justify-start"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M12 4v16m8-8H4"
            />
          </svg>
          <span>New Appointment</span>
        </button>
      </template>
    </PageHeader>

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
        ref="toolbarRef"
        :current-view="currentView"
        :formatted-date-range="formattedDateRange"
        :appointment-summary="appointmentSummary"
        @update:view="changeView"
        @previous="handlePrev"
        @next="handleNext"
        @today="handleToday"
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

    <!-- Create Appointment Modal -->
    <AppointmentFormModal
      :visible="showCreateModal"
      mode="create"
      @update:visible="showCreateModal = $event"
      @submit="handleCreateAppointment"
    />

    <!-- Edit Appointment Modal -->
    <AppointmentFormModal
      :visible="showEditModal"
      :appointment="appointmentToEdit"
      mode="edit"
      @update:visible="showEditModal = $event"
      @submit="handleEditAppointment"
    />

    <!-- Cancel Appointment Dialog -->
    <CancelAppointmentDialog
      :visible="showCancelDialog"
      :appointment="appointmentToCancel"
      @update:visible="showCancelDialog = $event"
      @confirm="handleConfirmCancel"
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
 * Flexible Layout System for Calendar Transitions
 *
 * Architecture:
 * 1. calendar-content-area: Auto-height container - adapts to FullCalendar's natural height
 * 2. calendar-container: Positioned relatively within content area
 *
 * This ensures smooth transitions between calendar views without layout shifts.
 * FullCalendar's height: 'auto' configuration (in calendarConfig.ts) allows it to size
 * itself based on content (16 hours × 72px = 1,152px + internal structure).
 *
 * The container uses min-height to prevent collapsing and allows natural page scroll
 * instead of container-level scrolling for better UX.
 */

/* Main content area with auto height - adapts to FullCalendar's natural size */
.calendar-content-area {
  position: relative;
  min-height: 600px; /* Prevent collapsing on initial load */
  overflow: visible; /* Allow natural page scroll */
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

/* PHASE 1: Increased slot height for better appointment readability */
.fc-timegrid-slot {
  height: 4.5rem; /* 72px per hour - allows 3 lines of text in appointments (was 3rem/48px) */
}

/* Business hours background (8 AM - 6 PM) */
.fc-non-business {
  background-color: #fafafa; /* Light gray for early/late hours (6-8 AM, 6-10 PM) */
}

/* PHASE 2: Improved time labels styling */
.fc-timegrid-slot-label {
  color: #374151; /* gray-700 - stronger contrast than default gray-500 */
  font-size: 0.875rem;
  font-weight: 500; /* Medium weight for better scannability */
  font-variant-numeric: tabular-nums; /* Align digits vertically */
  vertical-align: top;
  padding-top: 0.25rem;
}

.fc-event {
  border-radius: 0.375rem;
  padding: 4px 6px; /* Increased from 2px 4px for better spacing */
  font-size: 0.875rem;
  line-height: 1.3; /* Tighter line height for multi-line content */
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

/* PHASE 2: Current time indicator - emerald to match PazPaz brand */
.fc-timegrid-now-indicator-line {
  border-color: #10b981; /* emerald-500 */
  border-width: 2px;
  opacity: 0.7;
}

.fc-timegrid-now-indicator-arrow {
  border-top-color: #10b981;
  border-bottom-color: #10b981;
  border-width: 6px;
}

/* PHASE 2: Responsive adjustments */

/* Tablet-specific adjustments (641px - 1024px) */
@media (max-width: 1024px) and (min-width: 641px) {
  .fc-timegrid-slot {
    height: 4rem; /* 64px on tablet - balanced readability */
  }
}

/* Mobile adjustments (≤640px) */
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

  /* Reduce slot height on mobile for better viewport usage */
  .fc-timegrid-slot {
    height: 3.5rem; /* 56px on mobile - still readable */
  }

  .fc-timegrid-slot-label {
    font-size: 0.75rem; /* 12px on mobile */
  }

  .fc-event {
    padding: 2px 4px; /* Tighter padding on mobile */
    font-size: 0.8125rem; /* 13px */
  }
}

/* Conflict Detection Visual Indicators */

/* Striped pattern and border for conflicting appointments */
.fc-event.has-conflict {
  border: 2px solid #f59e0b !important; /* amber-500 */
  background-image: repeating-linear-gradient(
    45deg,
    transparent,
    transparent 10px,
    rgba(251, 191, 36, 0.15) 10px,
    rgba(251, 191, 36, 0.15) 20px
  ) !important;
  position: relative;
}

/* Warning icon badge in top-right corner */
.fc-event.has-conflict::after {
  content: '⚠️';
  position: absolute;
  top: 4px;
  right: 4px;
  width: 18px;
  height: 18px;
  background: white;
  border: 1.5px solid #f59e0b;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  z-index: 10;
  line-height: 1;
  pointer-events: none;
}

/* Ensure conflict indicators work in month view */
.fc-daygrid-event.has-conflict::after {
  top: 2px;
  right: 2px;
  width: 14px;
  height: 14px;
  font-size: 8px;
}

/* Hover state for conflicting appointments */
.fc-event.has-conflict:hover {
  opacity: 1;
  border-color: #d97706; /* amber-600 for stronger visual on hover */
}
</style>
