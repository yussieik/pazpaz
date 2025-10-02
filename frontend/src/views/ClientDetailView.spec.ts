import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import ClientDetailView from './ClientDetailView.vue'
import { useClientsStore } from '@/stores/clients'
import { createPinia, setActivePinia } from 'pinia'
import type { AppointmentListItem } from '@/types/calendar'
import type { Client } from '@/types/client'

// Mock API client
vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

describe('ClientDetailView - Smart Back Navigation', () => {
  let router: ReturnType<typeof createRouter>
  let pinia: ReturnType<typeof createPinia>
  let mockClient: Client

  beforeEach(() => {
    // Reset everything
    pinia = createPinia()
    setActivePinia(pinia)

    // Reset history.state
    Object.defineProperty(window.history, 'state', {
      value: null,
      writable: true,
      configurable: true,
    })

    // Clear sessionStorage
    sessionStorage.clear()

    // Mock client data
    mockClient = {
      id: 'client-123',
      workspace_id: 'workspace-123',
      first_name: 'John',
      last_name: 'Doe',
      full_name: 'John Doe',
      email: 'john@example.com',
      phone: '555-1234',
      date_of_birth: null,
      address: null,
      emergency_contact_name: null,
      emergency_contact_phone: null,
      medical_history: null,
      notes: null,
    }

    // Setup router with required routes
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', name: 'calendar', component: { template: '<div>Calendar</div>' } },
        {
          path: '/clients',
          name: 'clients',
          component: { template: '<div>Clients</div>' },
        },
        {
          path: '/clients/:id',
          name: 'client-detail',
          component: ClientDetailView,
        },
        {
          path: '/settings',
          name: 'settings',
          component: { template: '<div>Settings</div>' },
        },
      ],
    })

    // Add navigation guard to track previous route (same as in real router)
    router.beforeEach((to, from) => {
      to.meta.from = from.path
    })

    // Mock the clients store
    const clientsStore = useClientsStore()
    clientsStore.currentClient = mockClient
    vi.spyOn(clientsStore, 'fetchClient').mockResolvedValue(mockClient)
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  /**
   * Test Case 1: Back to Appointment
   * When navigating from appointment modal with appointment state
   */
  it('shows "Back to Appointment" when navigating from appointment modal', async () => {
    // Simulate navigation from appointment with state
    const appointmentData: AppointmentListItem = {
      id: 'apt-123',
      workspace_id: 'workspace-123',
      client_id: 'client-123',
      client: {
        id: 'client-123',
        first_name: 'John',
        last_name: 'Doe',
        full_name: 'John Doe',
      },
      scheduled_start: '2025-03-15T14:00:00Z',
      scheduled_end: '2025-03-15T15:00:00Z',
      status: 'scheduled',
      location_type: 'clinic',
      location_details: null,
      notes: null,
    }

    // Mock history.state to simulate navigation with state
    // Vue Router's memory history doesn't support state like browser history,
    // so we mock it directly
    Object.defineProperty(window.history, 'state', {
      value: { appointment: appointmentData },
      writable: true,
      configurable: true,
    })

    await router.push({
      name: 'client-detail',
      params: { id: 'client-123' },
    })

    const wrapper = mount(ClientDetailView, {
      global: {
        plugins: [pinia, router],
      },
    })

    await flushPromises()
    await wrapper.vm.$nextTick()

    // Should show "Back to Appointment"
    const backButtons = wrapper.findAll('button')
    const backButton = backButtons.find((btn) => btn.text().includes('Back to'))
    expect(backButton).toBeDefined()
    expect(backButton?.text()).toContain('Back to Appointment')

    // Should show contextual banner
    expect(wrapper.html()).toContain('Viewing from appointment')
    expect(wrapper.html()).toContain('Return to appointment details')
    expect(wrapper.html()).toContain('Mar 15') // Contains date
    expect(wrapper.html()).toContain('PM') // Contains time (exact time depends on timezone)
  })

  /**
   * Test Case 2: Back to Clients
   * When navigating from /clients list via route.meta.from
   */
  it('shows "Back to Clients" when navigating from /clients list', async () => {
    // Navigate to /clients first, then to client-detail
    // This will set route.meta.from = '/clients'
    await router.push('/clients')
    await router.push({
      name: 'client-detail',
      params: { id: 'client-123' },
    })

    const wrapper = mount(ClientDetailView, {
      global: {
        plugins: [pinia, router],
      },
    })

    await flushPromises()

    // Should show "Back to Clients"
    const backButtons = wrapper.findAll('button')
    const backButton = backButtons.find((btn) => btn.text().includes('Back to'))
    expect(backButton).toBeDefined()
    expect(backButton?.text()).toContain('Back to Clients')

    // Should NOT show appointment banner
    expect(wrapper.html()).not.toContain('Viewing from appointment')
  })

  /**
   * Test Case 3: Back to Calendar (Default)
   * When navigating from root or other pages
   */
  it('shows "Back to Calendar" as default', async () => {
    // Navigate from root (/) to client-detail
    // This will set route.meta.from = '/'
    await router.push('/')
    await router.push({
      name: 'client-detail',
      params: { id: 'client-123' },
    })

    const wrapper = mount(ClientDetailView, {
      global: {
        plugins: [pinia, router],
      },
    })

    await flushPromises()

    // Should show "Back to Calendar"
    const backButtons = wrapper.findAll('button')
    const backButton = backButtons.find((btn) => btn.text().includes('Back to'))
    expect(backButton).toBeDefined()
    expect(backButton?.text()).toContain('Back to Calendar')

    // Should NOT show appointment banner
    expect(wrapper.html()).not.toContain('Viewing from appointment')
  })

  /**
   * Test Case 4: Navigation Action - Back to Appointment
   * Clicking "Back to Appointment" navigates to calendar with appointment query param
   */
  it('navigates back to appointment when clicking "Back to Appointment"', async () => {
    const appointmentData: AppointmentListItem = {
      id: 'apt-123',
      workspace_id: 'workspace-123',
      client_id: 'client-123',
      client: {
        id: 'client-123',
        first_name: 'John',
        last_name: 'Doe',
        full_name: 'John Doe',
      },
      scheduled_start: '2025-03-15T14:00:00Z',
      scheduled_end: '2025-03-15T15:00:00Z',
      status: 'scheduled',
      location_type: 'clinic',
      location_details: null,
      notes: null,
    }

    // Mock history.state
    Object.defineProperty(window.history, 'state', {
      value: { appointment: appointmentData },
      writable: true,
      configurable: true,
    })

    await router.push({
      name: 'client-detail',
      params: { id: 'client-123' },
    })

    const wrapper = mount(ClientDetailView, {
      global: {
        plugins: [pinia, router],
      },
    })

    await flushPromises()

    // Find and click the back button
    const backButtons = wrapper.findAll('button')
    const backButton = backButtons.find((btn) =>
      btn.text().includes('Back to Appointment')
    )
    expect(backButton).toBeDefined()

    await backButton!.trigger('click')
    await flushPromises()

    // Should navigate to calendar with appointment query
    expect(router.currentRoute.value.path).toBe('/')
    expect(router.currentRoute.value.query.appointment).toBe('apt-123')
  })

  /**
   * Test Case 5: Navigation Action - Back to Clients
   * Clicking "Back to Clients" navigates to /clients
   */
  it('navigates back to clients list when clicking "Back to Clients"', async () => {
    // Navigate from /clients to client-detail
    await router.push('/clients')
    await router.push({
      name: 'client-detail',
      params: { id: 'client-123' },
    })

    const wrapper = mount(ClientDetailView, {
      global: {
        plugins: [pinia, router],
      },
    })

    await flushPromises()

    // Find and click the back button
    const backButtons = wrapper.findAll('button')
    const backButton = backButtons.find((btn) => btn.text().includes('Back to Clients'))
    expect(backButton).toBeDefined()

    await backButton!.trigger('click')
    await flushPromises()

    // Should navigate to /clients
    expect(router.currentRoute.value.path).toBe('/clients')
  })

  /**
   * Test Case 6: Navigation Action - Back to Calendar (Default)
   * Clicking "Back to Calendar" navigates to /
   */
  it('navigates back to calendar when clicking "Back to Calendar"', async () => {
    // Navigate from root to client-detail
    await router.push('/')
    await router.push({
      name: 'client-detail',
      params: { id: 'client-123' },
    })

    const wrapper = mount(ClientDetailView, {
      global: {
        plugins: [pinia, router],
      },
    })

    await flushPromises()

    // Find and click the back button
    const backButtons = wrapper.findAll('button')
    const backButton = backButtons.find((btn) =>
      btn.text().includes('Back to Calendar')
    )
    expect(backButton).toBeDefined()

    await backButton!.trigger('click')
    await flushPromises()

    // Should navigate to /
    expect(router.currentRoute.value.path).toBe('/')
  })

  /**
   * Test Case 7: Dismiss Banner
   * Clicking dismiss button removes banner and changes back button
   */
  it('dismisses appointment banner when clicking dismiss button', async () => {
    const appointmentData: AppointmentListItem = {
      id: 'apt-123',
      workspace_id: 'workspace-123',
      client_id: 'client-123',
      client: {
        id: 'client-123',
        first_name: 'John',
        last_name: 'Doe',
        full_name: 'John Doe',
      },
      scheduled_start: '2025-03-15T14:00:00Z',
      scheduled_end: '2025-03-15T15:00:00Z',
      status: 'scheduled',
      location_type: 'clinic',
      location_details: null,
      notes: null,
    }

    // Mock history.state
    Object.defineProperty(window.history, 'state', {
      value: { appointment: appointmentData },
      writable: true,
      configurable: true,
    })

    // Navigate from root to establish default fallback
    await router.push('/')
    await router.push({
      name: 'client-detail',
      params: { id: 'client-123' },
    })

    const wrapper = mount(ClientDetailView, {
      global: {
        plugins: [pinia, router],
      },
    })

    await flushPromises()

    // Banner should be visible
    expect(wrapper.html()).toContain('Viewing from appointment')

    // Find and click dismiss button (aria-label="Dismiss")
    const dismissButtons = wrapper.findAll('button')
    const dismissButton = dismissButtons.find(
      (btn) => btn.attributes('aria-label') === 'Dismiss'
    )
    expect(dismissButton).toBeDefined()

    await dismissButton!.trigger('click')
    await flushPromises()

    // Banner should be gone
    expect(wrapper.html()).not.toContain('Viewing from appointment')

    // Back button should now show default (Back to Calendar)
    const backButtons = wrapper.findAll('button')
    const backButton = backButtons.find((btn) => btn.text().includes('Back to'))
    expect(backButton?.text()).toContain('Back to Calendar')
  })

  /**
   * Test Case 8: Return to Appointment Link in Banner
   * Clicking "Return to appointment details" link navigates to appointment
   */
  it('navigates to appointment when clicking banner link', async () => {
    const appointmentData: AppointmentListItem = {
      id: 'apt-123',
      workspace_id: 'workspace-123',
      client_id: 'client-123',
      client: {
        id: 'client-123',
        first_name: 'John',
        last_name: 'Doe',
        full_name: 'John Doe',
      },
      scheduled_start: '2025-03-15T14:00:00Z',
      scheduled_end: '2025-03-15T15:00:00Z',
      status: 'scheduled',
      location_type: 'clinic',
      location_details: null,
      notes: null,
    }

    // Mock history.state
    Object.defineProperty(window.history, 'state', {
      value: { appointment: appointmentData },
      writable: true,
      configurable: true,
    })

    await router.push({
      name: 'client-detail',
      params: { id: 'client-123' },
    })

    const wrapper = mount(ClientDetailView, {
      global: {
        plugins: [pinia, router],
      },
    })

    await flushPromises()

    // Find the "Return to appointment details" button
    const bannerButtons = wrapper.findAll('button')
    const returnButton = bannerButtons.find((btn) =>
      btn.text().includes('Return to appointment details')
    )
    expect(returnButton).toBeDefined()

    await returnButton!.trigger('click')
    await flushPromises()

    // Should navigate to calendar with appointment query
    expect(router.currentRoute.value.path).toBe('/')
    expect(router.currentRoute.value.query.appointment).toBe('apt-123')
  })

  /**
   * Test Case 9: Direct Navigation
   * When navigating directly (no previous route), defaults to calendar
   */
  it('defaults to "Back to Calendar" on direct navigation', async () => {
    // Navigate directly to client-detail (from.path will be '/')
    await router.push({
      name: 'client-detail',
      params: { id: 'client-123' },
    })

    const wrapper = mount(ClientDetailView, {
      global: {
        plugins: [pinia, router],
      },
    })

    await flushPromises()

    // Should show "Back to Calendar" as default
    const backButtons = wrapper.findAll('button')
    const backButton = backButtons.find((btn) => btn.text().includes('Back to'))
    expect(backButton?.text()).toContain('Back to Calendar')
  })

  /**
   * Test Case 10: Unknown Route
   * When coming from an unknown route, defaults to calendar
   */
  it('defaults to "Back to Calendar" when coming from unknown route', async () => {
    // Navigate from settings (not /clients, so defaults to calendar)
    await router.push('/settings')
    await router.push({
      name: 'client-detail',
      params: { id: 'client-123' },
    })

    const wrapper = mount(ClientDetailView, {
      global: {
        plugins: [pinia, router],
      },
    })

    await flushPromises()

    // Should show "Back to Calendar" as default
    const backButtons = wrapper.findAll('button')
    const backButton = backButtons.find((btn) => btn.text().includes('Back to'))
    expect(backButton?.text()).toContain('Back to Calendar')
  })

  /**
   * Test Case 11: Priority Check
   * Appointment context takes priority over route.meta.from
   */
  it('prioritizes appointment context over route.meta.from', async () => {
    const appointmentData: AppointmentListItem = {
      id: 'apt-123',
      workspace_id: 'workspace-123',
      client_id: 'client-123',
      client: {
        id: 'client-123',
        first_name: 'John',
        last_name: 'Doe',
        full_name: 'John Doe',
      },
      scheduled_start: '2025-03-15T14:00:00Z',
      scheduled_end: '2025-03-15T15:00:00Z',
      status: 'scheduled',
      location_type: 'clinic',
      location_details: null,
      notes: null,
    }

    // Mock history.state
    Object.defineProperty(window.history, 'state', {
      value: { appointment: appointmentData },
      writable: true,
      configurable: true,
    })

    // Navigate from /clients (which would normally show "Back to Clients")
    // But appointment context should take priority
    await router.push('/clients')
    await router.push({
      name: 'client-detail',
      params: { id: 'client-123' },
    })

    const wrapper = mount(ClientDetailView, {
      global: {
        plugins: [pinia, router],
      },
    })

    await flushPromises()

    // Should show "Back to Appointment" (not "Back to Clients")
    const backButtons = wrapper.findAll('button')
    const backButton = backButtons.find((btn) => btn.text().includes('Back to'))
    expect(backButton?.text()).toContain('Back to Appointment')
  })
})
