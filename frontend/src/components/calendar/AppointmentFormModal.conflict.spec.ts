import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import AppointmentFormModal from './AppointmentFormModal.vue'
import ConflictAlert from './ConflictAlert.vue'
import * as apiClient from '@/api/client'
import type { ConflictCheckResponse } from '@/types/calendar'

// Mock the API client
vi.mock('@/api/client', () => ({
  checkAppointmentConflicts: vi.fn(),
}))

describe('AppointmentFormModal - Conflict Detection', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  const mockConflictResponse: ConflictCheckResponse = {
    has_conflict: true,
    conflicting_appointments: [
      {
        id: '123e4567-e89b-12d3-a456-426614174000',
        scheduled_start: '2025-10-03T10:00:00Z',
        scheduled_end: '2025-10-03T11:00:00Z',
        client_initials: 'J.D.',
        location_type: 'clinic',
        status: 'scheduled',
      },
    ],
  }

  const mockNoConflictResponse: ConflictCheckResponse = {
    has_conflict: false,
    conflicting_appointments: [],
  }

  it('debounces conflict checks to 500ms', async () => {
    vi.mocked(apiClient.checkAppointmentConflicts).mockResolvedValue(mockNoConflictResponse)

    const wrapper = mount(AppointmentFormModal, {
      props: {
        visible: true,
        mode: 'create',
      },
      attachTo: document.body,
    })

    await nextTick()

    // Simulate rapid changes by directly updating form data
    // Access component instance for testing
    const vm = wrapper.vm as any

    vm.formData.scheduled_start = '2025-10-03T10:00'
    vm.formData.scheduled_end = '2025-10-03T11:00'
    await nextTick()

    vm.formData.scheduled_start = '2025-10-03T10:30'
    await nextTick()

    vm.formData.scheduled_end = '2025-10-03T11:30'
    await nextTick()

    // API should not have been called yet (debounced)
    expect(apiClient.checkAppointmentConflicts).not.toHaveBeenCalled()

    // Fast-forward to debounce threshold
    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()

    // API should have been called exactly once
    expect(apiClient.checkAppointmentConflicts).toHaveBeenCalledTimes(1)

    wrapper.unmount()
  })

  it('passes correct parameters to API in create mode', async () => {
    vi.mocked(apiClient.checkAppointmentConflicts).mockResolvedValue(mockNoConflictResponse)

    const wrapper = mount(AppointmentFormModal, {
      props: {
        visible: true,
        mode: 'create',
      },
      attachTo: document.body,
    })

    await nextTick()

    const vm = wrapper.vm as any
    vm.formData.scheduled_start = '2025-10-03T10:00'
    vm.formData.scheduled_end = '2025-10-03T11:00'
    await nextTick()

    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()

    expect(apiClient.checkAppointmentConflicts).toHaveBeenCalledWith({
      scheduled_start: expect.stringMatching(/2025-10-03T\d{2}:00:00/),
      scheduled_end: expect.stringMatching(/2025-10-03T\d{2}:00:00/),
      exclude_appointment_id: undefined,
    })

    wrapper.unmount()
  })

  it('excludes current appointment ID in edit mode', async () => {
    vi.mocked(apiClient.checkAppointmentConflicts).mockResolvedValue(mockNoConflictResponse)

    const appointmentId = 'existing-appointment-123'

    const wrapper = mount(AppointmentFormModal, {
      props: {
        visible: true,
        mode: 'edit',
        appointment: {
          id: appointmentId,
          client_id: 'client-1',
          scheduled_start: '2025-10-03T09:00:00Z',
          scheduled_end: '2025-10-03T10:00:00Z',
          location_type: 'clinic',
          status: 'scheduled',
          created_at: '2025-10-01T00:00:00Z',
          updated_at: '2025-10-01T00:00:00Z',
        },
      },
      attachTo: document.body,
    })

    await nextTick()

    const vm = wrapper.vm as any
    vm.formData.scheduled_start = '2025-10-03T10:00'
    vm.formData.scheduled_end = '2025-10-03T11:00'
    await nextTick()

    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()

    expect(apiClient.checkAppointmentConflicts).toHaveBeenCalledWith(
      expect.objectContaining({
        exclude_appointment_id: appointmentId,
      })
    )

    wrapper.unmount()
  })

  it('shows ConflictAlert component when conflicts are detected', async () => {
    vi.mocked(apiClient.checkAppointmentConflicts).mockResolvedValue(mockConflictResponse)

    const wrapper = mount(AppointmentFormModal, {
      props: {
        visible: true,
        mode: 'create',
      },
      attachTo: document.body,
    })

    await nextTick()

    const vm = wrapper.vm as any
    vm.formData.scheduled_start = '2025-10-03T10:00'
    vm.formData.scheduled_end = '2025-10-03T11:00'
    await nextTick()

    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()

    // Should show ConflictAlert component
    expect(wrapper.findComponent(ConflictAlert).exists()).toBe(true)

    wrapper.unmount()
  })

  it('hides ConflictAlert when no conflicts exist', async () => {
    vi.mocked(apiClient.checkAppointmentConflicts).mockResolvedValue(mockNoConflictResponse)

    const wrapper = mount(AppointmentFormModal, {
      props: {
        visible: true,
        mode: 'create',
      },
      attachTo: document.body,
    })

    await nextTick()

    const vm = wrapper.vm as any
    vm.formData.scheduled_start = '2025-10-03T10:00'
    vm.formData.scheduled_end = '2025-10-03T11:00'
    await nextTick()

    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()

    // Should NOT show ConflictAlert
    expect(wrapper.findComponent(ConflictAlert).exists()).toBe(false)

    wrapper.unmount()
  })

  it('handles API errors gracefully without blocking submission', async () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.mocked(apiClient.checkAppointmentConflicts).mockRejectedValue(
      new Error('Network error')
    )

    const wrapper = mount(AppointmentFormModal, {
      props: {
        visible: true,
        mode: 'create',
      },
      attachTo: document.body,
    })

    await nextTick()

    const vm = wrapper.vm as any
    vm.formData.scheduled_start = '2025-10-03T10:00'
    vm.formData.scheduled_end = '2025-10-03T11:00'
    await nextTick()

    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()

    // Should log error but not show conflict alert
    expect(consoleErrorSpy).toHaveBeenCalledWith(
      'Conflict check failed:',
      expect.any(Error)
    )
    expect(wrapper.findComponent(ConflictAlert).exists()).toBe(false)

    consoleErrorSpy.mockRestore()
    wrapper.unmount()
  })

  it('clears conflicts when time fields are emptied', async () => {
    vi.mocked(apiClient.checkAppointmentConflicts).mockResolvedValue(mockConflictResponse)

    const wrapper = mount(AppointmentFormModal, {
      props: {
        visible: true,
        mode: 'create',
      },
      attachTo: document.body,
    })

    await nextTick()

    const vm = wrapper.vm as any

    // Set times and trigger conflict
    vm.formData.scheduled_start = '2025-10-03T10:00'
    vm.formData.scheduled_end = '2025-10-03T11:00'
    await nextTick()

    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()

    expect(wrapper.findComponent(ConflictAlert).exists()).toBe(true)

    // Clear end time
    vm.formData.scheduled_end = ''
    await nextTick()

    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()

    // Conflict should be cleared (no API call with incomplete times)
    expect(wrapper.findComponent(ConflictAlert).exists()).toBe(false)

    wrapper.unmount()
  })

  it('resets conflicts when modal is closed', async () => {
    vi.mocked(apiClient.checkAppointmentConflicts).mockResolvedValue(mockConflictResponse)

    const wrapper = mount(AppointmentFormModal, {
      props: {
        visible: true,
        mode: 'create',
      },
      attachTo: document.body,
    })

    await nextTick()

    const vm = wrapper.vm as any

    // Trigger conflict
    vm.formData.scheduled_start = '2025-10-03T10:00'
    vm.formData.scheduled_end = '2025-10-03T11:00'
    await nextTick()

    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()

    expect(wrapper.findComponent(ConflictAlert).exists()).toBe(true)

    // Close modal
    await wrapper.setProps({ visible: false })
    await flushPromises()

    // Reopen modal
    await wrapper.setProps({ visible: true })
    await flushPromises()

    // Conflicts should be cleared
    expect(wrapper.findComponent(ConflictAlert).exists()).toBe(false)

    wrapper.unmount()
  })

  it('converts datetime-local format to ISO 8601 for API', async () => {
    vi.mocked(apiClient.checkAppointmentConflicts).mockResolvedValue(mockNoConflictResponse)

    const wrapper = mount(AppointmentFormModal, {
      props: {
        visible: true,
        mode: 'create',
      },
      attachTo: document.body,
    })

    await nextTick()

    const vm = wrapper.vm as any
    vm.formData.scheduled_start = '2025-10-03T10:30'
    vm.formData.scheduled_end = '2025-10-03T11:45'
    await nextTick()

    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()

    expect(apiClient.checkAppointmentConflicts).toHaveBeenCalledWith({
      scheduled_start: expect.stringMatching(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/),
      scheduled_end: expect.stringMatching(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/),
      exclude_appointment_id: undefined,
    })

    wrapper.unmount()
  })
})
