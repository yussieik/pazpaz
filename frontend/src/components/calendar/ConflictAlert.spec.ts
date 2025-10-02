import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ConflictAlert from './ConflictAlert.vue'
import type { ConflictingAppointment } from '@/types/calendar'

describe('ConflictAlert', () => {
  const mockConflicts: ConflictingAppointment[] = [
    {
      id: '123e4567-e89b-12d3-a456-426614174000',
      scheduled_start: '2025-10-03T10:00:00Z',
      scheduled_end: '2025-10-03T11:00:00Z',
      client_initials: 'J.D.',
      location_type: 'clinic',
      status: 'scheduled',
    },
    {
      id: '123e4567-e89b-12d3-a456-426614174001',
      scheduled_start: '2025-10-03T14:00:00Z',
      scheduled_end: '2025-10-03T15:00:00Z',
      client_initials: 'S.M.',
      location_type: 'online',
      status: 'confirmed',
    },
  ]

  it('renders conflict alert with correct count', () => {
    const wrapper = mount(ConflictAlert, {
      props: {
        conflicts: mockConflicts,
      },
    })

    expect(wrapper.text()).toContain('Scheduling Conflict')
    expect(wrapper.text()).toContain('This time overlaps with 2 existing appointments.')
  })

  it('shows singular form for single conflict', () => {
    const wrapper = mount(ConflictAlert, {
      props: {
        conflicts: [mockConflicts[0]],
      },
    })

    expect(wrapper.text()).toContain('This time overlaps with 1 existing appointment.')
  })

  it('has correct ARIA attributes for accessibility', () => {
    const wrapper = mount(ConflictAlert, {
      props: {
        conflicts: mockConflicts,
      },
    })

    const alert = wrapper.find('[role="alert"]')
    expect(alert.exists()).toBe(true)
    expect(alert.attributes('aria-live')).toBe('polite')
    expect(alert.attributes('aria-atomic')).toBe('true')

    // Check warning icon is hidden from screen readers
    const icon = wrapper.find('svg')
    expect(icon.attributes('aria-hidden')).toBe('true')
  })

  it('toggles expanded state on "View details" click', async () => {
    const wrapper = mount(ConflictAlert, {
      props: {
        conflicts: mockConflicts,
      },
    })

    const toggleButton = wrapper.find('button')

    // Initially collapsed
    expect(toggleButton.text()).toBe('View details')
    expect(toggleButton.attributes('aria-expanded')).toBe('false')
    expect(wrapper.find('#conflict-details').exists()).toBe(false)

    // Click to expand
    await toggleButton.trigger('click')
    expect(toggleButton.text()).toBe('Hide details')
    expect(toggleButton.attributes('aria-expanded')).toBe('true')
    expect(wrapper.find('#conflict-details').exists()).toBe(true)

    // Click to collapse
    await toggleButton.trigger('click')
    expect(toggleButton.text()).toBe('View details')
    expect(toggleButton.attributes('aria-expanded')).toBe('false')
  })

  it('displays conflict details when expanded', async () => {
    const wrapper = mount(ConflictAlert, {
      props: {
        conflicts: mockConflicts,
      },
    })

    const toggleButton = wrapper.find('button')
    await toggleButton.trigger('click')

    // Check that both conflicts are displayed
    const conflictCards = wrapper.findAll('#conflict-details > div')
    expect(conflictCards).toHaveLength(2)

    // Check first conflict details
    expect(conflictCards[0].text()).toContain('Client: J.D.')
    expect(conflictCards[0].text()).toContain('Clinic')

    // Check second conflict details
    expect(conflictCards[1].text()).toContain('Client: S.M.')
    expect(conflictCards[1].text()).toContain('Online')
  })

  it('formats time ranges correctly', async () => {
    const wrapper = mount(ConflictAlert, {
      props: {
        conflicts: [mockConflicts[0]],
      },
    })

    const toggleButton = wrapper.find('button')
    await toggleButton.trigger('click')

    // Check time formatting (will vary based on timezone)
    const timeText = wrapper.find('#conflict-details').text()
    expect(timeText).toMatch(/\d{1,2}:\d{2} [AP]M - \d{1,2}:\d{2} [AP]M/)
  })

  it('emits view-conflict event when "View →" button is clicked', async () => {
    const wrapper = mount(ConflictAlert, {
      props: {
        conflicts: [mockConflicts[0]],
      },
    })

    const toggleButton = wrapper.find('button')
    await toggleButton.trigger('click')

    const viewButton = wrapper.findAll('button')[1] // Second button is "View →"
    await viewButton.trigger('click')

    expect(wrapper.emitted('view-conflict')).toBeTruthy()
    expect(wrapper.emitted('view-conflict')?.[0]).toEqual([mockConflicts[0].id])
  })

  it('handles multiple conflicts with scrollable container', async () => {
    const manyConflicts: ConflictingAppointment[] = Array.from({ length: 10 }, (_, i) => ({
      id: `conflict-${i}`,
      scheduled_start: '2025-10-03T10:00:00Z',
      scheduled_end: '2025-10-03T11:00:00Z',
      client_initials: `C.${i}`,
      location_type: 'clinic' as const,
      status: 'scheduled' as const,
    }))

    const wrapper = mount(ConflictAlert, {
      props: {
        conflicts: manyConflicts,
      },
    })

    const toggleButton = wrapper.find('button')
    await toggleButton.trigger('click')

    // Check that container has overflow styling
    const conflictDetails = wrapper.find('#conflict-details')
    expect(conflictDetails.classes()).toContain('overflow-y-auto')
    expect(conflictDetails.classes()).toContain('max-h-64')

    // Check all conflicts are rendered
    const conflictCards = wrapper.findAll('#conflict-details > div')
    expect(conflictCards).toHaveLength(10)
  })

  it('displays correct location labels', async () => {
    const conflicts: ConflictingAppointment[] = [
      { ...mockConflicts[0], location_type: 'clinic' },
      { ...mockConflicts[0], id: '2', location_type: 'home' },
      { ...mockConflicts[0], id: '3', location_type: 'online' },
    ]

    const wrapper = mount(ConflictAlert, {
      props: { conflicts },
    })

    await wrapper.find('button').trigger('click')

    expect(wrapper.text()).toContain('Clinic')
    expect(wrapper.text()).toContain('Home Visit')
    expect(wrapper.text()).toContain('Online')
  })

  it('has proper focus management for accessibility', async () => {
    const wrapper = mount(ConflictAlert, {
      props: {
        conflicts: mockConflicts,
      },
    })

    const toggleButton = wrapper.find('button')

    // Check focus styles are present
    expect(toggleButton.classes()).toContain('focus:outline-none')
    expect(toggleButton.classes()).toContain('focus:ring-2')
    expect(toggleButton.classes()).toContain('focus:ring-amber-500')
  })

  it('has ARIA controls relationship between button and details', async () => {
    const wrapper = mount(ConflictAlert, {
      props: {
        conflicts: mockConflicts,
      },
    })

    const toggleButton = wrapper.find('button')
    expect(toggleButton.attributes('aria-controls')).toBe('conflict-details')

    await toggleButton.trigger('click')

    const detailsRegion = wrapper.find('#conflict-details')
    expect(detailsRegion.attributes('role')).toBe('region')
    expect(detailsRegion.attributes('aria-labelledby')).toBe('conflict-heading')
  })

  it('renders with correct Tailwind classes for styling', () => {
    const wrapper = mount(ConflictAlert, {
      props: {
        conflicts: mockConflicts,
      },
    })

    const alertContainer = wrapper.find('[role="alert"]')

    // Check for amber color scheme
    expect(alertContainer.classes()).toContain('bg-amber-50')
    expect(alertContainer.classes()).toContain('border-amber-500')
    expect(alertContainer.classes()).toContain('border-l-4')

    // Check for proper spacing
    expect(alertContainer.classes()).toContain('px-4')
    expect(alertContainer.classes()).toContain('py-3')
    expect(alertContainer.classes()).toContain('rounded-lg')
  })
})
