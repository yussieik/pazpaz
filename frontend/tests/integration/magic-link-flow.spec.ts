import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'
import AuthVerifyView from '@/views/AuthVerifyView.vue'
import apiClient from '@/api/client'

/**
 * Magic Link Authentication Flow Tests
 *
 * Test Coverage:
 * 1. Happy path: User clicks magic link → authenticated → redirected to calendar
 * 2. Expired link: Shows error with manual recovery buttons
 * 3. Already authenticated: Shows friendly message → redirects
 * 4. Keyboard shortcuts (Enter/Escape)
 * 5. Token removal from URL (security)
 */

describe('Magic Link Authentication Flow', () => {
  let router: any
  let pinia: any

  beforeEach(() => {
    // Use fake timers
    vi.useFakeTimers()

    // Create fresh Pinia instance
    pinia = createPinia()
    setActivePinia(pinia)

    // Create router
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/',
          name: 'calendar',
          component: { template: '<div>Calendar</div>' },
          meta: { requiresAuth: true },
        },
        {
          path: '/login',
          name: 'login',
          component: { template: '<div>Login</div>' },
          meta: { requiresAuth: false },
        },
        {
          path: '/auth/verify',
          name: 'auth-verify',
          component: AuthVerifyView,
          meta: { requiresAuth: false },
        },
        {
          path: '/clients',
          name: 'clients',
          component: { template: '<div>Clients</div>' },
          meta: { requiresAuth: true },
        },
      ],
    })

    // Start at /auth/verify route
    router.push('/auth/verify')

    // Mock window.history.replaceState
    vi.spyOn(window.history, 'replaceState').mockImplementation(() => {})

    // Mock console methods
    vi.spyOn(console, 'debug').mockImplementation(() => {})
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  describe('Happy Path - Valid Magic Link', () => {
    it('should verify token and show success state', async () => {
      // Mock successful API response
      const mockUser = {
        id: 'user-123',
        email: 'therapist@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
        is_platform_admin: false,
      }

      const apiPostSpy = vi.spyOn(apiClient, 'post').mockResolvedValueOnce({
        data: { user: mockUser },
      })

      // Mount component
      const wrapper = mount(AuthVerifyView, {
        global: {
          plugins: [pinia, router],
          mocks: {
            $route: {
              query: { token: 'valid-token-123' },
              path: '/auth/verify',
            },
          },
        },
      })

      // Wait for component to process
      await flushPromises()

      // Verify API was called with token
      expect(apiPostSpy).toHaveBeenCalledWith('/auth/verify', {
        token: 'valid-token-123',
      })

      // Verify user is set in auth store
      const authStore = useAuthStore()
      expect(authStore.user).toEqual(mockUser)
      expect(authStore.isAuthenticated).toBe(true)

      // Check UI shows success state
      expect(wrapper.text()).toContain('Welcome back!')
      expect(wrapper.text()).toContain('Taking you to your calendar')
    })

    it('should remove token from URL for security', async () => {
      const mockUser = {
        id: 'user-123',
        email: 'therapist@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
        is_platform_admin: false,
      }

      vi.spyOn(apiClient, 'post').mockResolvedValueOnce({
        data: { user: mockUser },
      })

      const wrapper = mount(AuthVerifyView, {
        global: {
          plugins: [pinia, router],
          mocks: {
            $route: {
              query: { token: 'sensitive-token-123' },
              path: '/auth/verify',
            },
          },
        },
      })

      await flushPromises()

      // Verify token was removed from URL (replaceState called)
      expect(window.history.replaceState).toHaveBeenCalled()
    })
  })

  describe('Expired Link - Error Handling', () => {
    it('should show error message with manual recovery buttons', async () => {
      // Mock expired token error
      vi.spyOn(apiClient, 'post').mockRejectedValueOnce({
        response: {
          data: {
            detail: 'Token has expired',
          },
        },
      })

      const wrapper = mount(AuthVerifyView, {
        global: {
          plugins: [pinia, router],
          mocks: {
            $route: {
              query: { token: 'expired-token' },
              path: '/auth/verify',
            },
          },
        },
      })

      await flushPromises()

      // Check error state UI
      expect(wrapper.text()).toContain('Link expired or invalid')
      expect(wrapper.text()).toContain('Token has expired')
      expect(wrapper.text()).toContain('Magic links expire after 15 minutes')

      // Check manual action buttons exist
      const buttons = wrapper.findAll('button')
      expect(buttons.length).toBeGreaterThanOrEqual(2)

      const requestNewLinkButton = buttons.find((btn) =>
        btn.text().includes('Request new magic link')
      )
      const returnHomeButton = buttons.find((btn) =>
        btn.text().includes('Return to home')
      )

      expect(requestNewLinkButton).toBeTruthy()
      expect(returnHomeButton).toBeTruthy()

      // Verify NO auto-redirect happened (wait 5 seconds)
      await vi.advanceTimersByTime(5000)
      await flushPromises()

      // Error state should still be visible
      expect(wrapper.text()).toContain('Link expired or invalid')
    })

    it('should navigate to login when Request new magic link clicked', async () => {
      vi.spyOn(apiClient, 'post').mockRejectedValueOnce({
        response: {
          data: { detail: 'Token has expired' },
        },
      })

      const wrapper = mount(AuthVerifyView, {
        global: {
          plugins: [pinia, router],
          mocks: {
            $route: {
              query: { token: 'expired-token' },
              path: '/auth/verify',
            },
          },
        },
      })

      await flushPromises()

      // Click Request new magic link button
      const requestNewLinkButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Request new magic link'))

      await requestNewLinkButton!.trigger('click')
      await flushPromises()

      // Should navigate to login
      expect(router.currentRoute.value.path).toBe('/login')
    })

    it('should navigate to home when Return to home clicked', async () => {
      vi.spyOn(apiClient, 'post').mockRejectedValueOnce({
        response: {
          data: { detail: 'Token has expired' },
        },
      })

      const wrapper = mount(AuthVerifyView, {
        global: {
          plugins: [pinia, router],
          mocks: {
            $route: {
              query: { token: 'expired-token' },
              path: '/auth/verify',
            },
          },
        },
      })

      await flushPromises()

      // Click Return to home button
      const returnHomeButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Return to home'))

      await returnHomeButton!.trigger('click')
      await flushPromises()

      // Should navigate to home
      expect(router.currentRoute.value.path).toBe('/')
    })

    it('should handle Enter key to request new link', async () => {
      vi.spyOn(apiClient, 'post').mockRejectedValueOnce({
        response: {
          data: { detail: 'Token has expired' },
        },
      })

      const wrapper = mount(AuthVerifyView, {
        global: {
          plugins: [pinia, router],
          mocks: {
            $route: {
              query: { token: 'expired-token' },
              path: '/auth/verify',
            },
          },
        },
      })

      await flushPromises()

      // Simulate Enter key press
      const enterEvent = new KeyboardEvent('keydown', {
        key: 'Enter',
        bubbles: true,
        cancelable: true,
      })
      window.dispatchEvent(enterEvent)
      await flushPromises()

      // Should navigate to login
      expect(router.currentRoute.value.path).toBe('/login')
    })

    it('should handle Escape key to return home', async () => {
      vi.spyOn(apiClient, 'post').mockRejectedValueOnce({
        response: {
          data: { detail: 'Token has expired' },
        },
      })

      const wrapper = mount(AuthVerifyView, {
        global: {
          plugins: [pinia, router],
          mocks: {
            $route: {
              query: { token: 'expired-token' },
              path: '/auth/verify',
            },
          },
        },
      })

      await flushPromises()

      // Simulate Escape key press
      const escapeEvent = new KeyboardEvent('keydown', {
        key: 'Escape',
        bubbles: true,
        cancelable: true,
      })
      window.dispatchEvent(escapeEvent)
      await flushPromises()

      // Should navigate to home
      expect(router.currentRoute.value.path).toBe('/')
    })
  })

  describe('Already Authenticated', () => {
    it('should show already signed in message and redirect', async () => {
      // Set up authenticated user BEFORE mounting component
      const authStore = useAuthStore()
      authStore.setUser({
        id: 'user-123',
        email: 'therapist@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
        is_platform_admin: false,
      })

      const wrapper = mount(AuthVerifyView, {
        global: {
          plugins: [pinia, router],
          mocks: {
            $route: {
              query: { token: 'some-token' },
              path: '/auth/verify',
            },
          },
        },
      })

      await flushPromises()

      // Should show already signed in message
      expect(wrapper.text()).toContain("You're already signed in")
      expect(wrapper.text()).toContain('Taking you back to your calendar')

      // Wait for redirect (1 second)
      await vi.advanceTimersByTime(1000)
      await flushPromises()

      // Should redirect to home
      expect(router.currentRoute.value.path).toBe('/')
    })
  })

  describe('Loading State', () => {
    it('should show loading state while verifying', async () => {
      // Create a promise we control
      let resolveApi: any
      const apiPromise = new Promise((resolve) => {
        resolveApi = resolve
      })

      vi.spyOn(apiClient, 'post').mockReturnValueOnce(apiPromise as any)

      const wrapper = mount(AuthVerifyView, {
        global: {
          plugins: [pinia, router],
          mocks: {
            $route: {
              query: { token: 'token-123' },
              path: '/auth/verify',
            },
          },
        },
      })

      await flushPromises()

      // Should show loading state
      expect(wrapper.text()).toContain('Signing you in')
      expect(wrapper.text()).toContain('Verifying your magic link')

      // Resolve the API call
      resolveApi({
        data: {
          user: {
            id: 'user-123',
            email: 'therapist@example.com',
            workspace_id: 'ws-123',
            role: 'therapist',
            is_platform_admin: false,
          },
        },
      })

      await flushPromises()

      // Should show success state
      expect(wrapper.text()).toContain('Welcome back!')
    })
  })

  describe('Edge Cases', () => {
    it('should handle missing token gracefully', async () => {
      const wrapper = mount(AuthVerifyView, {
        global: {
          plugins: [pinia, router],
          mocks: {
            $route: {
              query: {},
              path: '/auth/verify',
            },
          },
        },
      })

      await flushPromises()

      // Should show error
      expect(wrapper.text()).toContain('Link expired or invalid')
      expect(wrapper.text()).toContain('No verification token provided')
    })

    it('should handle network errors gracefully', async () => {
      vi.spyOn(apiClient, 'post').mockRejectedValueOnce({
        message: 'Network Error',
      })

      const wrapper = mount(AuthVerifyView, {
        global: {
          plugins: [pinia, router],
          mocks: {
            $route: {
              query: { token: 'token-123' },
              path: '/auth/verify',
            },
          },
        },
      })

      await flushPromises()

      // Should show generic error
      expect(wrapper.text()).toContain('Link expired or invalid')
      expect(wrapper.text()).toContain('Invalid or expired magic link')
    })
  })

  describe('Accessibility', () => {
    it('should have proper ARIA attributes on icons', async () => {
      const mockUser = {
        id: 'user-123',
        email: 'therapist@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
        is_platform_admin: false,
      }

      vi.spyOn(apiClient, 'post').mockResolvedValueOnce({
        data: { user: mockUser },
      })

      const wrapper = mount(AuthVerifyView, {
        global: {
          plugins: [pinia, router],
          mocks: {
            $route: {
              query: { token: 'valid-token' },
              path: '/auth/verify',
            },
          },
        },
      })

      await flushPromises()

      // Check that SVG icons have aria-hidden
      const svgs = wrapper.findAll('svg')
      svgs.forEach((svg) => {
        expect(svg.attributes('aria-hidden')).toBe('true')
      })
    })

    it('should set autofocus on primary button in error state', async () => {
      vi.spyOn(apiClient, 'post').mockRejectedValueOnce({
        response: {
          data: { detail: 'Token has expired' },
        },
      })

      const wrapper = mount(AuthVerifyView, {
        global: {
          plugins: [pinia, router],
          mocks: {
            $route: {
              query: { token: 'expired-token' },
              path: '/auth/verify',
            },
          },
        },
      })

      await flushPromises()

      // Check primary button has autofocus
      const primaryButton = wrapper
        .findAll('button')
        .find((btn) => btn.text().includes('Request new magic link'))

      expect(primaryButton!.attributes('autofocus')).toBeDefined()
    })
  })

  describe('Visual States', () => {
    it('should show emerald gradient background matching LoginView', async () => {
      const wrapper = mount(AuthVerifyView, {
        global: {
          plugins: [pinia, router],
          mocks: {
            $route: {
              query: { token: 'token-123' },
              path: '/auth/verify',
            },
          },
        },
      })

      const rootDiv = wrapper.find('div')
      expect(rootDiv.classes()).toContain('bg-gradient-to-br')
      expect(rootDiv.classes()).toContain('from-emerald-50')
      expect(rootDiv.classes()).toContain('to-slate-50')
    })

    it('should display loading animation with bouncing dots', async () => {
      // Delay API response to test loading state
      let resolveApi: any
      const apiPromise = new Promise((resolve) => {
        resolveApi = resolve
      })
      vi.spyOn(apiClient, 'post').mockReturnValueOnce(apiPromise as any)

      const wrapper = mount(AuthVerifyView, {
        global: {
          plugins: [pinia, router],
          mocks: {
            $route: {
              query: { token: 'token-123' },
              path: '/auth/verify',
            },
          },
        },
      })

      await flushPromises()

      // Check for spinning border
      const spinningElement = wrapper.find('.animate-spin')
      expect(spinningElement.exists()).toBe(true)

      // Check for bouncing dots
      const dots = wrapper.findAll('.animate-bounce')
      expect(dots.length).toBeGreaterThanOrEqual(3)
    })
  })
})
