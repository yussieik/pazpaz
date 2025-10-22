import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import AcceptInvitationView from './AcceptInvitationView.vue'
import { useAuthStore } from '@/stores/auth'
import apiClient from '@/api/client'

/**
 * AcceptInvitationView Component Tests
 *
 * Tests the therapist invitation acceptance flow:
 * - Missing token handling
 * - Valid token success flow
 * - Invalid token (404) handling
 * - Expired token (410) handling
 * - API error handling
 * - Auth store integration
 * - Automatic redirects
 *
 * This is a public route (no auth required) that:
 * 1. Accepts invitation token via query param
 * 2. Calls /auth/accept-invite endpoint
 * 3. Updates auth store with user data
 * 4. Redirects to home (success) or login (error)
 */

// Mock apiClient
vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn(),
  },
}))

describe('AcceptInvitationView', () => {
  let router: any
  let pinia: any

  beforeEach(() => {
    // Create fresh Pinia instance
    pinia = createPinia()
    setActivePinia(pinia)

    // Create test router
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        {
          path: '/accept-invitation',
          name: 'accept-invitation',
          component: AcceptInvitationView,
          meta: { requiresAuth: false },
        },
        {
          path: '/',
          name: 'home',
          component: { template: '<div>Home</div>' },
        },
        {
          path: '/login',
          name: 'login',
          component: { template: '<div>Login</div>' },
        },
      ],
    })

    // Mock console methods to avoid noise
    vi.spyOn(console, 'info').mockImplementation(() => {})
    vi.spyOn(console, 'error').mockImplementation(() => {})

    // Clear all mocks
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('Missing Token Handling', () => {
    it('shows error message when token is missing from URL', async () => {
      await router.push('/accept-invitation')
      await router.isReady()

      const wrapper = mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Invitation Failed')
      expect(wrapper.text()).toContain('Invitation link is missing token')
      expect(wrapper.find('[role="alert"]').exists()).toBe(false) // No API call made
    })

    it('sets status to error when token is missing', async () => {
      await router.push('/accept-invitation')
      await router.isReady()

      const wrapper = mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await wrapper.vm.$nextTick()

      // Verify error state is rendered
      const errorIcon = wrapper.find('.bg-red-100')
      expect(errorIcon.exists()).toBe(true)
    })

    it('does not call API when token is missing', async () => {
      await router.push('/accept-invitation')
      await router.isReady()

      mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await flushPromises()

      expect(apiClient.get).not.toHaveBeenCalled()
    })

    it('provides link to go to login page', async () => {
      await router.push('/accept-invitation')
      await router.isReady()

      const wrapper = mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await wrapper.vm.$nextTick()

      const loginLink = wrapper.find('a[href="/login"]')
      expect(loginLink.exists()).toBe(true)
      expect(loginLink.text()).toContain('Go to Login')
    })
  })

  describe('Valid Token - Success Flow', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    it('calls API with token as query parameter', async () => {
      const mockToken = 'valid-invitation-token-abc123'
      vi.mocked(apiClient.get).mockResolvedValue({
        data: {
          success: true,
          user: {
            id: 'user-123',
            email: 'therapist@example.com',
            workspace_id: 'ws-456',
            role: 'therapist',
            is_platform_admin: false,
          },
        },
      })

      await router.push(`/accept-invitation?token=${mockToken}`)
      await router.isReady()

      mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      // Wait for onMounted async operations
      await flushPromises()

      expect(apiClient.get).toHaveBeenCalledWith('/auth/accept-invite', {
        params: { token: mockToken },
      })
    })

    it('shows success message after accepting invitation', async () => {
      vi.mocked(apiClient.get).mockResolvedValue({
        data: {
          success: true,
          user: {
            id: 'user-123',
            email: 'therapist@example.com',
            workspace_id: 'ws-456',
            role: 'therapist',
            is_platform_admin: false,
          },
        },
      })

      await router.push('/accept-invitation?token=valid-token')
      await router.isReady()

      const wrapper = mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await flushPromises()

      expect(wrapper.text()).toContain('Welcome to PazPaz!')
      expect(wrapper.text()).toContain('Your account has been activated')
      expect(wrapper.text()).toContain('Redirecting you to the calendar')
    })

    it('updates auth store with user data from response', async () => {
      const mockUser = {
        id: 'user-123',
        email: 'therapist@example.com',
        workspace_id: 'ws-456',
        role: 'therapist',
        is_platform_admin: false,
      }

      vi.mocked(apiClient.get).mockResolvedValue({
        data: {
          success: true,
          user: mockUser,
        },
      })

      await router.push('/accept-invitation?token=valid-token')
      await router.isReady()

      mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await flushPromises()

      const authStore = useAuthStore()
      expect(authStore.user).toEqual(mockUser)
      expect(authStore.isAuthenticated).toBe(true)
    })

    it('redirects to home page after 2 seconds', async () => {
      vi.mocked(apiClient.get).mockResolvedValue({
        data: {
          success: true,
          user: {
            id: 'user-123',
            email: 'therapist@example.com',
            workspace_id: 'ws-456',
            role: 'therapist',
            is_platform_admin: false,
          },
        },
      })

      await router.push('/accept-invitation?token=valid-token')
      await router.isReady()

      const routerPushSpy = vi.spyOn(router, 'push')

      mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await flushPromises()

      // Should not redirect immediately
      expect(routerPushSpy).not.toHaveBeenCalled()

      // Fast-forward 2 seconds
      vi.advanceTimersByTime(2000)
      await flushPromises()

      // Should redirect to home
      expect(routerPushSpy).toHaveBeenCalledWith('/')
    })

    it('shows success icon (checkmark)', async () => {
      vi.mocked(apiClient.get).mockResolvedValue({
        data: {
          success: true,
          user: {
            id: 'user-123',
            email: 'therapist@example.com',
            workspace_id: 'ws-456',
            role: 'therapist',
            is_platform_admin: false,
          },
        },
      })

      await router.push('/accept-invitation?token=valid-token')
      await router.isReady()

      const wrapper = mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await flushPromises()

      const successIcon = wrapper.find('.bg-green-100')
      expect(successIcon.exists()).toBe(true)

      // Check for checkmark SVG path
      const checkmarkPath = wrapper.find('path[d="M5 13l4 4L19 7"]')
      expect(checkmarkPath.exists()).toBe(true)
    })
  })

  describe('Invalid Token (404)', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    it('shows error message for 404 response', async () => {
      vi.mocked(apiClient.get).mockRejectedValue({
        response: {
          status: 404,
          data: { detail: 'Invitation not found' },
        },
      })

      await router.push('/accept-invitation?token=invalid-token')
      await router.isReady()

      const wrapper = mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await flushPromises()
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Invitation Failed')
      expect(wrapper.text()).toContain('Invalid invitation link')
    })

    it('redirects to login after 3 seconds on 404', async () => {
      vi.mocked(apiClient.get).mockRejectedValue({
        response: {
          status: 404,
          data: {},
        },
      })

      await router.push('/accept-invitation?token=invalid-token')
      await router.isReady()

      const routerPushSpy = vi.spyOn(router, 'push')

      mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await flushPromises()

      // Should not redirect immediately
      expect(routerPushSpy).not.toHaveBeenCalled()

      // Fast-forward 3 seconds
      vi.advanceTimersByTime(3000)
      await flushPromises()

      // Should redirect to login with error query
      expect(routerPushSpy).toHaveBeenCalledWith({
        path: '/login',
        query: { error: 'invitation_failed' },
      })
    })

    it('shows error icon (X)', async () => {
      vi.mocked(apiClient.get).mockRejectedValue({
        response: {
          status: 404,
          data: {},
        },
      })

      await router.push('/accept-invitation?token=invalid-token')
      await router.isReady()

      const wrapper = mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await flushPromises()
      await wrapper.vm.$nextTick()

      const errorIcon = wrapper.find('.bg-red-100')
      expect(errorIcon.exists()).toBe(true)

      // Check for X icon SVG path
      const xIconPath = wrapper.find('path[d="M6 18L18 6M6 6l12 12"]')
      expect(xIconPath.exists()).toBe(true)
    })

    it('does not update auth store on 404', async () => {
      vi.mocked(apiClient.get).mockRejectedValue({
        response: {
          status: 404,
          data: {},
        },
      })

      await router.push('/accept-invitation?token=invalid-token')
      await router.isReady()

      mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await flushPromises()

      const authStore = useAuthStore()
      expect(authStore.user).toBeNull()
      expect(authStore.isAuthenticated).toBe(false)
    })
  })

  describe('Expired Token (410)', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    it('shows error message for 410 response', async () => {
      vi.mocked(apiClient.get).mockRejectedValue({
        response: {
          status: 410,
          data: { detail: 'Invitation has expired' },
        },
      })

      await router.push('/accept-invitation?token=expired-token')
      await router.isReady()

      const wrapper = mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await flushPromises()
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Invitation Failed')
      expect(wrapper.text()).toContain(
        'This invitation has expired or has already been used'
      )
    })

    it('redirects to login after 3 seconds on 410', async () => {
      vi.mocked(apiClient.get).mockRejectedValue({
        response: {
          status: 410,
          data: {},
        },
      })

      await router.push('/accept-invitation?token=expired-token')
      await router.isReady()

      const routerPushSpy = vi.spyOn(router, 'push')

      mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await flushPromises()

      // Fast-forward 3 seconds
      vi.advanceTimersByTime(3000)
      await flushPromises()

      expect(routerPushSpy).toHaveBeenCalledWith({
        path: '/login',
        query: { error: 'invitation_failed' },
      })
    })

    it('does not update auth store on 410', async () => {
      vi.mocked(apiClient.get).mockRejectedValue({
        response: {
          status: 410,
          data: {},
        },
      })

      await router.push('/accept-invitation?token=expired-token')
      await router.isReady()

      mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await flushPromises()

      const authStore = useAuthStore()
      expect(authStore.user).toBeNull()
      expect(authStore.isAuthenticated).toBe(false)
    })
  })

  describe('Generic Error Handling', () => {
    beforeEach(() => {
      vi.useFakeTimers()
    })

    afterEach(() => {
      vi.useRealTimers()
    })

    it('shows backend error detail when available', async () => {
      vi.mocked(apiClient.get).mockRejectedValue({
        response: {
          status: 500,
          data: { detail: 'Database connection failed' },
        },
      })

      await router.push('/accept-invitation?token=some-token')
      await router.isReady()

      const wrapper = mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await flushPromises()
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Database connection failed')
    })

    it('shows generic error message when no detail provided', async () => {
      vi.mocked(apiClient.get).mockRejectedValue({
        response: {
          status: 500,
          data: {},
        },
      })

      await router.push('/accept-invitation?token=some-token')
      await router.isReady()

      const wrapper = mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await flushPromises()
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Failed to accept invitation')
      expect(wrapper.text()).toContain('Please contact support')
    })

    it('redirects to login after 3 seconds on generic error', async () => {
      vi.mocked(apiClient.get).mockRejectedValue({
        response: {
          status: 500,
          data: {},
        },
      })

      await router.push('/accept-invitation?token=some-token')
      await router.isReady()

      const routerPushSpy = vi.spyOn(router, 'push')

      mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await flushPromises()

      vi.advanceTimersByTime(3000)
      await flushPromises()

      expect(routerPushSpy).toHaveBeenCalledWith({
        path: '/login',
        query: { error: 'invitation_failed' },
      })
    })

    it('handles network errors gracefully', async () => {
      vi.mocked(apiClient.get).mockRejectedValue({
        message: 'Network Error',
        request: {},
      })

      await router.push('/accept-invitation?token=some-token')
      await router.isReady()

      const wrapper = mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await flushPromises()
      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Failed to accept invitation')
      expect(wrapper.text()).toContain('Please contact support')
    })
  })

  describe('Loading State', () => {
    it('shows loading spinner initially', async () => {
      // Create a promise that never resolves to keep loading state
      vi.mocked(apiClient.get).mockReturnValue(new Promise(() => {}) as any)

      await router.push('/accept-invitation?token=valid-token')
      await router.isReady()

      const wrapper = mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await wrapper.vm.$nextTick()

      expect(wrapper.text()).toContain('Accepting your invitation')
      expect(wrapper.find('.animate-spin').exists()).toBe(true)
    })

    it('transitions from loading to success', async () => {
      let resolveRequest: ((value: any) => void) | undefined
      const requestPromise = new Promise((resolve) => {
        resolveRequest = resolve
      })

      vi.mocked(apiClient.get).mockReturnValue(requestPromise as any)

      await router.push('/accept-invitation?token=valid-token')
      await router.isReady()

      const wrapper = mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await wrapper.vm.$nextTick()

      // Initially loading
      expect(wrapper.text()).toContain('Accepting your invitation')

      // Resolve the request
      resolveRequest!({
        data: {
          success: true,
          user: {
            id: 'user-123',
            email: 'therapist@example.com',
            workspace_id: 'ws-456',
            role: 'therapist',
            is_platform_admin: false,
          },
        },
      })

      await flushPromises()
      await wrapper.vm.$nextTick()

      // Should show success
      expect(wrapper.text()).toContain('Welcome to PazPaz!')
    })

    it('transitions from loading to error', async () => {
      let rejectRequest: ((error: any) => void) | undefined
      const requestPromise = new Promise((_, reject) => {
        rejectRequest = reject
      })

      vi.mocked(apiClient.get).mockReturnValue(requestPromise as any)

      await router.push('/accept-invitation?token=invalid-token')
      await router.isReady()

      const wrapper = mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await wrapper.vm.$nextTick()

      // Initially loading
      expect(wrapper.text()).toContain('Accepting your invitation')

      // Reject the request
      rejectRequest!({
        response: {
          status: 404,
          data: {},
        },
      })

      await flushPromises()
      await wrapper.vm.$nextTick()

      // Should show error
      expect(wrapper.text()).toContain('Invitation Failed')
      expect(wrapper.text()).toContain('Invalid invitation link')
    })
  })

  describe('Edge Cases', () => {
    it('handles response without success flag', async () => {
      vi.mocked(apiClient.get).mockResolvedValue({
        data: {
          user: {
            id: 'user-123',
            email: 'therapist@example.com',
            workspace_id: 'ws-456',
            role: 'therapist',
            is_platform_admin: false,
          },
        },
      })

      await router.push('/accept-invitation?token=valid-token')
      await router.isReady()

      const wrapper = mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await flushPromises()
      await wrapper.vm.$nextTick()

      // Should treat as error if success flag is missing
      expect(wrapper.text()).toContain('Invitation Failed')
    })

    it('handles response without user data', async () => {
      vi.mocked(apiClient.get).mockResolvedValue({
        data: {
          success: true,
        },
      })

      await router.push('/accept-invitation?token=valid-token')
      await router.isReady()

      const wrapper = mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await flushPromises()
      await wrapper.vm.$nextTick()

      // Should still show success but not update auth store
      expect(wrapper.text()).toContain('Welcome to PazPaz!')

      const authStore = useAuthStore()
      expect(authStore.user).toBeNull()
    })

    it('logs user ID to console when user is authenticated', async () => {
      const consoleInfoSpy = vi.spyOn(console, 'info')

      vi.mocked(apiClient.get).mockResolvedValue({
        data: {
          success: true,
          user: {
            id: 'user-123',
            email: 'therapist@example.com',
            workspace_id: 'ws-456',
            role: 'therapist',
            is_platform_admin: false,
          },
        },
      })

      await router.push('/accept-invitation?token=valid-token')
      await router.isReady()

      mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await flushPromises()

      expect(consoleInfoSpy).toHaveBeenCalledWith(
        '[AcceptInvitation] User authenticated:',
        'user-123'
      )
    })

    it('logs error to console on failure', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error')

      vi.mocked(apiClient.get).mockRejectedValue({
        response: {
          status: 404,
          data: {},
        },
      })

      await router.push('/accept-invitation?token=invalid-token')
      await router.isReady()

      mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await flushPromises()

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        '[AcceptInvitation] Invitation acceptance failed:',
        expect.any(Object)
      )
    })
  })

  describe('Accessibility', () => {
    it('has proper semantic structure', async () => {
      await router.push('/accept-invitation')
      await router.isReady()

      const wrapper = mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await wrapper.vm.$nextTick()

      // Main container should exist
      expect(wrapper.find('.min-h-screen').exists()).toBe(true)

      // Content should be centered
      expect(wrapper.find('.items-center.justify-center').exists()).toBe(true)
    })

    it('error state is accessible', async () => {
      await router.push('/accept-invitation')
      await router.isReady()

      const wrapper = mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await wrapper.vm.$nextTick()

      // Error heading should exist
      const heading = wrapper.find('h2')
      expect(heading.text()).toBe('Invitation Failed')

      // Error message should be visible
      expect(wrapper.text()).toContain('Invitation link is missing token')

      // Link to login should be keyboard accessible
      const loginLink = wrapper.find('a[href="/login"]')
      expect(loginLink.exists()).toBe(true)
    })

    it('success state is accessible', async () => {
      vi.mocked(apiClient.get).mockResolvedValue({
        data: {
          success: true,
          user: {
            id: 'user-123',
            email: 'therapist@example.com',
            workspace_id: 'ws-456',
            role: 'therapist',
            is_platform_admin: false,
          },
        },
      })

      await router.push('/accept-invitation?token=valid-token')
      await router.isReady()

      const wrapper = mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      await flushPromises()
      await wrapper.vm.$nextTick()

      // Success heading should exist
      const heading = wrapper.find('h2')
      expect(heading.text()).toBe('Welcome to PazPaz!')

      // Success message should be visible
      expect(wrapper.text()).toContain('Your account has been activated')
    })
  })

  describe('Responsive Design', () => {
    it('has responsive container classes', async () => {
      await router.push('/accept-invitation')
      await router.isReady()

      const wrapper = mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      const container = wrapper.find('.max-w-md')
      expect(container.exists()).toBe(true)
      expect(container.classes()).toContain('w-full')
    })

    it('has proper padding on all screen sizes', async () => {
      await router.push('/accept-invitation')
      await router.isReady()

      const wrapper = mount(AcceptInvitationView, {
        global: { plugins: [router, pinia] },
      })

      const innerContainer = wrapper.find('.p-8')
      expect(innerContainer.exists()).toBe(true)
    })
  })
})
