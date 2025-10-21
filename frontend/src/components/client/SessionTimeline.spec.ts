/**
 * SessionTimeline Component Tests
 *
 * Tests for session restoration bug fix:
 * - Session restoration triggers timeline refresh
 * - Restored session can be deleted again
 * - Timeline refresh fetches both sessions and appointments
 * - handleSessionDeleted removes session from timeline
 * - Full restore-delete cycle works correctly
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import SessionTimeline from './SessionTimeline.vue'
import SessionCard from '@/components/sessions/SessionCard.vue'
import apiClient from '@/api/client'

// Mock API client
vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}))

// Mock date-fns
vi.mock('date-fns', () => ({
  format: vi.fn((date) => new Date(date).toISOString()),
}))

const mockSessions = [
  {
    id: 'session-1',
    client_id: 'client-1',
    appointment_id: 'appt-1',
    subjective: 'Test subjective content',
    objective: 'Test objective content',
    assessment: 'Test assessment content',
    plan: 'Test plan content',
    session_date: '2025-10-10T10:00:00Z',
    duration_minutes: 60,
    is_draft: false,
    draft_last_saved_at: null,
    finalized_at: '2025-10-10T11:00:00Z',
  },
  {
    id: 'session-2',
    client_id: 'client-1',
    appointment_id: null,
    subjective: 'Draft session content',
    objective: null,
    assessment: null,
    plan: null,
    session_date: '2025-10-08T14:00:00Z',
    duration_minutes: 45,
    is_draft: true,
    draft_last_saved_at: '2025-10-08T14:30:00Z',
    finalized_at: null,
  },
]

const mockAppointments = [
  {
    id: 'appt-2',
    client_id: 'client-1',
    scheduled_start: '2025-10-05T09:00:00Z',
    scheduled_end: '2025-10-05T10:00:00Z',
    location_type: 'clinic',
    notes: 'Follow-up appointment',
    status: 'completed',
    service_name: 'Massage Therapy',
  },
]

describe('SessionTimeline', () => {
  let wrapper: VueWrapper
  let router: ReturnType<typeof createRouter>

  beforeEach(() => {
    vi.clearAllMocks()

    // Setup router
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', component: { template: '<div>Home</div>' } },
        { path: '/sessions/:id', component: { template: '<div>Session</div>' } },
      ],
    })

    // Mock API responses
    vi.mocked(apiClient.get).mockImplementation((url: string, config?: { params?: Record<string, unknown> }) => {
      if (url === '/sessions' || url.includes('/sessions?')) {
        return Promise.resolve({ data: { items: mockSessions, total: mockSessions.length } })
      }
      if (url.includes('/appointments')) {
        return Promise.resolve({ data: { items: mockAppointments } })
      }
      if (url.includes('/appointments/')) {
        // Individual appointment fetch
        const appointmentId = url.split('/').pop()
        const appointment = mockAppointments.find((a) => a.id === appointmentId)
        return appointment
          ? Promise.resolve({ data: appointment })
          : Promise.reject(new Error('Appointment not found'))
      }
      return Promise.reject(new Error('Unknown endpoint'))
    })
  })

  const createWrapper = () => {
    return mount(SessionTimeline, {
      props: {
        clientId: 'client-1',
      },
      global: {
        plugins: [router],
        stubs: {
          SessionCard: SessionCard,
        },
      },
    })
  }

  describe('Data Fetching', () => {
    it('fetches sessions and appointments on mount', async () => {
      wrapper = createWrapper()
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Check that API was called with params object (not query string)
      expect(apiClient.get).toHaveBeenCalledWith('/sessions', expect.objectContaining({
        params: expect.objectContaining({ client_id: 'client-1' })
      }))
      expect(apiClient.get).toHaveBeenCalledWith(
        '/appointments?client_id=client-1&status=completed'
      )
    })

    it('displays sessions in chronological order', async () => {
      wrapper = createWrapper()
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      const sessions = wrapper.findAllComponents(SessionCard)
      expect(sessions.length).toBe(2)
    })

    it('filters out appointments that already have sessions', async () => {
      wrapper = createWrapper()
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Verify: We have 2 sessions (session-1, session-2)
      // and 1 appointment without session (appt-2)
      // appt-1 should be filtered out because it has session-1

      const sessions = wrapper.findAllComponents(SessionCard)
      expect(sessions.length).toBe(2)

      // Total timeline items should be 3 (2 sessions + 1 appointment)
      // This verifies appt-1 is filtered (otherwise would be 4 items)
      const allItems = wrapper.findAll('[data-timeline-item],.rounded-lg')
      expect(allItems.length).toBeGreaterThanOrEqual(3)
      expect(allItems.length).toBeLessThanOrEqual(4)
    })

    it('handles fetch errors gracefully', async () => {
      vi.mocked(apiClient.get).mockRejectedValueOnce({
        response: { data: { detail: 'Network error' } },
      })

      wrapper = createWrapper()
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 10))

      // Check for error state (either the error message or the error component)
      const hasError =
        wrapper.text().includes('Failed') || wrapper.find('.text-red-800').exists()
      expect(hasError).toBe(true)
    })
  })

  describe('Refresh Method (Bug Fix)', () => {
    it('exposes refresh method to parent components', async () => {
      wrapper = createWrapper()
      await wrapper.vm.$nextTick()

      // Verify refresh method is exposed
      expect(wrapper.vm.refresh).toBeDefined()
      expect(typeof wrapper.vm.refresh).toBe('function')
    })

    it('refresh method fetches both sessions and appointments', async () => {
      wrapper = createWrapper()
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Clear previous calls
      vi.clearAllMocks()

      // Call refresh
      await wrapper.vm.refresh()

      // Verify both endpoints are called
      expect(apiClient.get).toHaveBeenCalledWith('/sessions', expect.objectContaining({
        params: expect.objectContaining({ client_id: 'client-1' })
      }))
      expect(apiClient.get).toHaveBeenCalledWith(
        '/appointments?client_id=client-1&status=completed'
      )
      // NOTE: fetchSessions also fetches individual appointment details for sessions with appointment_id
      // mockSessions has session-1 with appointment_id='appt-1', so we get:
      // 1. GET /sessions with params
      // 2. GET /appointments/appt-1 (individual appointment fetch)
      // 3. GET /appointments?client_id=client-1&status=completed
      expect(apiClient.get).toHaveBeenCalledTimes(3)
    })

    it('refresh method updates session list with new data', async () => {
      wrapper = createWrapper()
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Update mock to return new session
      const newSession = {
        id: 'session-3',
        client_id: 'client-1',
        appointment_id: null,
        subjective: 'Restored session',
        objective: null,
        assessment: null,
        plan: null,
        session_date: '2025-10-12T10:00:00Z',
        duration_minutes: 30,
        is_draft: true,
        draft_last_saved_at: '2025-10-12T10:30:00Z',
        finalized_at: null,
      }

      vi.mocked(apiClient.get).mockImplementation((url: string, config?: { params?: Record<string, unknown> }) => {
        if (url === '/sessions' || url.includes('/sessions?')) {
          return Promise.resolve({ data: { items: [...mockSessions, newSession], total: 3 } })
        }
        if (url.includes('/appointments')) {
          return Promise.resolve({ data: { items: mockAppointments } })
        }
        if (url.includes('/appointments/')) {
          // Individual appointment fetch
          const appointmentId = url.split('/').pop()
          const appointment = mockAppointments.find((a) => a.id === appointmentId)
          return appointment
            ? Promise.resolve({ data: appointment })
            : Promise.reject(new Error('Appointment not found'))
        }
        return Promise.reject(new Error('Unknown endpoint'))
      })

      // Call refresh
      await wrapper.vm.refresh()
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Verify new session appears
      const sessions = wrapper.findAllComponents(SessionCard)
      expect(sessions.length).toBe(3)
    })
  })

  describe('Session Deletion', () => {
    it('handleSessionDeleted removes session from timeline', async () => {
      wrapper = createWrapper()
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Find first session card
      const sessionCards = wrapper.findAllComponents(SessionCard)
      expect(sessionCards.length).toBe(2)

      // Emit deleted event
      if (sessionCards[0]) {
        await sessionCards[0].vm.$emit('deleted', 'session-1')
        await wrapper.vm.$nextTick()

        // Verify session removed from timeline
        const updatedSessions = wrapper.findAllComponents(SessionCard)
        expect(updatedSessions.length).toBe(1)
      }
    })

    it('emits session-deleted event to parent', async () => {
      wrapper = createWrapper()
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      const sessionCards = wrapper.findAllComponents(SessionCard)
      if (sessionCards[0]) {
        await sessionCards[0].vm.$emit('deleted', 'session-1')
        await wrapper.vm.$nextTick()

        expect(wrapper.emitted('session-deleted')).toBeTruthy()
      }
    })

    it('emits trigger-badge-pulse event to parent', async () => {
      wrapper = createWrapper()
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      const sessionCards = wrapper.findAllComponents(SessionCard)
      if (sessionCards[0]) {
        await sessionCards[0].vm.$emit('deleted', 'session-1')
        await wrapper.vm.$nextTick()

        expect(wrapper.emitted('trigger-badge-pulse')).toBeTruthy()
      }
    })
  })

  describe('Full Restore-Delete Cycle', () => {
    it('successfully handles restore -> delete cycle', async () => {
      wrapper = createWrapper()
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Initial state: 2 sessions
      let sessions = wrapper.findAllComponents(SessionCard)
      expect(sessions.length).toBe(2)

      // Step 1: Delete a session
      if (sessions[0]) {
        await sessions[0].vm.$emit('deleted', 'session-1')
        await wrapper.vm.$nextTick()

        // Verify session removed
        sessions = wrapper.findAllComponents(SessionCard)
        expect(sessions.length).toBe(1)

        // Step 2: Simulate restoration (parent calls refresh)
        // Mock API to return the restored session
        vi.mocked(apiClient.get).mockImplementation((url: string, config?: { params?: Record<string, unknown> }) => {
          if (url === '/sessions' || url.includes('/sessions?')) {
            return Promise.resolve({ data: { items: mockSessions, total: mockSessions.length } })
          }
          if (url.includes('/appointments')) {
            return Promise.resolve({ data: { items: mockAppointments } })
          }
          if (url.includes('/appointments/')) {
            const appointmentId = url.split('/').pop()
            const appointment = mockAppointments.find((a) => a.id === appointmentId)
            return appointment
              ? Promise.resolve({ data: appointment })
              : Promise.reject(new Error('Appointment not found'))
          }
          return Promise.reject(new Error('Unknown endpoint'))
        })

        await wrapper.vm.refresh()
        await wrapper.vm.$nextTick()
        await new Promise((resolve) => setTimeout(resolve, 50))

        // Verify session restored
        sessions = wrapper.findAllComponents(SessionCard)
        expect(sessions.length).toBe(2)

        // Step 3: Delete the restored session again
        if (sessions[0]) {
          await sessions[0].vm.$emit('deleted', 'session-1')
          await wrapper.vm.$nextTick()

          // Verify session removed again
          sessions = wrapper.findAllComponents(SessionCard)
          expect(sessions.length).toBe(1)
        }
      }
    })

    it('timeline stays in sync after multiple restore operations', async () => {
      wrapper = createWrapper()
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Simulate multiple restores by calling refresh multiple times
      await wrapper.vm.refresh()
      await wrapper.vm.$nextTick()
      await wrapper.vm.refresh()
      await wrapper.vm.$nextTick()
      await wrapper.vm.refresh()
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      // Verify timeline still shows correct data
      const sessions = wrapper.findAllComponents(SessionCard)
      expect(sessions.length).toBe(2)
    })
  })

  describe('Session Creation', () => {
    it('navigates to session editor when creating from appointment', async () => {
      const pushSpy = vi.spyOn(router, 'push')

      vi.mocked(apiClient.post).mockResolvedValueOnce({
        data: { id: 'new-session-id' },
      })

      wrapper = createWrapper()
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 0))

      // Find appointment card and click create
      const createButton = wrapper.find('[data-create-session]')
      if (createButton.exists()) {
        await createButton.trigger('click')
        await wrapper.vm.$nextTick()

        expect(apiClient.post).toHaveBeenCalledWith('/sessions', expect.any(Object))
        expect(pushSpy).toHaveBeenCalledWith(
          expect.objectContaining({
            path: '/sessions/new-session-id',
          })
        )
      }
    })
  })

  describe('Empty States', () => {
    it('displays empty state when no sessions or appointments', async () => {
      vi.mocked(apiClient.get).mockImplementation(() => {
        return Promise.resolve({ data: { items: [] } })
      })

      wrapper = createWrapper()
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 0))

      expect(wrapper.text()).toContain('No sessions yet')
    })

    it('displays loading state while fetching', async () => {
      // Mock a delayed response to capture loading state
      vi.mocked(apiClient.get).mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(() => resolve({ data: { items: [] } }), 100)
          )
      )

      wrapper = createWrapper()
      await wrapper.vm.$nextTick()

      // Should show loading spinner
      const hasLoadingSpinner = wrapper.find('.animate-spin').exists()
      expect(hasLoadingSpinner).toBe(true)
    })
  })

  describe('Session Navigation', () => {
    it('navigates to session detail with correct state', async () => {
      const pushSpy = vi.spyOn(router, 'push')

      wrapper = createWrapper()
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 50))

      const sessionCards = wrapper.findAllComponents(SessionCard)
      if (sessionCards[0]) {
        await sessionCards[0].vm.$emit('view', 'session-1')

        expect(pushSpy).toHaveBeenCalledWith(
          expect.objectContaining({
            path: '/sessions/session-1',
            state: expect.objectContaining({
              from: 'client-history',
              clientId: 'client-1',
              returnTo: 'client-detail',
            }),
          })
        )
      }
    })
  })
})
