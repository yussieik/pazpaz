<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppointmentsStore } from '@/stores/appointments'
import FullCalendar from '@fullcalendar/vue3'
import type { AppointmentListItem, AppointmentFormData } from '@/types/calendar'
import { useCalendar } from '@/composables/useCalendar'
import { useCalendarEvents } from '@/composables/useCalendarEvents'
import { useCalendarKeyboardShortcuts } from '@/composables/useCalendarKeyboardShortcuts'
import { useCalendarLoading } from '@/composables/useCalendarLoading'
import CalendarToolbar from '@/components/calendar/CalendarToolbar.vue'
import AppointmentDetailsModal from '@/components/calendar/AppointmentDetailsModal.vue'
import AppointmentFormModal from '@/components/calendar/AppointmentFormModal.vue'
import CancelAppointmentDialog from '@/components/calendar/CancelAppointmentDialog.vue'
import CalendarLoadingState from '@/components/calendar/CalendarLoadingState.vue'
import KeyboardShortcutsHelp from '@/components/calendar/KeyboardShortcutsHelp.vue'

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

const router = useRouter()
const appointmentsStore = useAppointmentsStore()
const calendarRef = ref<InstanceType<typeof FullCalendar>>()
const toolbarRef = ref<InstanceType<typeof CalendarToolbar>>()
const showKeyboardHelp = ref(false)

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

// Appointment summary for contextual header metadata
const appointmentSummary = computed(() => {
  const appointments = appointmentsStore.appointments

  if (appointments.length === 0) {
    return null // Don't show metadata if no appointments
  }

  // Count appointments in current view
  const appointmentCount = appointments.length

  const parts = []
  if (appointmentCount > 0) {
    parts.push(`${appointmentCount} appointment${appointmentCount === 1 ? '' : 's'}`)
  }

  // TODO: Add conflict detection logic when implemented
  // const conflicts = detectConflicts(appointments)
  // if (conflicts > 0) parts.push(`${conflicts} conflict${conflicts === 1 ? '' : 's'}`)

  // TODO (M4): Add session notes status
  // const needsNotes = appointments.filter(a => a.status === 'completed' && !a.has_notes).length
  // if (needsNotes > 0) parts.push(`${needsNotes} session${needsNotes === 1 ? '' : 's'} need notes`)

  return parts.join(' · ') || null
})

/**
 * Action handlers for appointment modal
 */
function viewClientDetails(clientId: string) {
  selectedAppointment.value = null // Close modal
  router.push(`/clients/${clientId}`) // Navigate to client detail page
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

/**
 * Keyboard shortcut help modal
 */
function handleHelpKey(e: KeyboardEvent) {
  if (e.key === '?' && !e.metaKey && !e.ctrlKey && !e.shiftKey) {
    // Only trigger if not typing in input field
    const target = e.target as HTMLElement
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return

    e.preventDefault()
    showKeyboardHelp.value = true
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleHelpKey)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleHelpKey)
})
</script>

<template>
  <div class="container mx-auto px-4 py-8">
    <!-- Header -->
    <header
      class="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
    >
      <!-- Title and metadata (inline on desktop, wraps on mobile) -->
      <div class="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
        <h1 class="text-2xl font-semibold text-slate-900">Calendar</h1>
        <span
          v-if="appointmentSummary"
          class="flex items-baseline gap-2.5 text-sm font-medium text-slate-600"
        >
          <span class="text-slate-400" aria-hidden="true">·</span>
          <span>{{ appointmentSummary }}</span>
        </span>
      </div>

      <!-- Primary action button -->
      <button
        @click="createNewAppointment"
        class="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-emerald-700 focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 focus-visible:outline-none"
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
        ref="toolbarRef"
        :current-view="currentView"
        :formatted-date-range="formattedDateRange"
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

    <!-- Keyboard Shortcuts Help Modal -->
    <KeyboardShortcutsHelp
      :visible="showKeyboardHelp"
      @update:visible="showKeyboardHelp = $event"
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
