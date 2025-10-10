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

  // Store only the selected appointment ID, not the object reference
  // This ensures we always get fresh data from the store
  const selectedAppointmentId = ref<string | null>(null)

  // Session status mapping: appointment_id -> session info
  const sessionStatusMap = ref<Map<string, SessionStatus>>(new Map())

  // Computed property that always fetches the latest appointment from the store
  // This ensures the modal displays updated times after drag-and-drop reschedule
  const selectedAppointment = computed<AppointmentListItem | null>({
    get: () => {
      if (!selectedAppointmentId.value) return null

      // Always fetch fresh data from store to avoid stale references
      return (
        appointmentsStore.appointments.find(
          (a) => a.id === selectedAppointmentId.value
        ) || null
      )
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
   * Fetch session status for all appointments
   * Maps appointment IDs to their session status (has session, draft/finalized)
   */
  async function fetchSessionStatus() {
    try {
      // Get unique client IDs from loaded appointments
      const clientIds = [
        ...new Set(
          appointmentsStore.appointments
            .map((apt) => apt.client_id)
            .filter((id): id is string => id !== null)
        ),
      ]

      if (clientIds.length === 0) {
        // No appointments with clients, nothing to fetch
        sessionStatusMap.value = new Map()
        return
      }

      // Fetch sessions for each client
      // Note: This makes multiple API calls. For V1 with <100 clients this is acceptable.
      // V2: Consider backend endpoint to fetch sessions by appointment_ids or all sessions
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
              page_size: 100, // Max sessions per client for calendar view
            },
          })
          .catch((error) => {
            // Log but don't fail - some clients might not have sessions
            console.warn(`Failed to fetch sessions for client ${clientId}:`, error)
            return null
          })
      )

      const responses = await Promise.all(sessionPromises)

      // Aggregate all sessions from all clients
      const allSessions = responses
        .filter(
          (response): response is NonNullable<typeof response> => response !== null
        )
        .flatMap((response) => response.data.items || [])

      // Create map of appointment_id -> session info
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
      // Don't throw - gracefully degrade if sessions can't be fetched
      // Visual indicators will simply not appear
    }
  }

  /**
   * Watch appointments and fetch session status when appointments change
   */
  watch(
    () => appointmentsStore.appointments,
    (newAppointments) => {
      if (newAppointments.length > 0) {
        // Fetch session status whenever appointments are loaded
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

    // Status-based colors with time awareness
    const colors: Record<string, string> = {
      completed: '#059669', // emerald-600
      cancelled: '#94a3b8', // slate-400
      no_show: '#f97316', // orange-500
      scheduled: isPast ? '#f59e0b' : '#10b981', // amber-500 : emerald-500
      confirmed: isPast ? '#f59e0b' : '#10b981', // amber-500 : emerald-500
    }

    return colors[appointment.status] || colors.scheduled
  }

  /**
   * Get event title with status and session indicators
   */
  function getEventTitle(appointment: AppointmentListItem): string {
    // Status emoji indicators
    const statusEmoji: Record<string, string> = {
      completed: '✓',
      cancelled: '✕',
      no_show: '⚠',
    }

    const statusIndicator = statusEmoji[appointment.status] || ''

    // Session indicator
    const sessionStatus = sessionStatusMap.value.get(appointment.id)
    const sessionIndicator = sessionStatus?.hasSession ? ' 📄' : ''

    // Client name
    const clientName =
      appointment.client?.full_name || `Client ${appointment.client_id.slice(0, 8)}`

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

      // Get event color and title
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
      // This will trigger the computed setter, which stores only the ID
      selectedAppointment.value = appointment
    }
  }

  return {
    // State
    selectedAppointment,
    calendarEvents,
    sessionStatusMap,

    // Methods
    handleEventClick,
    fetchSessionStatus,
  }
}
