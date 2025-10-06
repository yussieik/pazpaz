import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import DeleteAppointmentDialog from './DeleteAppointmentDialog.vue'
import type { AppointmentListItem } from '@/types/calendar'

// Mock date formatter
vi.mock('@/utils/calendar/dateFormatters', () => ({
  formatDate: vi.fn((date: string) => date),
}))

const mockScheduledAppointment: AppointmentListItem = {
  id: '123',
  workspace_id: 'ws-1',
  client_id: 'client-1',
  scheduled_start: '2024-01-01T10:00:00Z',
  scheduled_end: '2024-01-01T11:00:00Z',
  location_type: 'clinic',
  location_details: 'Room 101',
  status: 'scheduled',
  notes: '',
  created_at: '2024-01-01T09:00:00Z',
  updated_at: '2024-01-01T09:00:00Z',
  client: {
    id: 'client-1',
    first_name: 'John',
    last_name: 'Doe',
    full_name: 'John Doe',
  },
}

const mockCompletedAppointment: AppointmentListItem = {
  ...mockScheduledAppointment,
  status: 'completed',
}

const mockCancelledAppointment: AppointmentListItem = {
  ...mockScheduledAppointment,
  status: 'cancelled',
}

describe('DeleteAppointmentDialog', () => {
  it('calculates canDelete correctly for scheduled appointment', () => {
    const wrapper = mount(DeleteAppointmentDialog, {
      props: {
        visible: true,
        appointment: mockScheduledAppointment,
      },
    })

    // Access component's computed property indirectly through the template
    const vm = wrapper.vm as {
      canDelete: boolean
      blockReason: string
    }

    expect(vm.canDelete).toBe(true)
    expect(vm.blockReason).toBe('')
  })

  it('blocks deletion for completed appointment', () => {
    const wrapper = mount(DeleteAppointmentDialog, {
      props: {
        visible: true,
        appointment: mockCompletedAppointment,
      },
    })

    const vm = wrapper.vm as {
      canDelete: boolean
      blockReason: string
    }

    expect(vm.canDelete).toBe(false)
    expect(vm.blockReason).toContain('Completed appointments cannot be deleted')
  })

  it('allows deletion for cancelled appointment', () => {
    const wrapper = mount(DeleteAppointmentDialog, {
      props: {
        visible: true,
        appointment: mockCancelledAppointment,
      },
    })

    const vm = wrapper.vm as {
      canDelete: boolean
    }

    expect(vm.canDelete).toBe(true)
  })

  it('emits confirm event when handleConfirm is called for deletable appointment', async () => {
    const wrapper = mount(DeleteAppointmentDialog, {
      props: {
        visible: true,
        appointment: mockScheduledAppointment,
      },
    })

    // Access the handleConfirm method
    const vm = wrapper.vm as {
      handleConfirm: () => void
    }

    vm.handleConfirm()
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('confirm')).toBeTruthy()
    expect(wrapper.emitted('confirm')?.length).toBe(1)
  })

  it('does not emit confirm event for non-deletable appointment', async () => {
    const wrapper = mount(DeleteAppointmentDialog, {
      props: {
        visible: true,
        appointment: mockCompletedAppointment,
      },
    })

    const vm = wrapper.vm as {
      handleConfirm: () => void
    }

    vm.handleConfirm()
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('confirm')).toBeFalsy()
  })

  it('emits update:visible event when closeDialog is called', async () => {
    const wrapper = mount(DeleteAppointmentDialog, {
      props: {
        visible: true,
        appointment: mockScheduledAppointment,
      },
    })

    const vm = wrapper.vm as {
      closeDialog: () => void
    }

    vm.closeDialog()
    await wrapper.vm.$nextTick()

    expect(wrapper.emitted('update:visible')).toBeTruthy()
    expect(wrapper.emitted('update:visible')?.[0]).toEqual([false])
  })

  it('does not close when isDeleting is true', async () => {
    const wrapper = mount(DeleteAppointmentDialog, {
      props: {
        visible: true,
        appointment: mockScheduledAppointment,
      },
    })

    const vm = wrapper.vm as {
      isDeleting: boolean
      closeDialog: () => void
    }

    // Set isDeleting to true
    vm.isDeleting = true
    await wrapper.vm.$nextTick()

    vm.closeDialog()
    await wrapper.vm.$nextTick()

    // Should not emit update:visible when isDeleting is true
    expect(wrapper.emitted('update:visible')).toBeFalsy()
  })

  it('sets isDeleting to true when confirm is called', async () => {
    const wrapper = mount(DeleteAppointmentDialog, {
      props: {
        visible: true,
        appointment: mockScheduledAppointment,
      },
    })

    const vm = wrapper.vm as {
      isDeleting: boolean
      handleConfirm: () => void
    }

    expect(vm.isDeleting).toBe(false)

    vm.handleConfirm()
    await wrapper.vm.$nextTick()

    expect(vm.isDeleting).toBe(true)
  })
})
