import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MetricCard from './MetricCard.vue'

describe('MetricCard', () => {
  describe('Rendering', () => {
    it('renders metric value and title', () => {
      const wrapper = mount(MetricCard, {
        props: {
          title: 'Total Workspaces',
          value: 24,
        },
      })

      expect(wrapper.text()).toContain('Total Workspaces')
      expect(wrapper.text()).toContain('24')
    })

    it('renders string value', () => {
      const wrapper = mount(MetricCard, {
        props: {
          title: 'Status',
          value: 'Active',
        },
      })

      expect(wrapper.text()).toContain('Active')
    })

    it('renders icon when provided', () => {
      const wrapper = mount(MetricCard, {
        props: {
          title: 'Total Workspaces',
          value: 24,
          icon: 'workspaces',
        },
      })

      const iconContainer = wrapper.find('.bg-emerald-100')
      expect(iconContainer.exists()).toBe(true)
    })

    it('does not render icon when not provided', () => {
      const wrapper = mount(MetricCard, {
        props: {
          title: 'Total Workspaces',
          value: 24,
        },
      })

      const iconContainer = wrapper.find('.bg-emerald-100')
      expect(iconContainer.exists()).toBe(false)
    })

    it('renders all icon types correctly', () => {
      const icons = ['workspaces', 'users', 'invitations', 'blacklist'] as const

      icons.forEach((icon) => {
        const wrapper = mount(MetricCard, {
          props: {
            title: 'Test',
            value: 0,
            icon,
          },
        })

        const iconContainer = wrapper.find('.bg-emerald-100')
        expect(iconContainer.exists()).toBe(true)
      })
    })
  })

  describe('Change Indicator', () => {
    it('shows positive change indicator with green color', () => {
      const wrapper = mount(MetricCard, {
        props: {
          title: 'Total Workspaces',
          value: 24,
          change: 12,
          changeType: 'increase',
        },
      })

      expect(wrapper.text()).toContain('12%')
      expect(wrapper.text()).toContain('vs last month')

      const changeText = wrapper.find('.text-emerald-600')
      expect(changeText.exists()).toBe(true)
    })

    it('shows negative change indicator with red color', () => {
      const wrapper = mount(MetricCard, {
        props: {
          title: 'Active Users',
          value: 20,
          change: 5,
          changeType: 'decrease',
        },
      })

      expect(wrapper.text()).toContain('5%')
      expect(wrapper.text()).toContain('vs last month')

      const changeText = wrapper.find('.text-red-600')
      expect(changeText.exists()).toBe(true)
    })

    it('does not show change indicator when change is not provided', () => {
      const wrapper = mount(MetricCard, {
        props: {
          title: 'Total Workspaces',
          value: 24,
        },
      })

      expect(wrapper.text()).not.toContain('vs last month')
    })

    it('displays absolute value of negative change', () => {
      const wrapper = mount(MetricCard, {
        props: {
          title: 'Test',
          value: 100,
          change: -15,
          changeType: 'decrease',
        },
      })

      expect(wrapper.text()).toContain('15%')
    })
  })

  describe('Loading State', () => {
    it('shows loading skeleton when loading is true', () => {
      const wrapper = mount(MetricCard, {
        props: {
          title: 'Total Workspaces',
          value: 24,
          loading: true,
        },
      })

      const skeleton = wrapper.find('.animate-pulse')
      expect(skeleton.exists()).toBe(true)
      expect(wrapper.text()).not.toContain('24')
    })

    it('shows value when loading is false', () => {
      const wrapper = mount(MetricCard, {
        props: {
          title: 'Total Workspaces',
          value: 24,
          loading: false,
        },
      })

      const skeleton = wrapper.find('.animate-pulse')
      expect(skeleton.exists()).toBe(false)
      expect(wrapper.text()).toContain('24')
    })

    it('hides change indicator during loading', () => {
      const wrapper = mount(MetricCard, {
        props: {
          title: 'Total Workspaces',
          value: 24,
          change: 12,
          changeType: 'increase',
          loading: true,
        },
      })

      expect(wrapper.text()).not.toContain('vs last month')
    })
  })

  describe('Accessibility', () => {
    it('has correct ARIA attributes', () => {
      const wrapper = mount(MetricCard, {
        props: {
          title: 'Total Workspaces',
          value: 24,
        },
      })

      const region = wrapper.find('[role="region"]')
      expect(region.exists()).toBe(true)
      expect(region.attributes('aria-label')).toBe('Total Workspaces metric')
    })

    it('marks icon as aria-hidden', () => {
      const wrapper = mount(MetricCard, {
        props: {
          title: 'Total Workspaces',
          value: 24,
          icon: 'workspaces',
        },
      })

      const iconContainer = wrapper.find('[aria-hidden="true"]')
      expect(iconContainer.exists()).toBe(true)
    })
  })

  describe('Styling', () => {
    it('applies hover effect classes', () => {
      const wrapper = mount(MetricCard, {
        props: {
          title: 'Test',
          value: 0,
        },
      })

      const card = wrapper.find('.rounded-xl')
      expect(card.classes()).toContain('hover:shadow-md')
      expect(card.classes()).toContain('transition')
    })

    it('applies correct border and background colors', () => {
      const wrapper = mount(MetricCard, {
        props: {
          title: 'Test',
          value: 0,
        },
      })

      const card = wrapper.find('.rounded-xl')
      expect(card.classes()).toContain('border-slate-200')
      expect(card.classes()).toContain('bg-white')
    })
  })

  describe('Edge Cases', () => {
    it('handles zero value', () => {
      const wrapper = mount(MetricCard, {
        props: {
          title: 'Test',
          value: 0,
        },
      })

      expect(wrapper.text()).toContain('0')
    })

    it('handles zero change', () => {
      const wrapper = mount(MetricCard, {
        props: {
          title: 'Test',
          value: 100,
          change: 0,
          changeType: 'increase',
        },
      })

      expect(wrapper.text()).toContain('0%')
    })

    it('handles large numbers', () => {
      const wrapper = mount(MetricCard, {
        props: {
          title: 'Test',
          value: 999999,
        },
      })

      expect(wrapper.text()).toContain('999999')
    })

    it('handles long titles gracefully', () => {
      const wrapper = mount(MetricCard, {
        props: {
          title: 'This is a very long metric title that should still display properly',
          value: 42,
        },
      })

      expect(wrapper.text()).toContain('This is a very long metric title')
    })
  })
})
