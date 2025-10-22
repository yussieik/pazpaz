import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ActivityTimeline from './ActivityTimeline.vue'
import ActivityItem, { type Activity } from './ActivityItem.vue'

describe('ActivityTimeline', () => {
  const mockActivities: Activity[] = [
    {
      id: '1',
      type: 'invitation-accepted',
      timestamp: '2 minutes ago',
      description: 'Sarah Chen accepted invitation',
    },
    {
      id: '2',
      type: 'workspace-created',
      timestamp: '1 hour ago',
      description: 'New workspace created: "Zen Massage"',
    },
    {
      id: '3',
      type: 'invitation-expired',
      timestamp: '3 hours ago',
      description: 'Invitation expired: john@example.com',
    },
  ]

  describe('Rendering', () => {
    it('renders timeline title', () => {
      const wrapper = mount(ActivityTimeline, {
        props: {
          activities: mockActivities,
        },
      })

      expect(wrapper.text()).toContain('Recent Activity')
    })

    it('renders all activities', () => {
      const wrapper = mount(ActivityTimeline, {
        props: {
          activities: mockActivities,
        },
      })

      const activityItems = wrapper.findAllComponents(ActivityItem)
      expect(activityItems).toHaveLength(3)
    })

    it('passes correct props to ActivityItem components', () => {
      const wrapper = mount(ActivityTimeline, {
        props: {
          activities: mockActivities,
        },
      })

      const activityItems = wrapper.findAllComponents(ActivityItem)
      expect(activityItems[0].props('activity')).toEqual(mockActivities[0])
      expect(activityItems[1].props('activity')).toEqual(mockActivities[1])
      expect(activityItems[2].props('activity')).toEqual(mockActivities[2])
    })
  })

  describe('Empty State', () => {
    it('shows empty state when no activities', () => {
      const wrapper = mount(ActivityTimeline, {
        props: {
          activities: [],
        },
      })

      expect(wrapper.text()).toContain('No recent activity')
      const activityItems = wrapper.findAllComponents(ActivityItem)
      expect(activityItems).toHaveLength(0)
    })

    it('shows empty state icon when no activities', () => {
      const wrapper = mount(ActivityTimeline, {
        props: {
          activities: [],
        },
      })

      const emptyIcon = wrapper.find('.h-12.w-12.text-slate-400')
      expect(emptyIcon.exists()).toBe(true)
    })

    it('does not show empty state when activities exist', () => {
      const wrapper = mount(ActivityTimeline, {
        props: {
          activities: mockActivities,
        },
      })

      expect(wrapper.text()).not.toContain('No recent activity')
    })
  })

  describe('Loading State', () => {
    it('shows loading skeleton when loading is true', () => {
      const wrapper = mount(ActivityTimeline, {
        props: {
          activities: [],
          loading: true,
        },
      })

      const skeletons = wrapper.findAll('.animate-pulse')
      expect(skeletons.length).toBeGreaterThan(0)
      expect(wrapper.text()).not.toContain('No recent activity')
    })

    it('shows 5 skeleton items during loading', () => {
      const wrapper = mount(ActivityTimeline, {
        props: {
          activities: [],
          loading: true,
        },
      })

      const skeletonRows = wrapper.findAll('.flex.gap-3')
      expect(skeletonRows).toHaveLength(5)
    })

    it('hides activities during loading', () => {
      const wrapper = mount(ActivityTimeline, {
        props: {
          activities: mockActivities,
          loading: true,
        },
      })

      const activityItems = wrapper.findAllComponents(ActivityItem)
      expect(activityItems).toHaveLength(0)
    })

    it('shows activities when loading is false', () => {
      const wrapper = mount(ActivityTimeline, {
        props: {
          activities: mockActivities,
          loading: false,
        },
      })

      const activityItems = wrapper.findAllComponents(ActivityItem)
      expect(activityItems).toHaveLength(3)
      expect(wrapper.findAll('.animate-pulse')).toHaveLength(0)
    })
  })

  describe('Accessibility', () => {
    it('has correct ARIA attributes', () => {
      const wrapper = mount(ActivityTimeline, {
        props: {
          activities: mockActivities,
        },
      })

      const region = wrapper.find('[role="region"]')
      expect(region.exists()).toBe(true)
      expect(region.attributes('aria-label')).toBe('Recent activity timeline')
    })

    it('marks empty state icon as aria-hidden', () => {
      const wrapper = mount(ActivityTimeline, {
        props: {
          activities: [],
        },
      })

      const icon = wrapper.find('[aria-hidden="true"]')
      expect(icon.exists()).toBe(true)
    })
  })

  describe('Styling', () => {
    it('applies correct card styling', () => {
      const wrapper = mount(ActivityTimeline, {
        props: {
          activities: mockActivities,
        },
      })

      const card = wrapper.find('.rounded-xl')
      expect(card.classes()).toContain('border')
      expect(card.classes()).toContain('border-slate-200')
      expect(card.classes()).toContain('bg-white')
      expect(card.classes()).toContain('p-6')
    })

    it('uses correct spacing between activities', () => {
      const wrapper = mount(ActivityTimeline, {
        props: {
          activities: mockActivities,
        },
      })

      const activityList = wrapper.find('.space-y-4')
      expect(activityList.exists()).toBe(true)
    })
  })

  describe('Edge Cases', () => {
    it('handles single activity', () => {
      const wrapper = mount(ActivityTimeline, {
        props: {
          activities: [mockActivities[0]],
        },
      })

      const activityItems = wrapper.findAllComponents(ActivityItem)
      expect(activityItems).toHaveLength(1)
    })

    it('handles large number of activities', () => {
      const manyActivities = Array.from({ length: 50 }, (_, i) => ({
        id: `${i}`,
        type: 'invitation-sent' as const,
        timestamp: `${i} minutes ago`,
        description: `Activity ${i}`,
      }))

      const wrapper = mount(ActivityTimeline, {
        props: {
          activities: manyActivities,
        },
      })

      const activityItems = wrapper.findAllComponents(ActivityItem)
      expect(activityItems).toHaveLength(50)
    })

    it('does not crash with undefined activities', () => {
      expect(() => {
        mount(ActivityTimeline, {
          props: {
            activities: [],
          },
        })
      }).not.toThrow()
    })
  })
})
