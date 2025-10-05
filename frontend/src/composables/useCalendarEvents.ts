import { ref, computed } from 'vue'
import type { EventInput, EventClickArg } from '@fullcalendar/core'
import type { AppointmentListItem } from '@/types/calendar'
import { useAppointmentsStore } from '@/stores/appointments'
import { getStatusColor } from '@/utils/calendar/appointmentHelpers'

/**
 * Composable for managing calendar events
 *
 * Handles:
 * - Transforming appointments to FullCalendar events
 * - Event click handling
 * - Selected appointment state (reactive to store updates)
 * - Conflict detection for calendar display
 */
export function useCalendarEvents() {
  const appointmentsStore = useAppointmentsStore()

  // Store only the selected appointment ID, not the object reference
  // This ensures we always get fresh data from the store
  const selectedAppointmentId = ref<string | null>(null)

  // Computed property that always fetches the latest appointment from the store
  // This ensures the modal displays updated times after drag-and-drop reschedule
  const selectedAppointment = computed<AppointmentListItem | null>({
    get: () => {
      if (!selectedAppointmentId.value) return null

      // Always fetch fresh data from store to avoid stale references
      return appointmentsStore.appointments.find(
        (a) => a.id === selectedAppointmentId.value
      ) || null
    },
    set: (value: AppointmentListItem | null) => {
      selectedAppointmentId.value = value ? value.id : null
    }
  })

  /**
   * Check if an appointment has conflicts with other appointments
   */
  function checkIfAppointmentHasConflict(
    appointment: AppointmentListItem,
    allAppointments: AppointmentListItem[]
  ): boolean {
    return allAppointments.some((other) => {
      // Don't compare with self
      if (other.id === appointment.id) return false

      // Ignore cancelled and no-show appointments
      const ignoredStatuses = ['cancelled', 'no_show']
      if (ignoredStatuses.includes(other.status.toLowerCase())) return false

      const appointmentStart = new Date(appointment.scheduled_start)
      const appointmentEnd = new Date(appointment.scheduled_end)
      const otherStart = new Date(other.scheduled_start)
      const otherEnd = new Date(other.scheduled_end)

      // Check for overlap
      const hasOverlap = otherStart < appointmentEnd && otherEnd > appointmentStart

      // Exclude exact back-to-back (adjacency is OK)
      const isBackToBack =
        otherEnd.getTime() === appointmentStart.getTime() ||
        otherStart.getTime() === appointmentEnd.getTime()

      return hasOverlap && !isBackToBack
    })
  }

  /**
   * Transform appointments from store to FullCalendar events
   */
  const calendarEvents = computed<EventInput[]>(() => {
    const allAppointments = appointmentsStore.appointments

    return allAppointments.map((appointment) => {
      const hasConflict = checkIfAppointmentHasConflict(appointment, allAppointments)
      const isCancelled = appointment.status === 'cancelled'

      return {
        id: appointment.id,
        title:
          appointment.client?.full_name || `Client ${appointment.client_id.slice(0, 8)}`,
        start: appointment.scheduled_start,
        end: appointment.scheduled_end,
        // Use grey color for cancelled appointments
        backgroundColor: isCancelled ? '#94a3b8' : getStatusColor(appointment.status), // slate-400
        borderColor: isCancelled ? '#cbd5e1' : getStatusColor(appointment.status), // slate-300
        classNames: [
          ...(hasConflict ? ['has-conflict'] : []),
          ...(isCancelled ? ['is-cancelled'] : []),
        ],
        extendedProps: {
          status: appointment.status,
          location_type: appointment.location_type,
          location_details: appointment.location_details,
          notes: appointment.notes,
          client_id: appointment.client_id,
          hasConflict,
          isCancelled,
        },
      }
    })
  })

  /**
   * Handle event click - show appointment details
   * Sets the selected appointment ID, which triggers the computed property
   * to fetch the latest data from the store
   */
  function handleEventClick(clickInfo: EventClickArg) {
    const appointmentId = clickInfo.event.id
    const appointment = appointmentsStore.appointments.find(
      (a) => a.id === appointmentId
    )
    if (appointment) {
      // This will trigger the computed setter, which stores only the ID
      selectedAppointment.value = appointment
    }
  }

  return {
    // State
    selectedAppointment,
    calendarEvents,

    // Methods
    handleEventClick,
  }
}
