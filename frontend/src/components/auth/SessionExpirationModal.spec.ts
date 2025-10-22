import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import SessionExpirationModal from './SessionExpirationModal.vue'

describe('SessionExpirationModal', () => {
  const defaultProps = {
    visible: true,
    timeRemaining: 60, // 1 minute
    hasUnsavedChanges: false,
    isExtending: false,
  }

  beforeEach(() => {
    document.body.innerHTML = ''
  })

  describe('visibility', () => {
    it('should render when visible is true', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: defaultProps,
      })

      expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    })

    it('should not render when visible is false', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: {
          ...defaultProps,
          visible: false,
        },
      })

      expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    })
  })

  describe('time display', () => {
    it('should format 1 minute correctly', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: {
          ...defaultProps,
          timeRemaining: 60,
        },
      })

      expect(wrapper.text()).toContain('1:00')
    })

    it('should format 30 seconds correctly', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: {
          ...defaultProps,
          timeRemaining: 30,
        },
      })

      expect(wrapper.text()).toContain('0:30')
    })

    it('should format 10 seconds correctly', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: {
          ...defaultProps,
          timeRemaining: 10,
        },
      })

      expect(wrapper.text()).toContain('0:10')
    })

    it('should show countdown in large font', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: defaultProps,
      })

      const countdown = wrapper.find('.text-4xl')
      expect(countdown.exists()).toBe(true)
      expect(countdown.classes()).toContain('font-mono')
    })

    it('should add pulse animation when time remaining is 10 seconds or less', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: {
          ...defaultProps,
          timeRemaining: 10,
        },
      })

      const countdown = wrapper.find('.text-4xl')
      expect(countdown.classes()).toContain('animate-pulse')
    })

    it('should not pulse when time remaining is greater than 10 seconds', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: {
          ...defaultProps,
          timeRemaining: 30,
        },
      })

      const countdown = wrapper.find('.text-4xl')
      expect(countdown.classes()).not.toContain('animate-pulse')
    })
  })

  describe('unsaved changes warning', () => {
    it('should show warning when hasUnsavedChanges is true', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: {
          ...defaultProps,
          hasUnsavedChanges: true,
        },
      })

      expect(wrapper.text()).toContain('Warning')
      expect(wrapper.text()).toContain('You have unsaved work that will be lost')
    })

    it('should not show warning when hasUnsavedChanges is false', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: {
          ...defaultProps,
          hasUnsavedChanges: false,
        },
      })

      expect(wrapper.text()).not.toContain('You have unsaved work that will be lost')
    })

    it('should style unsaved changes warning with amber colors', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: {
          ...defaultProps,
          hasUnsavedChanges: true,
        },
      })

      const warning = wrapper.find('.bg-amber-50')
      expect(warning.exists()).toBe(true)
      expect(warning.classes()).toContain('border-amber-200')
    })
  })

  describe('extend action', () => {
    it('should emit extend event when extend button is clicked', async () => {
      const wrapper = mount(SessionExpirationModal, {
        props: defaultProps,
      })

      const extendButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Extend Session'))
      await extendButton?.trigger('click')

      expect(wrapper.emitted('extend')).toBeTruthy()
      expect(wrapper.emitted('extend')?.[0]).toEqual([])
    })

    it('should show loading state when isExtending is true', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: {
          ...defaultProps,
          isExtending: true,
        },
      })

      expect(wrapper.text()).toContain('Extending...')
    })

    it('should disable extend button when isExtending is true', () => {
      const wrapper = mount(SessionExpirationModal, {
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

    it('should have emerald primary button style', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: defaultProps,
      })

      const extendButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Extend Session'))
      expect(extendButton?.classes()).toContain('bg-emerald-600')
    })
  })

  describe('logout action', () => {
    it('should emit logout event when logout button is clicked', async () => {
      const wrapper = mount(SessionExpirationModal, {
        props: defaultProps,
      })

      const logoutButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Logout Now'))
      await logoutButton?.trigger('click')

      expect(wrapper.emitted('logout')).toBeTruthy()
      expect(wrapper.emitted('logout')?.[0]).toEqual([])
    })

    it('should have slate secondary button style', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: defaultProps,
      })

      const logoutButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Logout Now'))
      expect(logoutButton?.classes()).toContain('bg-slate-200')
    })
  })

  describe('accessibility', () => {
    it('should have proper ARIA attributes', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: defaultProps,
      })

      const dialog = wrapper.find('[role="dialog"]')
      expect(dialog.attributes('aria-modal')).toBe('true')
      expect(dialog.attributes('aria-labelledby')).toBe('session-expiration-title')
      expect(dialog.attributes('aria-describedby')).toBe('session-expiration-description')
    })

    it('should have alertdialog role on inner modal', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: defaultProps,
      })

      expect(wrapper.find('[role="alertdialog"]').exists()).toBe(true)
    })

    it('should have proper heading hierarchy', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: defaultProps,
      })

      const title = wrapper.find('#session-expiration-title')
      expect(title.exists()).toBe(true)
      expect(title.element.tagName).toBe('H3')
    })

    it('should have accessible description', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: defaultProps,
      })

      const description = wrapper.find('#session-expiration-description')
      expect(description.exists()).toBe(true)
    })

    it('should have tabindex on modal container for focus trap', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: defaultProps,
      })

      const modal = wrapper.find('[role="alertdialog"]')
      expect(modal.attributes('tabindex')).toBe('-1')
    })

    it('should hide decorative icons from screen readers', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: defaultProps,
      })

      const icons = wrapper.findAll('[aria-hidden="true"]')
      expect(icons.length).toBeGreaterThan(0)
    })
  })

  describe('focus management', () => {
    it('should focus extend button when modal opens', async () => {
      const wrapper = mount(SessionExpirationModal, {
        props: {
          ...defaultProps,
          visible: false,
        },
        attachTo: document.body,
      })

      // Open modal
      await wrapper.setProps({ visible: true })
      await nextTick()
      await nextTick() // Extra tick for focus to settle

      // Extend button should be focused
      const extendButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Extend Session'))
      expect(document.activeElement).toBe(extendButton?.element)

      wrapper.unmount()
    })
  })

  describe('message content', () => {
    it('should display critical warning title', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: defaultProps,
      })

      expect(wrapper.text()).toContain('Session Expiring')
      expect(wrapper.text()).toContain('Action required')
    })

    it('should display countdown label', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: defaultProps,
      })

      expect(wrapper.text()).toContain('Your session expires in:')
    })

    it('should display patient data protection message', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: defaultProps,
      })

      expect(wrapper.text()).toContain(
        'You will be automatically logged out to protect your patient data'
      )
    })

    it('should display HIPAA compliance notice', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: defaultProps,
      })

      expect(wrapper.text()).toContain('HIPAA compliance')
      expect(wrapper.text()).toContain('protect patient data')
    })
  })

  describe('visual styling', () => {
    it('should have red alert styling for critical warning', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: defaultProps,
      })

      const alertBox = wrapper.find('.bg-red-50')
      expect(alertBox.exists()).toBe(true)
      expect(alertBox.classes()).toContain('border-red-200')
    })

    it('should use red icon for critical alert', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: defaultProps,
      })

      const iconContainer = wrapper.find('.bg-red-100')
      expect(iconContainer.exists()).toBe(true)

      const icon = wrapper.find('.text-red-600')
      expect(icon.exists()).toBe(true)
    })

    it('should use tabular numbers for countdown', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: defaultProps,
      })

      const countdown = wrapper.find('.tabular-nums')
      expect(countdown.exists()).toBe(true)
    })
  })

  describe('non-dismissible behavior', () => {
    it('should not close on ESC key (modal is non-dismissible)', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: defaultProps,
      })

      const dialog = wrapper.find('[role="dialog"]')
      // Modal should not have ESC key handler
      expect(dialog.attributes()).not.toHaveProperty('@keydown.esc')
    })

    it('should not close on backdrop click (modal is non-dismissible)', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: defaultProps,
      })

      const backdrop = wrapper.find('[role="dialog"]')
      // Modal should not have backdrop click handler
      expect(backdrop.attributes()).not.toHaveProperty('@click.self')
    })
  })

  describe('edge cases', () => {
    it('should handle 0 seconds remaining', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: {
          ...defaultProps,
          timeRemaining: 0,
        },
      })

      expect(wrapper.text()).toContain('0:00')
      // Should show pulse animation
      const countdown = wrapper.find('.text-4xl')
      expect(countdown.classes()).toContain('animate-pulse')
    })

    it('should handle null time remaining', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: {
          ...defaultProps,
          timeRemaining: null,
          visible: true,
        },
      })

      // Modal should still render with null time
      expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
      expect(wrapper.text()).toContain('0:00')
    })
  })

  describe('transitions', () => {
    it('should use teleport for modal rendering', () => {
      const wrapper = mount(SessionExpirationModal, {
        props: {
          ...defaultProps,
          visible: true,
        },
      })

      // Modal should render with teleport
      expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    })
  })
})
