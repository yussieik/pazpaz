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
 */
export function useCalendarEvents() {
  const appointmentsStore = useAppointmentsStore()

  // Selected appointment for detail modal
  const selectedAppointment = ref<AppointmentListItem | null>(null)

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
