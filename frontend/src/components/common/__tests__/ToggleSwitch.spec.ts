/**
 * ToggleSwitch Component Tests
 *
 * Tests for the ToggleSwitch component including:
 * - Rendering and basic functionality
 * - Keyboard accessibility (Space/Enter)
 * - ARIA attributes
 * - Disabled state
 */

import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ToggleSwitch from '../ToggleSwitch.vue'

describe('ToggleSwitch', () => {
  describe('Rendering', () => {
    it('renders correctly when off', () => {
      const wrapper = mount(ToggleSwitch, {
        props: {
          modelValue: false,
          label: 'Test toggle',
        },
      })

      const button = wrapper.find('button')
      expect(button.exists()).toBe(true)
      expect(button.attributes('role')).toBe('switch')
      expect(button.attributes('aria-checked')).toBe('false')
      expect(button.classes()).toContain('bg-slate-300')
    })

    it('renders correctly when on', () => {
      const wrapper = mount(ToggleSwitch, {
        props: {
          modelValue: true,
          label: 'Test toggle',
        },
      })

      const button = wrapper.find('button')
      expect(button.attributes('aria-checked')).toBe('true')
      expect(button.classes()).toContain('bg-emerald-600')
    })

    it('renders with label for screen readers', () => {
      const wrapper = mount(ToggleSwitch, {
        props: {
          modelValue: false,
          label: 'Enable notifications',
        },
      })

      const button = wrapper.find('button')
      expect(button.attributes('aria-label')).toBe('Enable notifications')
      expect(wrapper.text()).toContain('Enable notifications')
    })

    it('renders with description', () => {
      const wrapper = mount(ToggleSwitch, {
        props: {
          modelValue: false,
          label: 'Test toggle',
          description: 'This is a description',
        },
      })

      const button = wrapper.find('button')
      const descriptionId = button.attributes('aria-describedby')
      expect(descriptionId).toBeTruthy()
      expect(wrapper.find(`#${descriptionId}`).text()).toBe('This is a description')
    })

    it('renders disabled state', () => {
      const wrapper = mount(ToggleSwitch, {
        props: {
          modelValue: false,
          label: 'Test toggle',
          disabled: true,
        },
      })

      const button = wrapper.find('button')
      expect(button.attributes('disabled')).toBe('')
      expect(button.classes()).toContain('opacity-50')
      expect(button.classes()).toContain('cursor-not-allowed')
    })
  })

  describe('Interactions', () => {
    it('emits update:modelValue when clicked', async () => {
      const wrapper = mount(ToggleSwitch, {
        props: {
          modelValue: false,
          label: 'Test toggle',
        },
      })

      await wrapper.find('button').trigger('click')

      expect(wrapper.emitted('update:modelValue')).toBeTruthy()
      expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([true])
    })

    it('toggles from on to off when clicked', async () => {
      const wrapper = mount(ToggleSwitch, {
        props: {
          modelValue: true,
          label: 'Test toggle',
        },
      })

      await wrapper.find('button').trigger('click')

      expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([false])
    })

    it('does not emit when disabled', async () => {
      const wrapper = mount(ToggleSwitch, {
        props: {
          modelValue: false,
          label: 'Test toggle',
          disabled: true,
        },
      })

      await wrapper.find('button').trigger('click')

      expect(wrapper.emitted('update:modelValue')).toBeFalsy()
    })
  })

  describe('Keyboard Accessibility', () => {
    it('toggles when Space key is pressed', async () => {
      const wrapper = mount(ToggleSwitch, {
        props: {
          modelValue: false,
          label: 'Test toggle',
        },
      })

      const button = wrapper.find('button')
      await button.trigger('keydown', { key: ' ' })

      expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([true])
    })

    it('toggles when Enter key is pressed', async () => {
      const wrapper = mount(ToggleSwitch, {
        props: {
          modelValue: false,
          label: 'Test toggle',
        },
      })

      const button = wrapper.find('button')
      await button.trigger('keydown', { key: 'Enter' })

      expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([true])
    })

    it('does not toggle with other keys', async () => {
      const wrapper = mount(ToggleSwitch, {
        props: {
          modelValue: false,
          label: 'Test toggle',
        },
      })

      const button = wrapper.find('button')
      await button.trigger('keydown', { key: 'a' })

      expect(wrapper.emitted('update:modelValue')).toBeFalsy()
    })

    it('does not toggle with Space when disabled', async () => {
      const wrapper = mount(ToggleSwitch, {
        props: {
          modelValue: false,
          label: 'Test toggle',
          disabled: true,
        },
      })

      const button = wrapper.find('button')
      await button.trigger('keydown', { key: ' ' })

      expect(wrapper.emitted('update:modelValue')).toBeFalsy()
    })

    it('prevents default on Space key', async () => {
      const wrapper = mount(ToggleSwitch, {
        props: {
          modelValue: false,
          label: 'Test toggle',
        },
      })

      const button = wrapper.find('button')
      const preventDefault = vi.fn()
      await button.trigger('keydown', { key: ' ', preventDefault })

      expect(preventDefault).toHaveBeenCalled()
    })
  })

  describe('ARIA attributes', () => {
    it('has correct role', () => {
      const wrapper = mount(ToggleSwitch, {
        props: {
          modelValue: false,
          label: 'Test toggle',
        },
      })

      expect(wrapper.find('button').attributes('role')).toBe('switch')
    })

    it('updates aria-checked when toggled', async () => {
      const wrapper = mount(ToggleSwitch, {
        props: {
          modelValue: false,
          label: 'Test toggle',
        },
      })

      let button = wrapper.find('button')
      expect(button.attributes('aria-checked')).toBe('false')

      // Update prop to simulate parent component updating the value
      await wrapper.setProps({ modelValue: true })

      button = wrapper.find('button')
      expect(button.attributes('aria-checked')).toBe('true')
    })

    it('has aria-label from label prop', () => {
      const wrapper = mount(ToggleSwitch, {
        props: {
          modelValue: false,
          label: 'Enable email notifications',
        },
      })

      expect(wrapper.find('button').attributes('aria-label')).toBe(
        'Enable email notifications'
      )
    })

    it('has aria-describedby when description is provided', () => {
      const wrapper = mount(ToggleSwitch, {
        props: {
          modelValue: false,
          label: 'Test toggle',
          description: 'Test description',
        },
      })

      const button = wrapper.find('button')
      const descriptionId = button.attributes('aria-describedby')
      expect(descriptionId).toBeTruthy()
      expect(wrapper.find(`#${descriptionId}`).exists()).toBe(true)
    })
  })

  describe('Visual states', () => {
    it('shows correct background color when off', () => {
      const wrapper = mount(ToggleSwitch, {
        props: {
          modelValue: false,
          label: 'Test toggle',
        },
      })

      const button = wrapper.find('button')
      expect(button.classes()).toContain('bg-slate-300')
      expect(button.classes()).not.toContain('bg-emerald-600')
    })

    it('shows correct background color when on', () => {
      const wrapper = mount(ToggleSwitch, {
        props: {
          modelValue: true,
          label: 'Test toggle',
        },
      })

      const button = wrapper.find('button')
      expect(button.classes()).toContain('bg-emerald-600')
      expect(button.classes()).not.toContain('bg-slate-300')
    })

    it('shows thumb in correct position when off', () => {
      const wrapper = mount(ToggleSwitch, {
        props: {
          modelValue: false,
          label: 'Test toggle',
        },
      })

      const thumb = wrapper.find('span[aria-hidden="true"]')
      expect(thumb.classes()).toContain('translate-x-0')
      expect(thumb.classes()).not.toContain('translate-x-5')
    })

    it('shows thumb in correct position when on', () => {
      const wrapper = mount(ToggleSwitch, {
        props: {
          modelValue: true,
          label: 'Test toggle',
        },
      })

      const thumb = wrapper.find('span[aria-hidden="true"]')
      expect(thumb.classes()).toContain('translate-x-5')
      expect(thumb.classes()).not.toContain('translate-x-0')
    })
  })

  describe('Custom ID', () => {
    it('uses provided ID', () => {
      const wrapper = mount(ToggleSwitch, {
        props: {
          modelValue: false,
          label: 'Test toggle',
          id: 'custom-toggle-id',
        },
      })

      expect(wrapper.find('button').attributes('id')).toBe('custom-toggle-id')
    })

    it('generates unique ID when not provided', () => {
      const wrapper1 = mount(ToggleSwitch, {
        props: {
          modelValue: false,
          label: 'Test toggle 1',
        },
      })

      const wrapper2 = mount(ToggleSwitch, {
        props: {
          modelValue: false,
          label: 'Test toggle 2',
        },
      })

      const id1 = wrapper1.find('button').attributes('id')
      const id2 = wrapper2.find('button').attributes('id')

      expect(id1).toBeTruthy()
      expect(id2).toBeTruthy()
      expect(id1).not.toBe(id2)
    })
  })
})
