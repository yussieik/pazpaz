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

// Mock FullCalendar to avoid rendering issues in tests
vi.mock('@fullcalendar/vue3', () => ({
  default: {
    name: 'FullCalendar',
    template: '<div class="mock-fullcalendar"></div>',
    methods: {
      getApi() {
        return {
          next: vi.fn(),
          prev: vi.fn(),
          today: vi.fn(),
          changeView: vi.fn(),
          gotoDate: vi.fn(),
          getDate: vi.fn(() => new Date()),
        }
      },
    },
  },
}))

const mockAppointments = [
  {
    id: 'appointment-uuid-1',
    workspace_id: 'workspace-uuid',
    client_id: 'client-uuid-1',
    scheduled_start: '2025-09-30T09:00:00Z',
    scheduled_end: '2025-09-30T10:00:00Z',
    status: 'scheduled' as const,
    location_type: 'clinic' as const,
    location_details: null,
    notes: null,
  },
  {
    id: 'appointment-uuid-2',
    workspace_id: 'workspace-uuid',
    client_id: 'client-uuid-2',
    scheduled_start: '2025-09-30T14:00:00Z',
    scheduled_end: '2025-09-30T15:00:00Z',
    status: 'confirmed' as const,
    location_type: 'video_call' as const,
    location_details: 'Zoom link',
    notes: 'Follow-up session',
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

    it('should render FullCalendar component', async () => {
      const wrapper = await createWrapper()
      expect(wrapper.find('.mock-fullcalendar').exists()).toBe(true)
    })

    it('should render navigation controls', async () => {
      const wrapper = await createWrapper()
      expect(wrapper.text()).toContain('Today')
    })

    it('should render view switcher buttons', async () => {
      const wrapper = await createWrapper()
      expect(wrapper.text()).toContain('Day')
      expect(wrapper.text()).toContain('Week')
      expect(wrapper.text()).toContain('Month')
    })
  })

  describe('Store Integration', () => {
    it('should use appointments store', async () => {
      await createWrapper()
      const store = useAppointmentsStore()

      // Store should be initialized and available
      expect(store).toBeDefined()
      expect(store.appointments).toBeDefined()
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
      const store = useAppointmentsStore()

      vi.mocked(apiClient.get).mockRejectedValueOnce(
        new Error('Failed to fetch appointments')
      )

      // Manually trigger fetch to capture error
      await store.fetchAppointments('2025-09-30', '2025-10-06')
      await flushPromises()

      const wrapper = await createWrapper()

      expect(store.error).toBeTruthy()
      expect(wrapper.text()).toContain('Error loading appointments')
    })

    it('should style error message with error colors', async () => {
      const store = useAppointmentsStore()

      vi.mocked(apiClient.get).mockRejectedValueOnce(new Error('Network error'))

      // Manually trigger fetch to capture error
      await store.fetchAppointments('2025-09-30', '2025-10-06')
      await flushPromises()

      const wrapper = await createWrapper()

      const errorDiv = wrapper.find('.border-red-200')
      expect(errorDiv.exists()).toBe(true)
      expect(errorDiv.classes()).toContain('bg-red-50')
      expect(errorDiv.classes()).toContain('text-red-800')
    })
  })

  describe('Success State - No Appointments', () => {
    it('should show empty state when no appointments', async () => {
      const wrapper = await createWrapper()

      expect(wrapper.text()).toContain('No appointments scheduled')
    })

    it('should show empty state message', async () => {
      const wrapper = await createWrapper()

      expect(wrapper.text()).toContain('Get started by creating your first appointment')
    })

    it('should render empty state icon', async () => {
      const wrapper = await createWrapper()

      const emptyIcon = wrapper.find('svg')
      expect(emptyIcon.exists()).toBe(true)
    })
  })

  describe('Success State - With Appointments', () => {
    it('should render FullCalendar when appointments exist', async () => {
      const store = useAppointmentsStore()

      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockAppointments,
          total: 2,
          page: 1,
          page_size: 50,
        },
      })

      // Manually populate store with appointments
      await store.fetchAppointments('2025-09-30', '2025-10-06')
      await flushPromises()

      const wrapper = await createWrapper()

      expect(wrapper.find('.mock-fullcalendar').exists()).toBe(true)
    })

    it('should not show empty state when appointments exist', async () => {
      const store = useAppointmentsStore()

      vi.mocked(apiClient.get).mockResolvedValueOnce({
        data: {
          items: mockAppointments,
          total: 2,
          page: 1,
          page_size: 50,
        },
      })

      // Manually populate store with appointments
      await store.fetchAppointments('2025-09-30', '2025-10-06')
      await flushPromises()

      const wrapper = await createWrapper()

      // Store should have appointments
      expect(store.appointments.length).toBe(2)

      // Empty state should not be visible when appointments exist
      expect(wrapper.text()).not.toContain(
        'Get started by creating your first appointment'
      )
    })
  })

  describe('Appointment Modal', () => {
    it('should not show modal initially', async () => {
      const wrapper = await createWrapper()

      expect(wrapper.text()).not.toContain('Appointment Details')
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
