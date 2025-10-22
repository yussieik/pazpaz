import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ActivityItem, { type Activity } from './ActivityItem.vue'

describe('ActivityItem', () => {
  const mockActivity: Activity = {
    id: '1',
    type: 'invitation-accepted',
    timestamp: '2 minutes ago',
    description: 'Sarah Chen accepted invitation',
    metadata: { email: 'sarah@example.com' },
  }

  describe('Rendering', () => {
    it('renders activity description', () => {
      const wrapper = mount(ActivityItem, {
        props: {
          activity: mockActivity,
        },
      })

      expect(wrapper.text()).toContain('Sarah Chen accepted invitation')
    })

    it('renders activity timestamp', () => {
      const wrapper = mount(ActivityItem, {
        props: {
          activity: mockActivity,
        },
      })

      expect(wrapper.text()).toContain('2 minutes ago')
    })

    it('renders icon for activity type', () => {
      const wrapper = mount(ActivityItem, {
        props: {
          activity: mockActivity,
        },
      })

      const icon = wrapper.find('svg')
      expect(icon.exists()).toBe(true)
    })
  })

  describe('Activity Types', () => {
    const activityTypes: Activity['type'][] = [
      'invitation-accepted',
      'invitation-sent',
      'invitation-expired',
      'workspace-created',
      'workspace-suspended',
      'user-blacklisted',
    ]

    it('renders correct icon color for each activity type', () => {
      const expectedColors: Record<Activity['type'], string> = {
        'invitation-accepted': 'bg-emerald-100',
        'invitation-sent': 'bg-blue-100',
        'invitation-expired': 'bg-amber-100',
        'workspace-created': 'bg-purple-100',
        'workspace-suspended': 'bg-red-100',
        'user-blacklisted': 'bg-red-100',
      }

      activityTypes.forEach((type) => {
        const activity: Activity = {
          id: '1',
          type,
          timestamp: 'now',
          description: 'Test',
        }

        const wrapper = mount(ActivityItem, {
          props: { activity },
        })

        const iconContainer = wrapper.find('.flex-shrink-0')
        expect(iconContainer.classes()).toContain(expectedColors[type])
      })
    })

    it('renders all activity types without errors', () => {
      activityTypes.forEach((type) => {
        const activity: Activity = {
          id: '1',
          type,
          timestamp: 'now',
          description: 'Test activity',
        }

        expect(() => {
          mount(ActivityItem, {
            props: { activity },
          })
        }).not.toThrow()
      })
    })
  })

  describe('Accessibility', () => {
    it('marks icon as aria-hidden', () => {
      const wrapper = mount(ActivityItem, {
        props: {
          activity: mockActivity,
        },
      })

      const iconContainer = wrapper.find('[aria-hidden="true"]')
      expect(iconContainer.exists()).toBe(true)
    })
  })

  describe('Layout', () => {
    it('uses flex layout with gap', () => {
      const wrapper = mount(ActivityItem, {
        props: {
          activity: mockActivity,
        },
      })

      const container = wrapper.find('.flex')
      expect(container.classes()).toContain('gap-3')
    })

    it('icon is non-shrinkable', () => {
      const wrapper = mount(ActivityItem, {
        props: {
          activity: mockActivity,
        },
      })

      const iconContainer = wrapper.find('.h-8.w-8')
      expect(iconContainer.classes()).toContain('flex-shrink-0')
    })

    it('content takes remaining space', () => {
      const wrapper = mount(ActivityItem, {
        props: {
          activity: mockActivity,
        },
      })

      const content = wrapper.find('.flex-1')
      expect(content.exists()).toBe(true)
    })
  })

  describe('Metadata', () => {
    it('renders without metadata', () => {
      const activity: Activity = {
        id: '1',
        type: 'invitation-sent',
        timestamp: 'now',
        description: 'Test',
      }

      expect(() => {
        mount(ActivityItem, {
          props: { activity },
        })
      }).not.toThrow()
    })

    it('renders with metadata', () => {
      const wrapper = mount(ActivityItem, {
        props: {
          activity: mockActivity,
        },
      })

      expect(wrapper.text()).toContain('Sarah Chen accepted invitation')
    })
  })
})
