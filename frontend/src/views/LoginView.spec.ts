import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import LoginView from './LoginView.vue'
import apiClient from '@/api/client'

// Mock apiClient
vi.mock('@/api/client', () => ({
  default: {
    post: vi.fn(),
  },
}))

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/login', component: LoginView },
    { path: '/', component: { template: '<div>Home</div>' } },
  ],
})

describe('LoginView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('renders login form with all required elements', () => {
      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      // Check branding
      expect(wrapper.text()).toContain('PazPaz')
      expect(wrapper.text()).toContain('Practice Management for Therapists')

      // Check form elements
      expect(wrapper.find('h2').text()).toBe('Sign In')
      expect(wrapper.find('input[type="email"]').exists()).toBe(true)
      expect(wrapper.find('button[type="submit"]').exists()).toBe(true)

      // Check labels and help text
      expect(wrapper.text()).toContain('Email Address')
      expect(wrapper.text()).toContain("We'll send you a magic link to sign in")
      expect(wrapper.text()).toContain('Secure passwordless authentication')
    })

    it('has proper ARIA attributes for accessibility', () => {
      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      const emailInput = wrapper.find('input[type="email"]')
      expect(emailInput.attributes('aria-required')).toBe('true')
      expect(emailInput.attributes('aria-describedby')).toBe('email-description')
      expect(emailInput.attributes('id')).toBe('email')

      const label = wrapper.find('label[for="email"]')
      expect(label.exists()).toBe(true)
    })

    it('displays error message from query parameter', async () => {
      const customRouter = createRouter({
        history: createMemoryHistory(),
        routes: [{ path: '/login', component: LoginView }],
      })

      await customRouter.push('/login?error=invalid_link')
      await customRouter.isReady()

      const wrapper = mount(LoginView, {
        global: { plugins: [customRouter] },
      })

      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Invalid or expired magic link')
    })
  })

  describe('Focus Management (Keyboard-first UX)', () => {
    it('focuses email input on mount', async () => {
      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
        attachTo: document.body,
      })

      await wrapper.vm.$nextTick()

      const emailInput = wrapper.find('input[type="email"]').element as HTMLInputElement
      expect(document.activeElement).toBe(emailInput)

      wrapper.unmount()
    })
  })

  describe('Form Validation', () => {
    it('shows validation error for empty email', async () => {
      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      const form = wrapper.find('form')
      await form.trigger('submit')

      expect(apiClient.post).not.toHaveBeenCalled()
      expect(wrapper.text()).toContain('valid email')
    })

    it('shows validation error for invalid email format', async () => {
      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      const emailInput = wrapper.find('input[type="email"]')
      await emailInput.setValue('invalid-email')

      const form = wrapper.find('form')
      await form.trigger('submit')

      expect(apiClient.post).not.toHaveBeenCalled()
      expect(wrapper.text()).toContain('valid email')
    })

    it('trims and lowercases email before sending', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: {} })

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      const emailInput = wrapper.find('input[type="email"]')
      await emailInput.setValue('  Test@Example.com  ')

      const form = wrapper.find('form')
      await form.trigger('submit')

      expect(apiClient.post).toHaveBeenCalledWith('/auth/magic-link', {
        email: 'test@example.com',
      })
    })
  })

  describe('Magic Link Request', () => {
    it('sends magic link request on valid email submission', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: {} })

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      const emailInput = wrapper.find('input[type="email"]')
      await emailInput.setValue('test@example.com')

      const form = wrapper.find('form')
      await form.trigger('submit')

      expect(apiClient.post).toHaveBeenCalledWith('/auth/magic-link', {
        email: 'test@example.com',
      })
    })

    it('shows success message after sending link', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: {} })

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Check your email')
      expect(wrapper.text()).toContain('test@example.com')
      expect(wrapper.text()).toContain('The link will expire in 10 minutes')
    })

    it('clears previous error when submitting again', async () => {
      // First request fails
      vi.mocked(apiClient.post).mockRejectedValueOnce({
        response: { status: 500 },
      })

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('An error occurred')

      // Second request succeeds
      vi.mocked(apiClient.post).mockResolvedValueOnce({ data: {} })
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).not.toContain('An error occurred')
      expect(wrapper.text()).toContain('Check your email')
    })
  })

  describe('Error Handling', () => {
    it('handles rate limit error (429)', async () => {
      vi.mocked(apiClient.post).mockRejectedValue({
        response: { status: 429 },
      })

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Too many requests')
      expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    })

    it('handles validation error (422)', async () => {
      vi.mocked(apiClient.post).mockRejectedValue({
        response: { status: 422 },
      })

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('invalid@email')
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('valid email')
      expect(wrapper.find('[role="alert"]').exists()).toBe(true)
    })

    it('handles generic server error', async () => {
      vi.mocked(apiClient.post).mockRejectedValue({
        response: { status: 500 },
      })

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('An error occurred')
    })

    it('handles network error (no response)', async () => {
      vi.mocked(apiClient.post).mockRejectedValue({
        request: {},
        message: 'Network Error',
      })

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('An error occurred')
    })
  })

  describe('Loading State', () => {
    it('disables form during API request', async () => {
      // Create a promise that we control
      let resolveRequest: ((value: { data: object }) => void) | undefined
      const requestPromise = new Promise<{ data: object }>((resolve) => {
        resolveRequest = resolve
      })

      vi.mocked(apiClient.post).mockReturnValue(requestPromise as never)

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      const form = wrapper.find('form')
      await form.trigger('submit')
      await wrapper.vm.$nextTick()

      // During loading
      const emailInput = wrapper.find('input[type="email"]')
      const submitButton = wrapper.find('button[type="submit"]')

      expect(emailInput.attributes('disabled')).toBeDefined()
      expect(submitButton.attributes('disabled')).toBeDefined()
      expect(submitButton.text()).toContain('Sending')

      // Resolve the request
      resolveRequest!({ data: {} })
      await wrapper.vm.$nextTick()
      await wrapper.vm.$nextTick() // Need extra tick for reactive updates

      // After loading
      const updatedButton = wrapper.find('button[type="submit"]')
      expect(updatedButton.text()).toContain('Link Sent')
    })

    it('shows loading spinner during request', async () => {
      let resolveRequest: ((value: { data: object }) => void) | undefined
      const requestPromise = new Promise<{ data: object }>((resolve) => {
        resolveRequest = resolve
      })

      vi.mocked(apiClient.post).mockReturnValue(requestPromise as never)

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      // Check for spinner SVG
      const submitButton = wrapper.find('button[type="submit"]')
      expect(submitButton.html()).toContain('animate-spin')

      resolveRequest!({ data: {} })
    })

    it('disables submit button when email is empty', () => {
      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      const submitButton = wrapper.find('button[type="submit"]')
      expect(submitButton.attributes('disabled')).toBeDefined()
    })

    it('enables submit button when email is provided', async () => {
      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      const emailInput = wrapper.find('input[type="email"]')
      await emailInput.setValue('test@example.com')
      await wrapper.vm.$nextTick()

      const submitButton = wrapper.find('button[type="submit"]')
      expect(submitButton.attributes('disabled')).toBeUndefined()
    })

    it('disables form after successful submission', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: {} })

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      const emailInput = wrapper.find('input[type="email"]')
      const submitButton = wrapper.find('button[type="submit"]')

      expect(emailInput.attributes('disabled')).toBeDefined()
      expect(submitButton.attributes('disabled')).toBeDefined()
      expect(submitButton.text()).toBe('Link Sent!')
    })
  })

  describe('Email Enumeration Prevention', () => {
    it('does not reveal whether email exists in system', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: {} })

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('nonexistent@example.com')
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      // Same success message regardless of whether email exists
      expect(wrapper.text()).toContain('Check your email')
      expect(wrapper.text()).not.toContain('not found')
      expect(wrapper.text()).not.toContain('does not exist')
    })
  })

  describe('Responsive Design', () => {
    it('has responsive container classes', () => {
      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      const container = wrapper.find('.max-w-md')
      expect(container.exists()).toBe(true)
      expect(container.classes()).toContain('w-full')
    })

    it('has mobile padding', () => {
      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      const mainContainer = wrapper.find('.min-h-screen')
      expect(mainContainer.classes()).toContain('px-4')
    })
  })
})
