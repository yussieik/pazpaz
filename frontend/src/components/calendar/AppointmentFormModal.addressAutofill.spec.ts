import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import AppointmentFormModal from './AppointmentFormModal.vue'
import { useClientsStore } from '@/stores/clients'
import type { ClientListItem } from '@/types/client'

// Mock the API client
vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
  checkAppointmentConflicts: vi.fn().mockResolvedValue({
    has_conflict: false,
    conflicting_appointments: [],
  }),
}))

// Mock composables
vi.mock('@/composables/useClientSearch', () => ({
  useClientSearch: () => ({
    searchResults: { value: [] },
    recentClients: { value: [] },
    isSearching: { value: false },
    isLoadingRecent: { value: false },
    isCreating: { value: false },
    error: { value: null },
    searchClients: vi.fn(),
    fetchRecentClients: vi.fn(),
    createClient: vi.fn(),
    clearSearch: vi.fn(),
  }),
}))

vi.mock('@/composables/useScreenReader', () => ({
  useScreenReader: () => ({
    announce: vi.fn(),
  }),
}))

describe('AppointmentFormModal - Address Auto-fill', () => {
  let pinia: ReturnType<typeof createPinia>
  let clientsStore: ReturnType<typeof useClientsStore>

  const mockClient: ClientListItem = {
    id: 'client-123',
    workspace_id: 'workspace-123',
    first_name: 'Jane',
    last_name: 'Doe',
    full_name: 'Jane Doe',
    email: 'jane.doe@example.com',
    phone: '555-1234',
    address: '123 Oak Street, Seattle, WA 98101',
    date_of_birth: '1990-01-15',
    emergency_contact_name: null,
    emergency_contact_phone: null,
    medical_history: null,
    notes: null,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
    appointment_count: 5,
    last_appointment: '2024-10-01T10:00:00Z',
    next_appointment: null,
  }

  const mockClientNoAddress: ClientListItem = {
    ...mockClient,
    id: 'client-456',
    first_name: 'John',
    last_name: 'Smith',
    full_name: 'John Smith',
    address: null,
  }

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)
    clientsStore = useClientsStore()

    // Setup mock clients in store
    clientsStore.clients = [mockClient, mockClientNoAddress]
  })

  it('auto-fills address when client with address is selected for home visit', async () => {
    const wrapper = mount(AppointmentFormModal, {
      props: {
        visible: true,
        mode: 'create',
        prefillDateTime: {
          start: new Date('2024-10-15T10:00:00'),
          end: new Date('2024-10-15T11:00:00'),
        },
      },
      global: {
        plugins: [pinia],
        stubs: {
          Teleport: true,
          ClientCombobox: true,
          TimePickerDropdown: true,
          IconClose: true,
          IconWarning: true,
        },
      },
    })

    await flushPromises()

    // Get form data reference
    const vm = wrapper.vm as unknown as {
      formData: {
        client_id: string
        location_type: string
        location_details: string
      }
      showAddressHint: boolean
    }

    // Initially empty
    expect(vm.formData.location_details).toBe('')

    // Select client
    vm.formData.client_id = mockClient.id
    await flushPromises()

    // Location details still empty (clinic is default)
    expect(vm.formData.location_details).toBe('')

    // Change to home visit
    vm.formData.location_type = 'home'
    await flushPromises()

    // Address should auto-fill
    expect(vm.formData.location_details).toBe(mockClient.address)

    // Hint should show
    expect(vm.showAddressHint).toBe(true)

    // Verify hint element exists in DOM
    const hint = wrapper.find('[role="status"]')
    expect(hint.exists()).toBe(true)
    expect(hint.text()).toContain('Using address from client profile')
  })

  it('auto-fills address when location type is changed to home after client selection', async () => {
    const wrapper = mount(AppointmentFormModal, {
      props: {
        visible: true,
        mode: 'create',
        prefillDateTime: {
          start: new Date('2024-10-15T10:00:00'),
          end: new Date('2024-10-15T11:00:00'),
        },
      },
      global: {
        plugins: [pinia],
        stubs: {
          Teleport: true,
          ClientCombobox: true,
          TimePickerDropdown: true,
          IconClose: true,
          IconWarning: true,
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as unknown as {
      formData: {
        client_id: string
        location_type: string
        location_details: string
      }
    }

    // Select client first
    vm.formData.client_id = mockClient.id
    vm.formData.location_type = 'clinic'
    await flushPromises()

    // No auto-fill for clinic
    expect(vm.formData.location_details).toBe('')

    // Change to home visit
    vm.formData.location_type = 'home'
    await flushPromises()

    // Address should auto-fill
    expect(vm.formData.location_details).toBe(mockClient.address)
  })

  it('does not auto-fill when client has no address', async () => {
    const wrapper = mount(AppointmentFormModal, {
      props: {
        visible: true,
        mode: 'create',
        prefillDateTime: {
          start: new Date('2024-10-15T10:00:00'),
          end: new Date('2024-10-15T11:00:00'),
        },
      },
      global: {
        plugins: [pinia],
        stubs: {
          Teleport: true,
          ClientCombobox: true,
          TimePickerDropdown: true,
          IconClose: true,
          IconWarning: true,
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as unknown as {
      formData: {
        client_id: string
        location_type: string
        location_details: string
      }
      showAddressHint: boolean
    }

    // Select client without address
    vm.formData.client_id = mockClientNoAddress.id
    vm.formData.location_type = 'home'
    await flushPromises()

    // Should remain empty
    expect(vm.formData.location_details).toBe('')

    // Hint should not show
    expect(vm.showAddressHint).toBe(false)
  })

  it('does not overwrite manually entered location details', async () => {
    const wrapper = mount(AppointmentFormModal, {
      props: {
        visible: true,
        mode: 'create',
        prefillDateTime: {
          start: new Date('2024-10-15T10:00:00'),
          end: new Date('2024-10-15T11:00:00'),
        },
      },
      global: {
        plugins: [pinia],
        stubs: {
          Teleport: true,
          ClientCombobox: true,
          TimePickerDropdown: true,
          IconClose: true,
          IconWarning: true,
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as unknown as {
      formData: {
        client_id: string
        location_type: string
        location_details: string
      }
    }

    // User manually enters location details
    vm.formData.location_details = 'Custom location'
    await flushPromises()

    // Now select client and home visit
    vm.formData.client_id = mockClient.id
    vm.formData.location_type = 'home'
    await flushPromises()

    // Should NOT overwrite manual entry
    expect(vm.formData.location_details).toBe('Custom location')
  })

  it('does not overwrite existing location details in edit mode', async () => {
    const wrapper = mount(AppointmentFormModal, {
      props: {
        visible: true,
        mode: 'edit',
        appointment: {
          id: 'apt-123',
          workspace_id: 'workspace-123',
          client_id: mockClient.id,
          client_initials: 'JD',
          client_full_name: mockClient.full_name,
          scheduled_start: '2024-10-15T10:00:00Z',
          scheduled_end: '2024-10-15T11:00:00Z',
          location_type: 'home',
          location_details: 'Old address from previous appointment',
          notes: null,
          status: 'scheduled',
          created_at: '2024-10-01T00:00:00Z',
          updated_at: '2024-10-01T00:00:00Z',
        },
      },
      global: {
        plugins: [pinia],
        stubs: {
          Teleport: true,
          ClientCombobox: true,
          TimePickerDropdown: true,
          IconClose: true,
          IconWarning: true,
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as unknown as {
      formData: {
        location_details: string
      }
    }

    // Should preserve existing location details
    expect(vm.formData.location_details).toBe('Old address from previous appointment')
  })

  it('does not auto-fill for clinic appointments', async () => {
    const wrapper = mount(AppointmentFormModal, {
      props: {
        visible: true,
        mode: 'create',
        prefillDateTime: {
          start: new Date('2024-10-15T10:00:00'),
          end: new Date('2024-10-15T11:00:00'),
        },
      },
      global: {
        plugins: [pinia],
        stubs: {
          Teleport: true,
          ClientCombobox: true,
          TimePickerDropdown: true,
          IconClose: true,
          IconWarning: true,
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as unknown as {
      formData: {
        client_id: string
        location_type: string
        location_details: string
      }
    }

    // Select client and clinic location
    vm.formData.client_id = mockClient.id
    vm.formData.location_type = 'clinic'
    await flushPromises()

    // Should NOT auto-fill
    expect(vm.formData.location_details).toBe('')
  })

  it('does not auto-fill for online appointments', async () => {
    const wrapper = mount(AppointmentFormModal, {
      props: {
        visible: true,
        mode: 'create',
        prefillDateTime: {
          start: new Date('2024-10-15T10:00:00'),
          end: new Date('2024-10-15T11:00:00'),
        },
      },
      global: {
        plugins: [pinia],
        stubs: {
          Teleport: true,
          ClientCombobox: true,
          TimePickerDropdown: true,
          IconClose: true,
          IconWarning: true,
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as unknown as {
      formData: {
        client_id: string
        location_type: string
        location_details: string
      }
    }

    // Select client and online location
    vm.formData.client_id = mockClient.id
    vm.formData.location_type = 'online'
    await flushPromises()

    // Should NOT auto-fill
    expect(vm.formData.location_details).toBe('')
  })

  it('hides hint after 3 seconds', async () => {
    vi.useFakeTimers()

    const wrapper = mount(AppointmentFormModal, {
      props: {
        visible: true,
        mode: 'create',
        prefillDateTime: {
          start: new Date('2024-10-15T10:00:00'),
          end: new Date('2024-10-15T11:00:00'),
        },
      },
      global: {
        plugins: [pinia],
        stubs: {
          Teleport: true,
          ClientCombobox: true,
          TimePickerDropdown: true,
          IconClose: true,
          IconWarning: true,
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as unknown as {
      formData: {
        client_id: string
        location_type: string
      }
      showAddressHint: boolean
    }

    // Trigger auto-fill
    vm.formData.client_id = mockClient.id
    vm.formData.location_type = 'home'
    await flushPromises()

    // Hint should show
    expect(vm.showAddressHint).toBe(true)

    // Fast-forward time by 3 seconds
    vi.advanceTimersByTime(3000)
    await flushPromises()

    // Hint should be hidden
    expect(vm.showAddressHint).toBe(false)

    vi.useRealTimers()
  })

  it('preserves manually edited address when switching location types', async () => {
    const wrapper = mount(AppointmentFormModal, {
      props: {
        visible: true,
        mode: 'create',
        prefillDateTime: {
          start: new Date('2024-10-15T10:00:00'),
          end: new Date('2024-10-15T11:00:00'),
        },
      },
      global: {
        plugins: [pinia],
        stubs: {
          Teleport: true,
          ClientCombobox: true,
          TimePickerDropdown: true,
          IconClose: true,
          IconWarning: true,
        },
      },
    })

    await flushPromises()

    const vm = wrapper.vm as unknown as {
      formData: {
        client_id: string
        location_type: string
        location_details: string
      }
    }

    // Select client and home visit (auto-fills)
    vm.formData.client_id = mockClient.id
    vm.formData.location_type = 'home'
    await flushPromises()

    // Verify auto-fill worked
    expect(vm.formData.location_details).toBe(mockClient.address)

    // User edits the address
    vm.formData.location_details = 'Edited address'
    await flushPromises()

    // Switch to clinic
    vm.formData.location_type = 'clinic'
    await flushPromises()

    // Should preserve edited address
    expect(vm.formData.location_details).toBe('Edited address')

    // Switch back to home
    vm.formData.location_type = 'home'
    await flushPromises()

    // Should still preserve edited address (not re-auto-fill)
    expect(vm.formData.location_details).toBe('Edited address')
  })
})
