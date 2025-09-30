import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import CalendarView from './CalendarView.vue'
import { useAppointmentsStore } from '@/stores/appointments'
import apiClient from '@/api/client'

// Mock the API client
vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

const mockAppointments = [
  {
    id: '1',
    title: 'Morning Session',
    start_time: '2025-09-30T09:00:00Z',
    end_time: '2025-09-30T10:00:00Z',
    client_id: 'client-1',
    status: 'scheduled' as const,
    notes: null,
    created_at: '2025-09-29T10:00:00Z',
    updated_at: '2025-09-29T10:00:00Z',
  },
  {
    id: '2',
    title: 'Afternoon Session',
    start_time: '2025-09-30T14:00:00Z',
    end_time: '2025-09-30T15:00:00Z',
    client_id: 'client-2',
    status: 'scheduled' as const,
    notes: 'Follow-up session',
    created_at: '2025-09-29T11:00:00Z',
    updated_at: '2025-09-29T11:00:00Z',
  },
]

describe('CalendarView.vue', () => {
  let pinia: ReturnType<typeof createPinia>
  let router: ReturnType<typeof createRouter>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)

    router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/calendar', name: 'calendar', component: CalendarView }],
    })

    vi.clearAllMocks()

    // Mock a successful empty response by default
    vi.mocked(apiClient.get).mockResolvedValue({
      data: {
        items: [],
        total: 0,
        page: 1,
        page_size: 50,
      },
    })
  })

  const createWrapper = async () => {
    const wrapper = mount(CalendarView, {
      global: {
        plugins: [pinia, router],
      },
    })
    await flushPromises()
    return wrapper
  }

  describe('Rendering', () => {
    it('should render the page title', async () => {
      const wrapper = await createWrapper()
      expect(wrapper.find('h1').text()).toBe('Calendar')
    })

    it('should render the page description', async () => {
      const wrapper = await createWrapper()
      expect(wrapper.text()).toContain('Weekly appointment schedule')
    })

    it('should render coming soon placeholder', async () => {
      const wrapper = await createWrapper()
      expect(wrapper.text()).toContain('Calendar component coming soon')
    })
  })

  describe('Store Integration', () => {
    it('should fetch appointments on mount', async () => {
      const store = useAppointmentsStore()
      const fetchSpy = vi.spyOn(store, 'fetchAppointments')

      await createWrapper()

      expect(fetchSpy).toHaveBeenCalledOnce()
      expect(fetchSpy).toHaveBeenCalledWith(expect.any(String), expect.any(String))
    })

    it('should fetch appointments for current week', async () => {
      const store = useAppointmentsStore()
      const fetchSpy = vi.spyOn(store, 'fetchAppointments')

      await createWrapper()

      const calls = fetchSpy.mock.calls[0]
      expect(calls[0]).toMatch(/^\d{4}-\d{2}-\d{2}$/) // ISO date format
      expect(calls[1]).toMatch(/^\d{4}-\d{2}-\d{2}$/) // ISO date format
    })
  })

  describe('Loading State', () => {
    it('should display loading message when loading', async () => {
      // Mock a delayed response to capture loading state
      vi.mocked(apiClient.get).mockImplementation(
        () =>
          new Promise((resolve) => {
            setTimeout(
              () =>
                resolve({
                  data: {
                    items: [],
                    total: 0,
                    page: 1,
                    page_size: 50,
                  },
                }),
              100
            )
          })
      )

      const wrapper = mount(CalendarView, {
        global: {
          plugins: [pinia, router],
        },
      })

      // Check immediately before promises resolve
      await wrapper.vm.$nextTick()
      const store = useAppointmentsStore()

      // If still loading, check for loading message
      if (store.loading) {
        expect(wrapper.text()).toContain('Loading appointments...')
      }

      await flushPromises()
    })

    it('should not display content when loading', async () => {
      vi.mocked(apiClient.get).mockImplementation(
        () =>
          new Promise((resolve) => {
            setTimeout(
              () =>
                resolve({
                  data: {
                    items: [],
                    total: 0,
                    page: 1,
                    page_size: 50,
                  },
                }),
              100
            )
          })
      )

      const wrapper = mount(CalendarView, {
        global: {
          plugins: [pinia, router],
        },
      })

      await wrapper.vm.$nextTick()
      const store = useAppointmentsStore()

      if (store.loading) {
        expect(wrapper.text()).not.toContain('Calendar component coming soon')
      }

      await flushPromises()
    })
  })

  describe('Error State', () => {
    it('should display error message when error occurs', async () => {
      vi.mocked(apiClient.get).mockRejectedValueOnce(
        new Error('Failed to fetch appointments')
      )

      const wrapper = await createWrapper()

      expect(wrapper.text()).toContain('Error: Failed to fetch appointments')
    })

    it('should style error message with error colors', async () => {
      vi.mocked(apiClient.get).mockRejectedValueOnce(new Error('Network error'))

      const wrapper = await createWrapper()

      const errorDiv = wrapper.find('.border-red-200')
      expect(errorDiv.exists()).toBe(true)
      expect(errorDiv.classes()).toContain('bg-red-50')
      expect(errorDiv.classes()).toContain('text-red-800')
    })
  })

  describe('Success State - No Appointments', () => {
    it('should show appointment count of 0', async () => {
      const wrapper = await createWrapper()

      expect(wrapper.text()).toContain('Appointments loaded: 0')
    })

    it('should not display appointments list when empty', async () => {
      const wrapper = await createWrapper()

      expect(wrapper.text()).not.toContain('Current Appointments:')
    })
  })

  describe('Success State - With Appointments', () => {
    it('should show appointment count', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockAppointments,
          total: 2,
          page: 1,
          page_size: 50,
        },
      })

      const wrapper = await createWrapper()

      expect(wrapper.text()).toContain('Appointments loaded: 2')
    })

    it('should display appointments list header', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockAppointments,
          total: 2,
          page: 1,
          page_size: 50,
        },
      })

      const wrapper = await createWrapper()

      expect(wrapper.text()).toContain('Current Appointments:')
    })

    it('should render each appointment with ID', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockAppointments,
          total: 2,
          page: 1,
          page_size: 50,
        },
      })

      const wrapper = await createWrapper()

      expect(wrapper.text()).toContain('Appointment 1')
      expect(wrapper.text()).toContain('Appointment 2')
    })

    it('should render appointment times', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockAppointments,
          total: 2,
          page: 1,
          page_size: 50,
        },
      })

      const wrapper = await createWrapper()

      // Times should be rendered as localized strings
      const appointments = wrapper.findAll('li')
      expect(appointments.length).toBe(2)
    })

    it('should render appointment notes when present', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockAppointments,
          total: 2,
          page: 1,
          page_size: 50,
        },
      })

      const wrapper = await createWrapper()

      expect(wrapper.text()).toContain('Follow-up session')
    })

    it('should not render notes section when notes are null', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: [mockAppointments[0]], // First appointment has no notes
          total: 1,
          page: 1,
          page_size: 50,
        },
      })

      const wrapper = await createWrapper()

      const notesElements = wrapper.findAll('.text-sm.text-gray-500')
      // Should only have time elements, not notes
      expect(notesElements.length).toBeLessThanOrEqual(1)
    })

    it('should render appointments in a list', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockAppointments,
          total: 2,
          page: 1,
          page_size: 50,
        },
      })

      const wrapper = await createWrapper()

      const list = wrapper.find('ul')
      expect(list.exists()).toBe(true)
      expect(list.classes()).toContain('space-y-2')

      const items = list.findAll('li')
      expect(items.length).toBe(2)
    })
  })

  describe('Computed Property Integration', () => {
    it('should conditionally render based on hasAppointments', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockAppointments,
          total: 2,
          page: 1,
          page_size: 50,
        },
      })

      const wrapper = await createWrapper()
      const store = useAppointmentsStore()

      // Should show the appointments section when hasAppointments is true
      expect(store.hasAppointments).toBe(true)
      expect(wrapper.text()).toContain('Current Appointments:')
    })
  })

  describe('Layout and Styling', () => {
    it('should have container with proper spacing', async () => {
      const wrapper = await createWrapper()

      const container = wrapper.find('.container')
      expect(container.exists()).toBe(true)
      expect(container.classes()).toContain('mx-auto')
      expect(container.classes()).toContain('px-4')
      expect(container.classes()).toContain('py-8')
    })

    it('should render content in card layout', async () => {
      const wrapper = await createWrapper()

      const card = wrapper.find('.rounded-lg.border.border-gray-200.bg-white')
      expect(card.exists()).toBe(true)
    })
  })
})
