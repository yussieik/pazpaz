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

  describe('Enhanced Waiting Experience - Countdown Timer', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })

    afterEach(() => {
      vi.restoreAllMocks()
      vi.useRealTimers()
    })

    it('shows countdown timer after successful magic link request', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: {} })

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Link expires in:')
      expect(wrapper.text()).toContain('15:00') // 15 minutes
    })

    it('decrements countdown timer every second', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: {} })

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      // Initial time
      expect(wrapper.text()).toContain('15:00')

      // Advance 5 seconds
      vi.advanceTimersByTime(5000)
      await wrapper.vm.$nextTick()
      expect(wrapper.text()).toContain('14:55')

      // Advance 60 seconds
      vi.advanceTimersByTime(60000)
      await wrapper.vm.$nextTick()
      expect(wrapper.text()).toContain('13:55')
    })

    it('adds pulse animation when countdown reaches 60 seconds or less', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: {} })

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      // Fast-forward to 59 seconds remaining
      vi.advanceTimersByTime(14 * 60 * 1000 + 1000) // 14 minutes 1 second
      await wrapper.vm.$nextTick()

      const countdown = wrapper.find('.font-mono')
      expect(countdown.classes()).toContain('animate-pulse')
      expect(countdown.classes()).toContain('text-red-600')
    })

    it('shows helpful tips in success message', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: {} })

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Check your spam folder')
      expect(wrapper.text()).toContain('The link can only be used once')
    })

    it('cleans up countdown interval on unmount', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: {} })

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      const clearIntervalSpy = vi.spyOn(global, 'clearInterval')

      wrapper.unmount()

      expect(clearIntervalSpy).toHaveBeenCalled()
    })
  })

  describe('Enhanced Waiting Experience - Resend Functionality', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })

    afterEach(() => {
      vi.restoreAllMocks()
      vi.useRealTimers()
    })

    it('shows resend cooldown after successful request', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: {} })

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Resend available in')
      expect(wrapper.text()).toContain('60s')
    })

    it('decrements resend cooldown timer every second', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: {} })

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('60s')

      vi.advanceTimersByTime(5000) // 5 seconds
      await wrapper.vm.$nextTick()
      expect(wrapper.text()).toContain('55s')

      vi.advanceTimersByTime(30000) // 30 seconds
      await wrapper.vm.$nextTick()
      expect(wrapper.text()).toContain('25s')
    })

    it('shows resend button when cooldown completes', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: {} })

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      // Cooldown active
      expect(wrapper.text()).toContain('Resend available in')

      // Fast-forward 60 seconds
      vi.advanceTimersByTime(60000)
      await wrapper.vm.$nextTick()

      // Resend button should now be visible
      expect(wrapper.text()).toContain('Resend magic link')
      expect(wrapper.text()).not.toContain('Resend available in')
    })

    it('allows resending magic link after cooldown', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: {} })

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      // Fast-forward past cooldown
      vi.advanceTimersByTime(60000)
      await wrapper.vm.$nextTick()

      // Click resend button
      const resendButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Resend magic link'))
      await resendButton?.trigger('click')
      await wrapper.vm.$nextTick()

      // Should call API again
      expect(apiClient.post).toHaveBeenCalledTimes(2)
      expect(apiClient.post).toHaveBeenLastCalledWith('/auth/magic-link', {
        email: 'test@example.com',
      })

      // Cooldown should restart
      expect(wrapper.text()).toContain('Resend available in')
    })

    it('shows loading state during resend', async () => {
      let resolveRequest: ((value: { data: object }) => void) | undefined
      const requestPromise = new Promise<{ data: object }>((resolve) => {
        resolveRequest = resolve
      })

      vi.mocked(apiClient.post)
        .mockResolvedValueOnce({ data: {} }) // First request succeeds immediately
        .mockReturnValueOnce(requestPromise as never) // Second request is pending

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      // Fast-forward past cooldown
      vi.advanceTimersByTime(60000)
      await wrapper.vm.$nextTick()

      // Click resend
      const resendButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Resend magic link'))
      await resendButton?.trigger('click')
      await wrapper.vm.$nextTick()

      // Should show "Resending..." during request
      expect(wrapper.text()).toContain('Resending...')

      resolveRequest!({ data: {} })
      await wrapper.vm.$nextTick()
    })

    it('handles 429 rate limit with retry-after in resend', async () => {
      vi.mocked(apiClient.post)
        .mockResolvedValueOnce({ data: {} }) // First request succeeds
        .mockRejectedValueOnce({
          response: {
            status: 429,
            data: { detail: 'Rate limited. Please try again in 120 seconds.' },
          },
        })

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      // Fast-forward past initial cooldown
      vi.advanceTimersByTime(60000)
      await wrapper.vm.$nextTick()

      // Try to resend
      const resendButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Resend magic link'))
      await resendButton?.trigger('click')
      await wrapper.vm.$nextTick()

      // Should show rate limit error
      expect(wrapper.text()).toContain('Too many requests')
      expect(wrapper.text()).toContain('120 seconds')
    })

    it('cleans up cooldown interval on unmount', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: {} })

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      const clearIntervalSpy = vi.spyOn(global, 'clearInterval')

      wrapper.unmount()

      expect(clearIntervalSpy).toHaveBeenCalled()
    })
  })

  describe('Enhanced Waiting Experience - Animations', () => {
    it('shows animated checkmark on success', async () => {
      vi.mocked(apiClient.post).mockResolvedValue({ data: {} })

      const wrapper = mount(LoginView, {
        global: { plugins: [router] },
      })

      await wrapper.find('input[type="email"]').setValue('test@example.com')
      await wrapper.find('form').trigger('submit')
      await wrapper.vm.$nextTick()

      // Checkmark SVG should be present
      const successAlert = wrapper.find('[role="alert"]')
      const checkmark = successAlert.find('svg')
      expect(checkmark.exists()).toBe(true)
    })
  })
})
