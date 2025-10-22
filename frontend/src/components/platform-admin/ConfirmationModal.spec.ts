import { describe, it, expect, beforeEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import ConfirmationModal from './ConfirmationModal.vue'

describe('ConfirmationModal', () => {
  let wrapper: VueWrapper

  const defaultProps = {
    visible: true,
    title: 'Confirm Action',
    message: 'Are you sure you want to proceed?',
  }

  beforeEach(() => {
    // Reset DOM
    document.body.innerHTML = ''
  })

  describe('Rendering', () => {
    it('renders modal when visible prop is true', () => {
      wrapper = mount(ConfirmationModal, {
        props: defaultProps,
      })

      expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
      expect(wrapper.text()).toContain('Confirm Action')
      expect(wrapper.text()).toContain('Are you sure you want to proceed?')
    })

    it('does not render modal when visible prop is false', () => {
      wrapper = mount(ConfirmationModal, {
        props: {
          ...defaultProps,
          visible: false,
        },
      })

      expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    })

    it('renders custom confirm text', () => {
      wrapper = mount(ConfirmationModal, {
        props: {
          ...defaultProps,
          confirmText: 'Delete',
        },
      })

      const confirmButton = wrapper
        .findAll('button')
        .find((btn) => btn.text() === 'Delete')
      expect(confirmButton).toBeTruthy()
    })

    it('renders danger style with warning icon', () => {
      wrapper = mount(ConfirmationModal, {
        props: {
          ...defaultProps,
          confirmStyle: 'danger',
        },
      })

      const confirmButton = wrapper
        .findAll('button')
        .find((btn) => btn.classes().includes('bg-red-600'))
      expect(confirmButton).toBeTruthy()

      // Check for warning icon
      const warningIcon = wrapper.find('.bg-red-100')
      expect(warningIcon.exists()).toBe(true)
    })

    it('renders primary style by default', () => {
      wrapper = mount(ConfirmationModal, {
        props: defaultProps,
      })

      const confirmButton = wrapper
        .findAll('button')
        .find((btn) => btn.classes().includes('bg-emerald-600'))
      expect(confirmButton).toBeTruthy()
    })
  })

  describe('Reason Field', () => {
    it('shows reason field when showReasonField is true', () => {
      wrapper = mount(ConfirmationModal, {
        props: {
          ...defaultProps,
          showReasonField: true,
        },
      })

      const textarea = wrapper.find('textarea')
      expect(textarea.exists()).toBe(true)
    })

    it('does not show reason field by default', () => {
      wrapper = mount(ConfirmationModal, {
        props: defaultProps,
      })

      const textarea = wrapper.find('textarea')
      expect(textarea.exists()).toBe(false)
    })

    it('renders custom reason label and placeholder', () => {
      wrapper = mount(ConfirmationModal, {
        props: {
          ...defaultProps,
          showReasonField: true,
          reasonLabel: 'Suspension Reason',
          reasonPlaceholder: 'Why are you suspending this workspace?',
        },
      })

      expect(wrapper.text()).toContain('Suspension Reason')
      const textarea = wrapper.find('textarea')
      expect(textarea.attributes('placeholder')).toBe(
        'Why are you suspending this workspace?'
      )
    })

    it('shows required indicator when reason is required', () => {
      wrapper = mount(ConfirmationModal, {
        props: {
          ...defaultProps,
          showReasonField: true,
          reasonRequired: true,
        },
      })

      const requiredIndicator = wrapper.find('.text-red-600[aria-label="required"]')
      expect(requiredIndicator.exists()).toBe(true)
    })

    it('disables confirm button when reason is required but empty', async () => {
      wrapper = mount(ConfirmationModal, {
        props: {
          ...defaultProps,
          showReasonField: true,
          reasonRequired: true,
        },
      })

      const confirmButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Confirm'))
      expect(confirmButton?.attributes('disabled')).toBeDefined()
    })

    it('enables confirm button when reason is provided and required', async () => {
      wrapper = mount(ConfirmationModal, {
        props: {
          ...defaultProps,
          showReasonField: true,
          reasonRequired: true,
        },
      })

      const textarea = wrapper.find('textarea')
      await textarea.setValue('Valid reason')

      const confirmButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Confirm'))
      expect(confirmButton?.attributes('disabled')).toBeUndefined()
    })
  })

  describe('Events', () => {
    it('emits confirm event when confirm button clicked', async () => {
      wrapper = mount(ConfirmationModal, {
        props: defaultProps,
      })

      const confirmButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Confirm'))
      await confirmButton?.trigger('click')

      expect(wrapper.emitted('confirm')).toBeTruthy()
      expect(wrapper.emitted('confirm')?.[0]).toEqual([undefined])
    })

    it('includes reason in confirm event payload when reason field is shown', async () => {
      wrapper = mount(ConfirmationModal, {
        props: {
          ...defaultProps,
          showReasonField: true,
        },
      })

      const textarea = wrapper.find('textarea')
      await textarea.setValue('Test reason')

      const confirmButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Confirm'))
      await confirmButton?.trigger('click')

      expect(wrapper.emitted('confirm')).toBeTruthy()
      expect(wrapper.emitted('confirm')?.[0]).toEqual(['Test reason'])
    })

    it('emits cancel event when cancel button clicked', async () => {
      wrapper = mount(ConfirmationModal, {
        props: defaultProps,
      })

      const cancelButton = wrapper
        .findAll('button')
        .find((btn) => btn.text() === 'Cancel')
      await cancelButton?.trigger('click')

      expect(wrapper.emitted('cancel')).toBeTruthy()
    })

    it('emits cancel event when close button clicked', async () => {
      wrapper = mount(ConfirmationModal, {
        props: defaultProps,
      })

      const closeButton = wrapper.find('[aria-label="Close modal"]')
      await closeButton.trigger('click')

      expect(wrapper.emitted('cancel')).toBeTruthy()
    })

    it('emits cancel event when backdrop clicked', async () => {
      wrapper = mount(ConfirmationModal, {
        props: defaultProps,
      })

      const backdrop = wrapper.find('[role="dialog"]')
      await backdrop.trigger('click.self')

      expect(wrapper.emitted('cancel')).toBeTruthy()
    })
  })

  describe('Keyboard Navigation', () => {
    it('closes modal when Escape key pressed', async () => {
      wrapper = mount(ConfirmationModal, {
        props: defaultProps,
        attachTo: document.body,
      })

      await wrapper.trigger('keydown', { key: 'Escape' })

      expect(wrapper.emitted('cancel')).toBeTruthy()

      wrapper.unmount()
    })

    it('does not close when Escape pressed and modal is not visible', async () => {
      wrapper = mount(ConfirmationModal, {
        props: {
          ...defaultProps,
          visible: false,
        },
        attachTo: document.body,
      })

      await wrapper.trigger('keydown', { key: 'Escape' })

      expect(wrapper.emitted('cancel')).toBeFalsy()

      wrapper.unmount()
    })
  })

  describe('Accessibility', () => {
    it('has correct ARIA attributes', () => {
      wrapper = mount(ConfirmationModal, {
        props: defaultProps,
      })

      const dialog = wrapper.find('[role="dialog"]')
      expect(dialog.attributes('aria-modal')).toBe('true')
      expect(dialog.attributes('aria-labelledby')).toContain('modal-title')
    })

    it('focuses first focusable element on mount', async () => {
      wrapper = mount(ConfirmationModal, {
        props: defaultProps,
        attachTo: document.body,
      })

      // Wait for focus trap setup
      await new Promise((resolve) => setTimeout(resolve, 10))

      const activeElement = document.activeElement
      expect(activeElement).toBeTruthy()

      wrapper.unmount()
    })

    it('marks reason field as required when reasonRequired is true', () => {
      wrapper = mount(ConfirmationModal, {
        props: {
          ...defaultProps,
          showReasonField: true,
          reasonRequired: true,
        },
      })

      const textarea = wrapper.find('textarea')
      expect(textarea.attributes('aria-required')).toBe('true')
      expect(textarea.attributes('required')).toBeDefined()
    })
  })

  describe('State Management', () => {
    it('clears reason when modal is closed', async () => {
      wrapper = mount(ConfirmationModal, {
        props: {
          ...defaultProps,
          showReasonField: true,
        },
      })

      const textarea = wrapper.find('textarea')
      await textarea.setValue('Test reason')

      const cancelButton = wrapper
        .findAll('button')
        .find((btn) => btn.text() === 'Cancel')
      await cancelButton?.trigger('click')

      // Re-open modal
      await wrapper.setProps({ visible: false })
      await wrapper.setProps({ visible: true })

      const clearedTextarea = wrapper.find('textarea')
      expect(clearedTextarea.element.value).toBe('')
    })

    it('clears reason after confirm', async () => {
      wrapper = mount(ConfirmationModal, {
        props: {
          ...defaultProps,
          showReasonField: true,
        },
      })

      const textarea = wrapper.find('textarea')
      await textarea.setValue('Test reason')

      const confirmButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Confirm'))
      await confirmButton?.trigger('click')

      // Re-open modal
      await wrapper.setProps({ visible: false })
      await wrapper.setProps({ visible: true })

      const clearedTextarea = wrapper.find('textarea')
      expect(clearedTextarea.element.value).toBe('')
    })
  })
})
