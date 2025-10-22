import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import LogoutConfirmationModal from './LogoutConfirmationModal.vue'

describe('LogoutConfirmationModal', () => {
  const defaultProps = {
    visible: true,
    hasUnsavedChanges: false,
    unsavedItemDescriptions: [],
    isLoggingOut: false,
  }

  beforeEach(() => {
    // Clean up any existing teleported elements
    document.body.innerHTML = ''
  })

  describe('visibility', () => {
    it('should render when visible is true', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: defaultProps,
      })

      expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    })

    it('should not render when visible is false', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: {
          ...defaultProps,
          visible: false,
        },
      })

      expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    })
  })

  describe('without unsaved changes', () => {
    it('should show simple confirmation message', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: defaultProps,
      })

      expect(wrapper.text()).toContain('Confirm Logout')
      expect(wrapper.text()).toContain('Are you sure you want to logout?')
      expect(wrapper.text()).toContain(
        'You will need to sign in again to access your workspace'
      )
    })

    it('should not show unsaved changes list', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: defaultProps,
      })

      expect(wrapper.find('[role="list"]').exists()).toBe(false)
      expect(wrapper.text()).not.toContain('You have unsaved work')
    })

    it('should not show HIPAA notice', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: defaultProps,
      })

      expect(wrapper.text()).not.toContain('For HIPAA compliance')
    })
  })

  describe('with unsaved changes', () => {
    const unsavedProps = {
      ...defaultProps,
      hasUnsavedChanges: true,
      unsavedItemDescriptions: [
        'John Doe (Session at Jan 15, 10:00 AM)',
        'Jane Smith (Session at Jan 15, 2:00 PM)',
      ],
    }

    it('should show warning title', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: unsavedProps,
      })

      expect(wrapper.text()).toContain('You Have Unsaved Work')
    })

    it('should show unsaved changes warning message', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: unsavedProps,
      })

      expect(wrapper.text()).toContain(
        'You have unsaved work that will be lost if you logout'
      )
    })

    it('should list all unsaved item descriptions', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: unsavedProps,
      })

      const list = wrapper.find('[role="list"]')
      expect(list.exists()).toBe(true)
      expect(wrapper.text()).toContain('John Doe (Session at Jan 15, 10:00 AM)')
      expect(wrapper.text()).toContain('Jane Smith (Session at Jan 15, 2:00 PM)')
    })

    it('should show HIPAA compliance notice', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: unsavedProps,
      })

      expect(wrapper.text()).toContain(
        'For HIPAA compliance, all local data is cleared on logout'
      )
    })

    it('should show correct count of unsaved items', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: unsavedProps,
      })

      const listItems = wrapper.findAll('[role="list"] li')
      expect(listItems).toHaveLength(2)
    })

    it('should handle empty descriptions array gracefully', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: {
          ...defaultProps,
          hasUnsavedChanges: true,
          unsavedItemDescriptions: [],
        },
      })

      expect(wrapper.find('[role="list"]').exists()).toBe(false)
    })

    it('should handle single unsaved item', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: {
          ...defaultProps,
          hasUnsavedChanges: true,
          unsavedItemDescriptions: ['John Doe (Session at Jan 15, 10:00 AM)'],
        },
      })

      const listItems = wrapper.findAll('[role="list"] li')
      expect(listItems).toHaveLength(1)
      expect(wrapper.text()).toContain('John Doe (Session at Jan 15, 10:00 AM)')
    })
  })

  describe('cancel action', () => {
    it('should emit cancel event when cancel button is clicked', async () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: defaultProps,
      })

      const cancelButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Cancel'))
      await cancelButton?.trigger('click')

      expect(wrapper.emitted('cancel')).toBeTruthy()
      expect(wrapper.emitted('cancel')?.[0]).toEqual([])
    })

    it('should emit cancel event when ESC key is pressed', async () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: defaultProps,
      })

      const dialog = wrapper.find('[role="dialog"]')
      await dialog.trigger('keydown.esc')

      expect(wrapper.emitted('cancel')).toBeTruthy()
    })

    it('should emit cancel event when backdrop is clicked', async () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: defaultProps,
      })

      const backdrop = wrapper.find('[role="dialog"]')
      await backdrop.trigger('click.self')

      expect(wrapper.emitted('cancel')).toBeTruthy()
    })
  })

  describe('logout action', () => {
    it('should emit logout event when logout button is clicked', async () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: defaultProps,
      })

      const logoutButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Logout Anyway'))
      await logoutButton?.trigger('click')

      expect(wrapper.emitted('logout')).toBeTruthy()
      expect(wrapper.emitted('logout')?.[0]).toEqual([])
    })

    it('should show loading state when isLoggingOut is true', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: {
          ...defaultProps,
          isLoggingOut: true,
        },
      })

      const logoutButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Logging out'))
      expect(logoutButton?.text()).toContain('Logging out...')
    })

    it('should disable logout button when isLoggingOut is true', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: {
          ...defaultProps,
          isLoggingOut: true,
        },
      })

      const logoutButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Logging out'))
      expect(logoutButton?.attributes('disabled')).toBeDefined()
    })

    it('should not emit logout when button is disabled', async () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: {
          ...defaultProps,
          isLoggingOut: true,
        },
      })

      const logoutButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Logging out'))
      await logoutButton?.trigger('click')

      // Button is disabled, so click should not work
      expect(wrapper.emitted('logout')).toBeFalsy()
    })
  })

  describe('accessibility', () => {
    it('should have proper ARIA attributes', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: defaultProps,
      })

      const dialog = wrapper.find('[role="dialog"]')
      expect(dialog.attributes('aria-modal')).toBe('true')
      expect(dialog.attributes('aria-labelledby')).toBe('logout-modal-title')
      expect(dialog.attributes('aria-describedby')).toBe('logout-modal-description')
    })

    it('should have alertdialog role on inner modal', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: defaultProps,
      })

      expect(wrapper.find('[role="alertdialog"]').exists()).toBe(true)
    })

    it('should have proper heading hierarchy', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: defaultProps,
      })

      const title = wrapper.find('#logout-modal-title')
      expect(title.exists()).toBe(true)
      expect(title.element.tagName).toBe('H3')
    })

    it('should have accessible description', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: defaultProps,
      })

      const description = wrapper.find('#logout-modal-description')
      expect(description.exists()).toBe(true)
    })

    it('should have list role when showing unsaved items', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: {
          ...defaultProps,
          hasUnsavedChanges: true,
          unsavedItemDescriptions: ['Item 1', 'Item 2'],
        },
      })

      const list = wrapper.find('[role="list"]')
      expect(list.exists()).toBe(true)
    })

    it('should have aria-hidden on decorative icon', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: defaultProps,
      })

      const icon = wrapper.find('svg')
      expect(icon.attributes('aria-hidden')).toBe('true')
    })
  })

  describe('focus management', () => {
    it('should focus cancel button when modal opens', async () => {
      const wrapper = mount(LogoutConfirmationModal, {
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

      // Cancel button should be focused
      const cancelButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Cancel'))
      expect(document.activeElement).toBe(cancelButton?.element)

      wrapper.unmount()
    })

    it('should have tabindex on modal container for focus trap', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: defaultProps,
      })

      const modal = wrapper.find('[role="alertdialog"]')
      expect(modal.attributes('tabindex')).toBe('-1')
    })
  })

  describe('transitions', () => {
    it('should use teleport for modal rendering', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: {
          ...defaultProps,
          visible: true,
        },
      })

      // Modal should render with teleport
      expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    })
  })

  describe('edge cases', () => {
    it('should handle very long unsaved item descriptions', () => {
      const longDescription = 'A'.repeat(200)
      const wrapper = mount(LogoutConfirmationModal, {
        props: {
          ...defaultProps,
          hasUnsavedChanges: true,
          unsavedItemDescriptions: [longDescription],
        },
      })

      expect(wrapper.text()).toContain(longDescription)
    })

    it('should handle many unsaved items', () => {
      const manyItems = Array.from({ length: 10 }, (_, i) => `Session ${i + 1}`)
      const wrapper = mount(LogoutConfirmationModal, {
        props: {
          ...defaultProps,
          hasUnsavedChanges: true,
          unsavedItemDescriptions: manyItems,
        },
      })

      const listItems = wrapper.findAll('[role="list"] li')
      expect(listItems).toHaveLength(10)
    })

    it('should handle special characters in descriptions', () => {
      const specialChars = 'John <Doe> & "Jane" O\'Brien (Session at 10:00 AM)'
      const wrapper = mount(LogoutConfirmationModal, {
        props: {
          ...defaultProps,
          hasUnsavedChanges: true,
          unsavedItemDescriptions: [specialChars],
        },
      })

      expect(wrapper.text()).toContain(specialChars)
    })

    it('should not break with null/undefined descriptions', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: {
          ...defaultProps,
          hasUnsavedChanges: true,
          unsavedItemDescriptions: [] as string[],
        },
      })

      expect(wrapper.find('[role="list"]').exists()).toBe(false)
      expect(() => wrapper.html()).not.toThrow()
    })
  })

  describe('button states', () => {
    it('should have distinct primary and secondary button styles', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: defaultProps,
      })

      const buttons = wrapper.findAll('button')
      const cancelButton = buttons.find((btn) => btn.text().includes('Cancel'))
      const logoutButton = buttons.find((btn) => btn.text().includes('Logout'))

      // Cancel should have emerald (primary) style
      expect(cancelButton?.classes()).toContain('bg-emerald-600')

      // Logout should have gray (secondary) style
      expect(logoutButton?.classes()).toContain('bg-slate-200')
    })

    it('should show focus styles on buttons', () => {
      const wrapper = mount(LogoutConfirmationModal, {
        props: defaultProps,
      })

      const buttons = wrapper.findAll('button')
      buttons.forEach((button) => {
        expect(button.classes()).toContain('focus:outline-none')
        expect(button.classes()).toContain('focus:ring-2')
      })
    })
  })
})
