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
 * - Selected appointment state
 * - Conflict detection for calendar display
 */
export function useCalendarEvents() {
  const appointmentsStore = useAppointmentsStore()

  // Selected appointment for detail modal
  const selectedAppointment = ref<AppointmentListItem | null>(null)

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

      return {
        id: appointment.id,
        title:
          appointment.client?.full_name || `Client ${appointment.client_id.slice(0, 8)}`,
        start: appointment.scheduled_start,
        end: appointment.scheduled_end,
        backgroundColor: getStatusColor(appointment.status),
        borderColor: getStatusColor(appointment.status),
        classNames: hasConflict ? ['has-conflict'] : [],
        extendedProps: {
          status: appointment.status,
          location_type: appointment.location_type,
          location_details: appointment.location_details,
          notes: appointment.notes,
          client_id: appointment.client_id,
          hasConflict,
        },
      }
    })
  })

  /**
   * Handle event click - show appointment details
   */
  function handleEventClick(clickInfo: EventClickArg) {
    const appointmentId = clickInfo.event.id
    const appointment = appointmentsStore.appointments.find(
      (a) => a.id === appointmentId
    )
    if (appointment) {
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
