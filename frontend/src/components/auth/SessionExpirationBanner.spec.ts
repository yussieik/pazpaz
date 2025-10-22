import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import SessionExpirationBanner from './SessionExpirationBanner.vue'

describe('SessionExpirationBanner', () => {
  const defaultProps = {
    visible: true,
    timeRemaining: 300, // 5 minutes
    isExtending: false,
  }

  beforeEach(() => {
    document.body.innerHTML = ''
  })

  describe('visibility', () => {
    it('should render when visible is true', () => {
      const wrapper = mount(SessionExpirationBanner, {
        props: defaultProps,
      })

      expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    })

    it('should not render when visible is false', () => {
      const wrapper = mount(SessionExpirationBanner, {
        props: {
          ...defaultProps,
          visible: false,
        },
      })

      expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    })
  })

  describe('time display', () => {
    it('should format 5 minutes correctly', () => {
      const wrapper = mount(SessionExpirationBanner, {
        props: {
          ...defaultProps,
          timeRemaining: 300,
        },
      })

      expect(wrapper.text()).toContain('5:00')
    })

    it('should format 4:30 correctly', () => {
      const wrapper = mount(SessionExpirationBanner, {
        props: {
          ...defaultProps,
          timeRemaining: 270,
        },
      })

      expect(wrapper.text()).toContain('4:30')
    })

    it('should format less than 1 minute correctly', () => {
      const wrapper = mount(SessionExpirationBanner, {
        props: {
          ...defaultProps,
          timeRemaining: 45,
        },
      })

      expect(wrapper.text()).toContain('0:45')
    })

    it('should pad seconds with leading zero', () => {
      const wrapper = mount(SessionExpirationBanner, {
        props: {
          ...defaultProps,
          timeRemaining: 125, // 2:05
        },
      })

      expect(wrapper.text()).toContain('2:05')
    })

    it('should handle null time remaining', () => {
      const wrapper = mount(SessionExpirationBanner, {
        props: {
          ...defaultProps,
          timeRemaining: null,
        },
      })

      expect(wrapper.text()).toContain('0:00')
    })
  })

  describe('extend action', () => {
    it('should emit extend event when link is clicked', async () => {
      const wrapper = mount(SessionExpirationBanner, {
        props: defaultProps,
      })

      const extendLink = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Click here to extend'))
      await extendLink?.trigger('click')

      expect(wrapper.emitted('extend')).toBeTruthy()
      expect(wrapper.emitted('extend')?.[0]).toEqual([])
    })

    it('should show loading state when isExtending is true', () => {
      const wrapper = mount(SessionExpirationBanner, {
        props: {
          ...defaultProps,
          isExtending: true,
        },
      })

      expect(wrapper.text()).toContain('Extending...')
    })

    it('should disable extend button when isExtending is true', () => {
      const wrapper = mount(SessionExpirationBanner, {
        props: {
          ...defaultProps,
          isExtending: true,
        },
      })

      const extendButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Extending'))
      expect(extendButton?.attributes('disabled')).toBeDefined()
    })
  })

  describe('dismiss action', () => {
    it('should emit dismiss event when dismiss button is clicked', async () => {
      const wrapper = mount(SessionExpirationBanner, {
        props: defaultProps,
      })

      const dismissButton = wrapper.find('[aria-label="Dismiss warning"]')
      await dismissButton.trigger('click')

      expect(wrapper.emitted('dismiss')).toBeTruthy()
      expect(wrapper.emitted('dismiss')?.[0]).toEqual([])
    })
  })

  describe('accessibility', () => {
    it('should have proper ARIA attributes', () => {
      const wrapper = mount(SessionExpirationBanner, {
        props: defaultProps,
      })

      const banner = wrapper.find('[role="alert"]')
      expect(banner.attributes('aria-live')).toBe('polite')
      expect(banner.attributes('aria-atomic')).toBe('true')
    })

    it('should have accessible dismiss button', () => {
      const wrapper = mount(SessionExpirationBanner, {
        props: defaultProps,
      })

      const dismissButton = wrapper.find('[aria-label="Dismiss warning"]')
      expect(dismissButton.exists()).toBe(true)
    })

    it('should hide decorative icons from screen readers', () => {
      const wrapper = mount(SessionExpirationBanner, {
        props: defaultProps,
      })

      const icons = wrapper.findAll('[aria-hidden="true"]')
      expect(icons.length).toBeGreaterThan(0)
    })
  })

  describe('message content', () => {
    it('should display warning message', () => {
      const wrapper = mount(SessionExpirationBanner, {
        props: defaultProps,
      })

      expect(wrapper.text()).toContain('Session expiring soon')
      expect(wrapper.text()).toContain('Your session will expire in')
    })

    it('should display monospace formatted time', () => {
      const wrapper = mount(SessionExpirationBanner, {
        props: defaultProps,
      })

      const timeElement = wrapper.find('.font-mono')
      expect(timeElement.exists()).toBe(true)
      expect(timeElement.text()).toContain('5:00')
    })
  })

  describe('transitions', () => {
    it('should render when visible', () => {
      const wrapper = mount(SessionExpirationBanner, {
        props: {
          ...defaultProps,
          visible: true,
        },
      })

      expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    })
  })

  describe('edge cases', () => {
    it('should handle 0 seconds remaining', () => {
      const wrapper = mount(SessionExpirationBanner, {
        props: {
          ...defaultProps,
          timeRemaining: 0,
        },
      })

      expect(wrapper.text()).toContain('0:00')
    })

    it('should handle negative time remaining', () => {
      const wrapper = mount(SessionExpirationBanner, {
        props: {
          ...defaultProps,
          timeRemaining: -10,
        },
      })

      // Should not crash - will show negative or 0
      expect(() => wrapper.text()).not.toThrow()
    })

    it('should handle very large time remaining', () => {
      const wrapper = mount(SessionExpirationBanner, {
        props: {
          ...defaultProps,
          timeRemaining: 3600, // 60 minutes
        },
      })

      expect(wrapper.text()).toContain('60:00')
    })
  })
})
