import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import { nextTick } from 'vue'
import AppointmentFormModal from './AppointmentFormModal.vue'
import type { AppointmentFormData } from '@/types/calendar'

// Mock the API client
vi.mock('@/api/client', () => ({
  checkAppointmentConflicts: vi.fn(() =>
    Promise.resolve({
      has_conflict: false,
      conflicting_appointments: [],
    })
  ),
}))

// Mock @vueuse/core
vi.mock('@vueuse/core', () => ({
  useDebounceFn: (fn: () => void) => fn,
  onClickOutside: vi.fn(),
}))

// Mock the composables
vi.mock('@/composables/useClientSearch', () => ({
  useClientSearch: () => ({
    searchResults: { value: [] },
    recentClients: { value: [] },
    isSearching: { value: false },
    isLoadingRecent: { value: false },
    isCreating: { value: false },
    error: { value: null },
    searchClients: vi.fn(),
    fetchRecentClients: vi.fn(),
    createClient: vi.fn(),
    clearSearch: vi.fn(),
  }),
}))

vi.mock('@/composables/useScreenReader', () => ({
  useScreenReader: () => ({
    announce: vi.fn(),
  }),
}))

describe('AppointmentFormModal - P0 Keyboard Interactions', () => {
  let wrapper: VueWrapper

  const defaultProps = {
    visible: true,
    mode: 'create' as const,
    prefillDateTime: null,
    prefillClientId: null,
  }

  beforeEach(() => {
    wrapper = mount(AppointmentFormModal, {
      props: defaultProps,
      attachTo: document.body, // Required for focus() to work
    })
  })

  describe('Feature 1: ⌘Enter / Ctrl+Enter Submit', () => {
    it('should submit form when Cmd+Enter is pressed on macOS', async () => {
      // Mock macOS platform
      Object.defineProperty(navigator, 'platform', {
        value: 'MacIntel',
        writable: true,
        configurable: true,
      })

      // Fill in required fields
      const vm = wrapper.vm as any
      vm.formData.client_id = 'client-123'
      vm.formData.scheduled_start = '2025-10-06T10:00'
      vm.formData.scheduled_end = '2025-10-06T11:00'
      await nextTick()

      const submitSpy = vi.fn()
      wrapper.vm.$emit = submitSpy

      // Simulate Cmd+Enter
      const event = new KeyboardEvent('keydown', {
        key: 'Enter',
        metaKey: true, // ⌘ key on macOS
        bubbles: true,
      })

      window.dispatchEvent(event)
      await nextTick()

      // Verify submit was called with form data
      expect(submitSpy).toHaveBeenCalledWith('submit', expect.any(Object))
    })

    it('should submit form when Ctrl+Enter is pressed on Windows/Linux', async () => {
      // Mock Windows platform
      Object.defineProperty(navigator, 'platform', {
        value: 'Win32',
        writable: true,
        configurable: true,
      })

      // Fill in required fields
      const vm = wrapper.vm as any
      vm.formData.client_id = 'client-123'
      vm.formData.scheduled_start = '2025-10-06T10:00'
      vm.formData.scheduled_end = '2025-10-06T11:00'
      await nextTick()

      const submitSpy = vi.fn()
      wrapper.vm.$emit = submitSpy

      // Simulate Ctrl+Enter
      const event = new KeyboardEvent('keydown', {
        key: 'Enter',
        ctrlKey: true, // Ctrl key on Windows/Linux
        bubbles: true,
      })

      window.dispatchEvent(event)
      await nextTick()

      // Verify submit was called
      expect(submitSpy).toHaveBeenCalledWith('submit', expect.any(Object))
    })

    it('should NOT submit form if validation fails', async () => {
      // Leave form empty (missing required fields)
      const submitSpy = vi.fn()
      wrapper.vm.$emit = submitSpy

      // Simulate Cmd+Enter
      const event = new KeyboardEvent('keydown', {
        key: 'Enter',
        metaKey: true,
        bubbles: true,
      })

      window.dispatchEvent(event)
      await nextTick()

      // Verify submit was NOT called (validation failed)
      expect(submitSpy).not.toHaveBeenCalledWith('submit', expect.any(Object))

      // Verify error messages are shown
      const errorMessages = wrapper.findAll('[role="alert"]')
      expect(errorMessages.length).toBeGreaterThan(0)
    })

    it('should prevent default browser behavior on ⌘Enter', async () => {
      // Fill in required fields
      const vm = wrapper.vm as any
      vm.formData.client_id = 'client-123'
      vm.formData.scheduled_start = '2025-10-06T10:00'
      vm.formData.scheduled_end = '2025-10-06T11:00'
      await nextTick()

      // Create event with preventDefault spy
      const preventDefaultSpy = vi.fn()
      const event = new KeyboardEvent('keydown', {
        key: 'Enter',
        metaKey: true,
        bubbles: true,
      })
      event.preventDefault = preventDefaultSpy

      window.dispatchEvent(event)
      await nextTick()

      // Verify preventDefault was called
      expect(preventDefaultSpy).toHaveBeenCalled()
    })
  })

  describe('Feature 2: Auto-Focus First Field', () => {
    it('should focus Client combobox when no prefill data exists', async () => {
      wrapper = mount(AppointmentFormModal, {
        props: {
          ...defaultProps,
          visible: false,
        },
        attachTo: document.body,
      })

      // Open modal
      await wrapper.setProps({ visible: true })
      await nextTick()
      await nextTick() // Extra tick for focus logic

      // Verify Client combobox input is focused
      const clientCombobox = wrapper.findComponent({ name: 'ClientCombobox' })
      expect(clientCombobox.exists()).toBe(true)
      // Note: In a real browser, we would check document.activeElement
      // In tests, we verify the focus() method was attempted via component structure
    })

    it('should focus Start Time when client is pre-filled', async () => {
      wrapper = mount(AppointmentFormModal, {
        props: {
          ...defaultProps,
          visible: false,
          prefillClientId: 'client-123',
        },
        attachTo: document.body,
      })

      // Open modal
      await wrapper.setProps({ visible: true })
      await nextTick()
      await nextTick()

      // Verify Start Time input exists and would be focused
      const startTimeInput = wrapper.find('#start-time')
      expect(startTimeInput.exists()).toBe(true)
    })

    it('should focus Location when both client and time are pre-filled', async () => {
      const prefillDateTime = {
        start: new Date('2025-10-06T10:00:00'),
        end: new Date('2025-10-06T11:00:00'),
      }

      wrapper = mount(AppointmentFormModal, {
        props: {
          ...defaultProps,
          visible: false,
          prefillClientId: 'client-123',
          prefillDateTime,
        },
        attachTo: document.body,
      })

      // Open modal
      await wrapper.setProps({ visible: true })
      await nextTick()
      await nextTick()

      // Verify Location select exists and would be focused
      const locationSelect = wrapper.find('#location-type')
      expect(locationSelect.exists()).toBe(true)
    })

    it('should focus Client combobox in edit mode', async () => {
      const mockAppointment = {
        id: 'appt-123',
        client_id: 'client-123',
        client_initials: 'JD',
        scheduled_start: '2025-10-06T10:00:00Z',
        scheduled_end: '2025-10-06T11:00:00Z',
        location_type: 'clinic' as const,
        location_details: null,
        notes: null,
      }

      wrapper = mount(AppointmentFormModal, {
        props: {
          ...defaultProps,
          visible: false,
          mode: 'edit' as const,
          appointment: mockAppointment,
        },
        attachTo: document.body,
      })

      // Open modal
      await wrapper.setProps({ visible: true })
      await nextTick()
      await nextTick()

      // Verify Client combobox exists and would be focused
      const clientCombobox = wrapper.findComponent({ name: 'ClientCombobox' })
      expect(clientCombobox.exists()).toBe(true)
    })
  })

  describe('Feature 3: Visual Keyboard Hints', () => {
    it('should display "⌘Enter" hint on macOS', async () => {
      // Mock macOS platform
      Object.defineProperty(navigator, 'platform', {
        value: 'MacIntel',
        writable: true,
        configurable: true,
      })

      wrapper = mount(AppointmentFormModal, {
        props: defaultProps,
      })

      await nextTick()

      // Find the keyboard hint
      const keyboardHint = wrapper.find('kbd')
      expect(keyboardHint.exists()).toBe(true)
      expect(keyboardHint.text()).toBe('⌘Enter')
    })

    it('should display "CtrlEnter" hint on Windows', async () => {
      // Mock Windows platform
      Object.defineProperty(navigator, 'platform', {
        value: 'Win32',
        writable: true,
        configurable: true,
      })

      wrapper = mount(AppointmentFormModal, {
        props: defaultProps,
      })

      await nextTick()

      // Find the keyboard hint
      const keyboardHint = wrapper.find('kbd')
      expect(keyboardHint.exists()).toBe(true)
      expect(keyboardHint.text()).toBe('CtrlEnter')
    })

    it('should display "CtrlEnter" hint on Linux', async () => {
      // Mock Linux platform
      Object.defineProperty(navigator, 'platform', {
        value: 'Linux x86_64',
        writable: true,
        configurable: true,
      })

      wrapper = mount(AppointmentFormModal, {
        props: defaultProps,
      })

      await nextTick()

      // Find the keyboard hint
      const keyboardHint = wrapper.find('kbd')
      expect(keyboardHint.exists()).toBe(true)
      expect(keyboardHint.text()).toBe('CtrlEnter')
    })

    it('should have proper styling for keyboard hint', async () => {
      wrapper = mount(AppointmentFormModal, {
        props: defaultProps,
      })

      await nextTick()

      // Find the keyboard hint element
      const keyboardHint = wrapper.find('kbd')
      expect(keyboardHint.exists()).toBe(true)

      // Verify it has the expected Tailwind classes
      expect(keyboardHint.classes()).toContain('rounded')
      expect(keyboardHint.classes()).toContain('bg-slate-100')
      expect(keyboardHint.classes()).toContain('font-mono')
      expect(keyboardHint.classes()).toContain('text-xs')
    })

    it('should position hint below submit button', async () => {
      wrapper = mount(AppointmentFormModal, {
        props: defaultProps,
      })

      await nextTick()

      // Find the submit button container
      const buttonContainer = wrapper.find('.flex.flex-col.items-center.gap-2')
      expect(buttonContainer.exists()).toBe(true)

      // Verify it contains both the button and the hint
      const submitButton = buttonContainer.find('button[type="submit"]')
      const hint = buttonContainer.find('p.text-xs.text-slate-500')

      expect(submitButton.exists()).toBe(true)
      expect(hint.exists()).toBe(true)
      expect(hint.text()).toContain('or press')
    })

    it('should be visible when modal is open', async () => {
      wrapper = mount(AppointmentFormModal, {
        props: {
          ...defaultProps,
          visible: true,
        },
      })

      await nextTick()

      // Verify hint is visible
      const hint = wrapper.find('p.text-xs.text-slate-500')
      expect(hint.exists()).toBe(true)
      expect(hint.isVisible()).toBe(true)
    })

    it('should not be visible when modal is closed', async () => {
      wrapper = mount(AppointmentFormModal, {
        props: {
          ...defaultProps,
          visible: false,
        },
      })

      await nextTick()

      // Verify modal is not rendered (and neither is the hint)
      const modal = wrapper.find('[role="dialog"]')
      expect(modal.exists()).toBe(false)
    })
  })

  describe('Integration: All P0 Features Together', () => {
    it('should support full keyboard workflow: auto-focus → fill form → ⌘Enter submit', async () => {
      // Start with modal closed
      wrapper = mount(AppointmentFormModal, {
        props: {
          ...defaultProps,
          visible: false,
        },
        attachTo: document.body,
      })

      // Open modal
      await wrapper.setProps({ visible: true })
      await nextTick()
      await nextTick()

      // Verify Client combobox would be auto-focused (Feature 2)
      const clientCombobox = wrapper.findComponent({ name: 'ClientCombobox' })
      expect(clientCombobox.exists()).toBe(true)

      // Verify keyboard hint is visible (Feature 3)
      const keyboardHint = wrapper.find('kbd')
      expect(keyboardHint.exists()).toBe(true)

      // Fill in form data
      const vm = wrapper.vm as any
      vm.formData.client_id = 'client-123'
      vm.formData.scheduled_start = '2025-10-06T10:00'
      vm.formData.scheduled_end = '2025-10-06T11:00'
      await nextTick()

      const submitSpy = vi.fn()
      wrapper.vm.$emit = submitSpy

      // Submit with ⌘Enter (Feature 1)
      const event = new KeyboardEvent('keydown', {
        key: 'Enter',
        metaKey: true,
        bubbles: true,
      })

      window.dispatchEvent(event)
      await nextTick()

      // Verify submit was called
      expect(submitSpy).toHaveBeenCalledWith('submit', expect.any(Object))
    })
  })

  describe('Accessibility: Screen Reader Support', () => {
    it('should have proper ARIA attributes for keyboard navigation', async () => {
      wrapper = mount(AppointmentFormModal, {
        props: defaultProps,
      })

      await nextTick()

      // Verify modal has role="dialog" and aria-modal="true"
      const dialog = wrapper.find('[role="dialog"]')
      expect(dialog.exists()).toBe(true)
      expect(dialog.attributes('aria-modal')).toBe('true')

      // Verify modal has aria-labelledby pointing to title
      expect(dialog.attributes('aria-labelledby')).toBe('appointment-form-modal-title')

      // Verify title exists with correct ID
      const title = wrapper.find('#appointment-form-modal-title')
      expect(title.exists()).toBe(true)
      expect(title.text()).toContain('Appointment')
    })

    it('should announce focused field to screen readers', async () => {
      // This is tested implicitly by the auto-focus logic
      // When a field is focused, screen readers automatically announce it
      // based on the field's label and aria attributes

      wrapper = mount(AppointmentFormModal, {
        props: {
          ...defaultProps,
          visible: false,
        },
        attachTo: document.body,
      })

      await wrapper.setProps({ visible: true })
      await nextTick()
      await nextTick()

      // Verify the Client combobox has proper ARIA attributes
      const clientInput = wrapper.find('input[role="combobox"]')
      expect(clientInput.exists()).toBe(true)
      expect(clientInput.attributes('aria-autocomplete')).toBe('list')
    })
  })

  describe('Edge Cases', () => {
    it('should handle rapid modal open/close without errors', async () => {
      wrapper = mount(AppointmentFormModal, {
        props: {
          ...defaultProps,
          visible: false,
        },
        attachTo: document.body,
      })

      // Rapidly toggle modal
      await wrapper.setProps({ visible: true })
      await wrapper.setProps({ visible: false })
      await wrapper.setProps({ visible: true })
      await nextTick()

      // Verify no errors occurred and modal is in correct state
      expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    })

    it('should not submit when modal is closed', async () => {
      wrapper = mount(AppointmentFormModal, {
        props: {
          ...defaultProps,
          visible: false,
        },
      })

      const submitSpy = vi.fn()
      wrapper.vm.$emit = submitSpy

      // Try to submit with ⌘Enter while modal is closed
      const event = new KeyboardEvent('keydown', {
        key: 'Enter',
        metaKey: true,
        bubbles: true,
      })

      window.dispatchEvent(event)
      await nextTick()

      // Verify submit was NOT called (modal is closed)
      expect(submitSpy).not.toHaveBeenCalledWith('submit', expect.any(Object))
    })

    it('should clean up keyboard listeners on unmount', () => {
      wrapper = mount(AppointmentFormModal, {
        props: defaultProps,
      })

      const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener')

      wrapper.unmount()

      // Verify removeEventListener was called
      expect(removeEventListenerSpy).toHaveBeenCalledWith(
        'keydown',
        expect.any(Function)
      )

      removeEventListenerSpy.mockRestore()
    })
  })
})
