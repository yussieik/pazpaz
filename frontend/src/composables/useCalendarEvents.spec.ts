import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useCalendarEvents } from './useCalendarEvents'
import { useAppointmentsStore } from '@/stores/appointments'
import type { AppointmentListItem } from '@/types/calendar'

/**
 * Tests for useCalendarEvents composable
 *
 * Specifically tests the bug fix where selectedAppointment was storing
 * a stale reference instead of reactively fetching from the store.
 */
describe('useCalendarEvents - Reactive Data Flow', () => {
  let pinia: ReturnType<typeof createPinia>
  let appointmentsStore: ReturnType<typeof useAppointmentsStore>

  const mockAppointment: AppointmentListItem = {
    id: 'apt-1',
    workspace_id: 'ws-1',
    client_id: 'client-1',
    scheduled_start: '2024-01-15T14:00:00Z', // 2:00 PM
    scheduled_end: '2024-01-15T15:00:00Z', // 3:00 PM
    location_type: 'clinic',
    location_details: 'Room 101',
    status: 'scheduled',
    notes: null,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    client: {
      id: 'client-1',
      first_name: 'John',
      last_name: 'Doe',
      full_name: 'John Doe',
    },
  }

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    appointmentsStore = useAppointmentsStore()
    appointmentsStore.appointments = [mockAppointment]
  })

  describe('Bug Fix: Reactive selectedAppointment', () => {
    it('should fetch fresh data from store when selectedAppointment is accessed', () => {
      const { selectedAppointment, handleEventClick } = useCalendarEvents()

      // Simulate event click
      handleEventClick({
        event: { id: 'apt-1' },
      } as any)

      // Initial appointment is selected
      expect(selectedAppointment.value?.id).toBe('apt-1')
      expect(selectedAppointment.value?.scheduled_start).toBe('2024-01-15T14:00:00Z')

      // Simulate store update (like after drag-drop reschedule)
      const updatedAppointment: AppointmentListItem = {
        ...mockAppointment,
        scheduled_start: '2024-01-15T15:30:00Z', // 3:30 PM - NEW TIME
        scheduled_end: '2024-01-15T16:30:00Z', // 4:30 PM - NEW TIME
        updated_at: '2024-01-15T15:35:00Z',
      }

      // Replace appointment in store (simulates updateAppointment success)
      appointmentsStore.appointments = [updatedAppointment]

      // BUG FIX VERIFICATION: selectedAppointment should now return updated data
      // Before fix: this would return old data (2:00 PM)
      // After fix: this returns fresh data from store (3:30 PM)
      expect(selectedAppointment.value?.scheduled_start).toBe('2024-01-15T15:30:00Z')
      expect(selectedAppointment.value?.scheduled_end).toBe('2024-01-15T16:30:00Z')

      // Ensure it's NOT returning stale data
      expect(selectedAppointment.value?.scheduled_start).not.toBe(
        '2024-01-15T14:00:00Z'
      )
    })

    it('should return null when selected appointment is deleted from store', () => {
      const { selectedAppointment, handleEventClick } = useCalendarEvents()

      // Select appointment
      handleEventClick({
        event: { id: 'apt-1' },
      } as any)

      expect(selectedAppointment.value?.id).toBe('apt-1')

      // Delete appointment from store
      appointmentsStore.appointments = []

      // selectedAppointment should return null (appointment no longer exists)
      expect(selectedAppointment.value).toBeNull()
    })

    it('should update when setting selectedAppointment to null', () => {
      const { selectedAppointment, handleEventClick } = useCalendarEvents()

      // Select appointment
      handleEventClick({
        event: { id: 'apt-1' },
      } as any)

      expect(selectedAppointment.value).not.toBeNull()

      // Clear selection
      selectedAppointment.value = null

      expect(selectedAppointment.value).toBeNull()
    })

    it('should update when setting selectedAppointment to a new appointment', () => {
      const secondAppointment: AppointmentListItem = {
        ...mockAppointment,
        id: 'apt-2',
        scheduled_start: '2024-01-15T16:00:00Z',
        scheduled_end: '2024-01-15T17:00:00Z',
      }

      appointmentsStore.appointments = [mockAppointment, secondAppointment]

      const { selectedAppointment } = useCalendarEvents()

      // Set to first appointment
      selectedAppointment.value = mockAppointment

      expect(selectedAppointment.value?.id).toBe('apt-1')

      // Set to second appointment
      selectedAppointment.value = secondAppointment

      expect(selectedAppointment.value?.id).toBe('apt-2')
      expect(selectedAppointment.value?.scheduled_start).toBe('2024-01-15T16:00:00Z')
    })

    it('should reflect store updates even when appointment object is completely replaced', () => {
      const { selectedAppointment, handleEventClick } = useCalendarEvents()

      // Select appointment
      handleEventClick({
        event: { id: 'apt-1' },
      } as any)

      const initialSelectedStart = selectedAppointment.value?.scheduled_start
      expect(initialSelectedStart).toBe('2024-01-15T14:00:00Z')

      // Create completely new appointment object with same ID (simulates API response)
      const completelyNewObject: AppointmentListItem = {
        id: 'apt-1', // SAME ID
        workspace_id: 'ws-1',
        client_id: 'client-1',
        scheduled_start: '2024-01-15T18:00:00Z', // Different time
        scheduled_end: '2024-01-15T19:00:00Z',
        location_type: 'video_call', // Different location
        location_details: 'Zoom',
        status: 'scheduled',
        notes: 'Updated notes',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-15T18:00:00Z',
        client: {
          id: 'client-1',
          first_name: 'John',
          last_name: 'Doe',
          full_name: 'John Doe',
        },
      }

      // Replace in store (this is what happens in store.updateAppointment)
      appointmentsStore.appointments = [completelyNewObject]

      // Computed property should return fresh object from store
      expect(selectedAppointment.value?.scheduled_start).toBe('2024-01-15T18:00:00Z')
      expect(selectedAppointment.value?.location_type).toBe('video_call')
      expect(selectedAppointment.value?.notes).toBe('Updated notes')
    })
  })

  describe('Event Click Handling', () => {
    it('should set selectedAppointment when handleEventClick is called', () => {
      const { selectedAppointment, handleEventClick } = useCalendarEvents()

      expect(selectedAppointment.value).toBeNull()

      handleEventClick({
        event: { id: 'apt-1' },
      } as any)

      expect(selectedAppointment.value?.id).toBe('apt-1')
    })

    it('should handle clicking non-existent appointment gracefully', () => {
      const { selectedAppointment, handleEventClick } = useCalendarEvents()

      handleEventClick({
        event: { id: 'non-existent-id' },
      } as any)

      // Should not set selectedAppointment if appointment not found
      expect(selectedAppointment.value).toBeNull()
    })
  })

  describe('Calendar Events Transformation', () => {
    it('should transform appointments to FullCalendar events', () => {
      const { calendarEvents } = useCalendarEvents()

      expect(calendarEvents.value).toHaveLength(1)
      expect(calendarEvents.value[0]).toMatchObject({
        id: 'apt-1',
        title: 'John Doe',
        start: '2024-01-15T14:00:00Z',
        end: '2024-01-15T15:00:00Z',
      })
    })

    it('should update calendar events when store updates', () => {
      const { calendarEvents } = useCalendarEvents()

      expect(calendarEvents.value[0].start).toBe('2024-01-15T14:00:00Z')

      // Update store
      const updatedAppointment: AppointmentListItem = {
        ...mockAppointment,
        scheduled_start: '2024-01-15T16:00:00Z',
        scheduled_end: '2024-01-15T17:00:00Z',
      }

      appointmentsStore.appointments = [updatedAppointment]

      // Calendar events should reflect updated times
      expect(calendarEvents.value[0].start).toBe('2024-01-15T16:00:00Z')
      expect(calendarEvents.value[0].end).toBe('2024-01-15T17:00:00Z')
    })
  })
})
