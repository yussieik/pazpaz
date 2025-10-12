import { ref, computed, watch } from 'vue'
import type { EventInput, EventClickArg } from '@fullcalendar/core'
import type { AppointmentListItem, SessionStatus } from '@/types/calendar'
import { useAppointmentsStore } from '@/stores/appointments'
import apiClient from '@/api/client'

/**
 * Composable for managing calendar events
 *
 * Handles:
 * - Transforming appointments to FullCalendar events
 * - Event click handling
 * - Selected appointment state (reactive to store updates)
 * - Conflict detection for calendar display
 * - Session status indicators (P0 feature)
 */
export function useCalendarEvents() {
  const appointmentsStore = useAppointmentsStore()

  const selectedAppointmentId = ref<string | null>(null)
  const sessionStatusMap = ref<Map<string, SessionStatus>>(new Map())

  // Computed property that always fetches the latest appointment from the store
  // This ensures the modal displays updated times after drag-and-drop reschedule
  const selectedAppointment = computed<AppointmentListItem | null>({
    get: () => {
      if (!selectedAppointmentId.value) return null

      const found = appointmentsStore.appointments.find(
        (a) => a.id === selectedAppointmentId.value
      ) || null

      return found
    },
    set: (value: AppointmentListItem | null) => {
      selectedAppointmentId.value = value ? value.id : null
    },
  })

  /**
   * Check if an appointment has conflicts with other appointments
   */
  function checkIfAppointmentHasConflict(
    appointment: AppointmentListItem,
    allAppointments: AppointmentListItem[]
  ): boolean {
    return allAppointments.some((other) => {
      if (other.id === appointment.id) return false

      const ignoredStatuses = ['cancelled', 'no_show']
      if (ignoredStatuses.includes(other.status.toLowerCase())) return false

      const appointmentStart = new Date(appointment.scheduled_start)
      const appointmentEnd = new Date(appointment.scheduled_end)
      const otherStart = new Date(other.scheduled_start)
      const otherEnd = new Date(other.scheduled_end)

      const hasOverlap = otherStart < appointmentEnd && otherEnd > appointmentStart

      const isBackToBack =
        otherEnd.getTime() === appointmentStart.getTime() ||
        otherStart.getTime() === appointmentEnd.getTime()

      return hasOverlap && !isBackToBack
    })
  }

  /**
   * Fetch session status for all appointments
   * Maps appointment IDs to their session status (has session, draft/finalized)
   */
  async function fetchSessionStatus() {
    try {
      const clientIds = [
        ...new Set(
          appointmentsStore.appointments
            .map((apt) => apt.client_id)
            .filter((id): id is string => id !== null)
        ),
      ]

      if (clientIds.length === 0) {
        sessionStatusMap.value = new Map()
        return
      }

      const sessionPromises = clientIds.map((clientId) =>
        apiClient
          .get<{
            items: Array<{
              id: string
              appointment_id: string | null
              is_draft: boolean
            }>
            total: number
          }>('/sessions', {
            params: {
              client_id: clientId,
              page: 1,
              page_size: 100,
            },
          })
          .catch((error) => {
            console.warn(`Failed to fetch sessions for client ${clientId}:`, error)
            return null
          })
      )

      const responses = await Promise.all(sessionPromises)

      const allSessions = responses
        .filter(
          (response): response is NonNullable<typeof response> => response !== null
        )
        .flatMap((response) => response.data.items || [])

      const statusMap = new Map<string, SessionStatus>()

      allSessions.forEach((session) => {
        if (session.appointment_id) {
          statusMap.set(session.appointment_id, {
            hasSession: true,
            sessionId: session.id,
            isDraft: session.is_draft,
          })
        }
      })

      sessionStatusMap.value = statusMap
    } catch (error) {
      console.error('Failed to fetch session status:', error)
    }
  }

  /**
   * Watch appointments and fetch session status when appointments change
   */
  watch(
    () => appointmentsStore.appointments,
    (newAppointments) => {
      if (newAppointments.length > 0) {
        fetchSessionStatus()
      }
    },
    { immediate: true }
  )

  /**
   * Get event color based on appointment status and time
   */
  function getEventColor(appointment: AppointmentListItem): string {
    const now = new Date()
    const isPast = new Date(appointment.scheduled_end) < now

    const colors: Record<string, string> = {
      completed: '#059669',
      cancelled: '#94a3b8',
      no_show: '#f97316',
      scheduled: isPast ? '#f59e0b' : '#10b981',
      confirmed: isPast ? '#f59e0b' : '#10b981',
    }

    return colors[appointment.status] || colors.scheduled
  }

  /**
   * Get event title with status and session indicators
   */
  function getEventTitle(appointment: AppointmentListItem): string {
    const statusEmoji: Record<string, string> = {
      completed: '✓',
      cancelled: '✕',
      no_show: '⚠',
    }

    const statusIndicator = statusEmoji[appointment.status] || ''
    const sessionStatus = sessionStatusMap.value.get(appointment.id)
    const sessionIndicator = sessionStatus?.hasSession ? ' 📄' : ''
    const clientName =
      appointment.client?.full_name ||
      (appointment.client_id ? `Client ${appointment.client_id.slice(0, 8)}` : 'Unknown Client')

    return `${statusIndicator}${sessionIndicator} ${clientName}`.trim()
  }

  /**
   * Transform appointments from store to FullCalendar events
   * Includes session status indicators (P0 feature)
   *
   * Calendar Event Accessibility Patterns:
   * - Completed: Solid emerald fill
   * - Cancelled: Gray with diagonal stripes (event-cancelled class)
   * - No-show: Orange with dashed border (event-no-show class)
   * - Past scheduled: Amber with pulsing glow (event-past-scheduled class)
   * - Future scheduled: Solid emerald fill
   *
   * This meets WCAG 2.1 Level AA requirements (not color-only).
   */
  const calendarEvents = computed<EventInput[]>(() => {
    const allAppointments = appointmentsStore.appointments
    const now = new Date()

    return allAppointments.map((appointment) => {
      const hasConflict = checkIfAppointmentHasConflict(appointment, allAppointments)
      const isCancelled = appointment.status === 'cancelled'
      const isNoShow = appointment.status === 'no_show'
      const isPast = new Date(appointment.scheduled_end) < now
      const isScheduled = appointment.status === 'scheduled'
      const isPastScheduled = isScheduled && isPast

      // Get session status for this appointment
      const sessionStatus = sessionStatusMap.value.get(appointment.id)
      const hasSession = sessionStatus?.hasSession || false
      const eventColor = getEventColor(appointment)
      const eventTitle = getEventTitle(appointment)

      return {
        id: appointment.id,
        title: eventTitle,
        start: appointment.scheduled_start,
        end: appointment.scheduled_end,
        backgroundColor: eventColor,
        borderColor: eventColor,
        classNames: [
          ...(hasConflict ? ['has-conflict'] : []),
          ...(isCancelled ? ['is-cancelled', 'event-cancelled'] : []),
          ...(isNoShow ? ['event-no-show'] : []),
          ...(isPastScheduled ? ['event-past-scheduled'] : []),
          ...(hasSession ? ['event-with-session'] : []),
        ],
        extendedProps: {
          status: appointment.status,
          location_type: appointment.location_type,
          location_details: appointment.location_details,
          notes: appointment.notes,
          client_id: appointment.client_id,
          appointmentId: appointment.id,
          hasConflict,
          isCancelled,
          hasSession,
          sessionId: sessionStatus?.sessionId || null,
          isDraft: sessionStatus?.isDraft || false,
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
      selectedAppointment.value = appointment
    }
  }

  return {
    selectedAppointment,
    calendarEvents,
    sessionStatusMap,
    handleEventClick,
    fetchSessionStatus,
  }
}
