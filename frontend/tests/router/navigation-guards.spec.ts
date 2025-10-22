import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'
import { setActivePinia, createPinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'

/**
 * Navigation Guard Tests
 *
 * HIPAA REQUIREMENT: Verify that all PHI/PII routes are protected by authentication.
 *
 * Test Coverage:
 * - Unauthenticated users cannot access protected routes
 * - Unauthenticated users are redirected to /login with return URL
 * - Authenticated users can access all protected routes
 * - Authenticated users skip /login page (redirect to /)
 * - Post-login redirect to intended destination works
 * - Page titles are set correctly from route meta
 */

describe('Navigation Guards', () => {
  let router: any
  let pinia: any

  beforeEach(() => {
    // Create fresh Pinia instance for each test
    pinia = createPinia()
    setActivePinia(pinia)

    // Create router with test routes
    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        // Public routes
        {
          path: '/login',
          name: 'login',
          component: { template: '<div>Login</div>' },
          meta: {
            title: 'Sign In - PazPaz',
            requiresAuth: false,
          },
        },
        {
          path: '/auth/verify',
          name: 'auth-verify',
          component: { template: '<div>Verify</div>' },
          meta: {
            title: 'Verifying - PazPaz',
            requiresAuth: false,
          },
        },
        {
          path: '/accept-invitation',
          name: 'accept-invitation',
          component: { template: '<div>Accept Invitation</div>' },
          meta: {
            title: 'Accept Invitation - PazPaz',
            requiresAuth: false,
          },
        },

        // Protected routes
        {
          path: '/',
          name: 'calendar',
          component: { template: '<div>Calendar</div>' },
          meta: {
            title: 'Calendar - PazPaz',
            requiresAuth: true,
          },
        },
        {
          path: '/clients',
          name: 'clients',
          component: { template: '<div>Clients</div>' },
          meta: {
            title: 'Clients - PazPaz',
            requiresAuth: true,
          },
        },
        {
          path: '/clients/:id',
          name: 'client-detail',
          component: { template: '<div>Client Detail</div>' },
          meta: {
            title: 'Client Details - PazPaz',
            requiresAuth: true,
          },
        },
        {
          path: '/sessions/:id',
          name: 'session-detail',
          component: { template: '<div>Session</div>' },
          meta: {
            title: 'Session - PazPaz',
            requiresAuth: true,
          },
        },
        {
          path: '/settings',
          name: 'settings',
          component: { template: '<div>Settings</div>' },
          meta: {
            title: 'Settings - PazPaz',
            requiresAuth: true,
          },
        },
      ],
    })

    // Add navigation guard (same as router/index.ts)
    router.beforeEach((to: any, from: any, next: any) => {
      const authStore = useAuthStore()
      const requiresAuth = to.meta.requiresAuth !== false

      // Update page title
      if (to.meta.title) {
        document.title = to.meta.title as string
      }

      // Track previous route
      to.meta.from = from.path

      // Authentication check
      if (requiresAuth && !authStore.isAuthenticated) {
        const redirectPath = to.fullPath !== '/login' ? to.fullPath : '/'

        next({
          path: '/login',
          query: { redirect: redirectPath },
          replace: true,
        })
      } else if (to.path === '/login' && authStore.isAuthenticated) {
        next({
          path: '/',
          replace: true,
        })
      } else {
        next()
      }
    })

    // Mock console.warn to avoid noise in test output
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    vi.spyOn(console, 'info').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('Unauthenticated Access', () => {
    it('should redirect unauthenticated user from root to login', async () => {
      const authStore = useAuthStore()
      authStore.clearUser()

      await router.push('/')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/login')
      expect(router.currentRoute.value.query.redirect).toBe('/')
    })

    it('should redirect unauthenticated user from /clients to login', async () => {
      const authStore = useAuthStore()
      authStore.clearUser()

      await router.push('/clients')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/login')
      expect(router.currentRoute.value.query.redirect).toBe('/clients')
    })

    it('should redirect unauthenticated user from /clients/:id to login', async () => {
      const authStore = useAuthStore()
      authStore.clearUser()

      await router.push('/clients/123')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/login')
      expect(router.currentRoute.value.query.redirect).toBe('/clients/123')
    })

    it('should redirect unauthenticated user from /sessions/:id to login', async () => {
      const authStore = useAuthStore()
      authStore.clearUser()

      await router.push('/sessions/456')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/login')
      expect(router.currentRoute.value.query.redirect).toBe('/sessions/456')
    })

    it('should redirect unauthenticated user from /settings to login', async () => {
      const authStore = useAuthStore()
      authStore.clearUser()

      await router.push('/settings')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/login')
      expect(router.currentRoute.value.query.redirect).toBe('/settings')
    })

    it('should allow unauthenticated user to access /login', async () => {
      const authStore = useAuthStore()
      authStore.clearUser()

      await router.push('/login')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/login')
    })

    it('should allow unauthenticated user to access /auth/verify', async () => {
      const authStore = useAuthStore()
      authStore.clearUser()

      await router.push('/auth/verify')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/auth/verify')
    })

    it('should allow unauthenticated user to access /accept-invitation', async () => {
      const authStore = useAuthStore()
      authStore.clearUser()

      await router.push('/accept-invitation')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/accept-invitation')
    })

    it('should allow unauthenticated user to access /accept-invitation with token', async () => {
      const authStore = useAuthStore()
      authStore.clearUser()

      await router.push('/accept-invitation?token=abc123')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/accept-invitation')
      expect(router.currentRoute.value.query.token).toBe('abc123')
    })
  })

  describe('Authenticated Access', () => {
    beforeEach(() => {
      const authStore = useAuthStore()
      authStore.setUser({
        id: '123e4567-e89b-12d3-a456-426614174000',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })
    })

    it('should allow authenticated user to access root', async () => {
      await router.push('/')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/')
    })

    it('should allow authenticated user to access /clients', async () => {
      await router.push('/clients')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/clients')
    })

    it('should allow authenticated user to access /clients/:id', async () => {
      await router.push('/clients/123')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/clients/123')
    })

    it('should allow authenticated user to access /sessions/:id', async () => {
      await router.push('/sessions/456')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/sessions/456')
    })

    it('should allow authenticated user to access /settings', async () => {
      await router.push('/settings')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/settings')
    })

    it('should redirect authenticated user from /login to root', async () => {
      await router.push('/login')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/')
    })

    it('should allow authenticated user to access /auth/verify (for 2FA flow)', async () => {
      await router.push('/auth/verify')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/auth/verify')
    })

    it('should allow authenticated user to access /accept-invitation (edge case)', async () => {
      // Edge case: user is already authenticated but somehow hits invitation link
      // Should allow access (component will handle the logic)
      await router.push('/accept-invitation?token=abc123')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/accept-invitation')
    })
  })

  describe('Post-Login Redirect', () => {
    it('should redirect to intended destination after login', async () => {
      const authStore = useAuthStore()

      // Start unauthenticated, try to access /clients
      authStore.clearUser()
      await router.push('/clients')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/login')
      const redirectPath = router.currentRoute.value.query.redirect as string

      // Simulate login
      authStore.setUser({
        id: '123e4567-e89b-12d3-a456-426614174000',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })

      // Navigate to redirect path
      await router.push(redirectPath || '/')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/clients')
    })

    it('should default to home if no redirect specified', async () => {
      const authStore = useAuthStore()

      authStore.setUser({
        id: '123e4567-e89b-12d3-a456-426614174000',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })

      await router.push('/login')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/')
    })

    it('should preserve query params in redirect URL', async () => {
      const authStore = useAuthStore()

      // Try to access /clients?search=john while unauthenticated
      authStore.clearUser()
      await router.push('/clients?search=john')
      await router.isReady()

      expect(router.currentRoute.value.path).toBe('/login')
      expect(router.currentRoute.value.query.redirect).toBe('/clients?search=john')
    })
  })

  describe('Page Title Updates', () => {
    it('should set page title for calendar route', async () => {
      const authStore = useAuthStore()
      authStore.setUser({
        id: '123',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })

      await router.push('/')
      await router.isReady()

      expect(document.title).toBe('Calendar - PazPaz')
    })

    it('should set page title for clients route', async () => {
      const authStore = useAuthStore()
      authStore.setUser({
        id: '123',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })

      await router.push('/clients')
      await router.isReady()

      expect(document.title).toBe('Clients - PazPaz')
    })

    it('should set page title for login route', async () => {
      const authStore = useAuthStore()
      authStore.clearUser()

      await router.push('/login')
      await router.isReady()

      expect(document.title).toBe('Sign In - PazPaz')
    })
  })

  describe('Route Meta Tracking', () => {
    it('should track previous route in meta.from', async () => {
      const authStore = useAuthStore()
      authStore.setUser({
        id: '123',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })

      await router.push('/')
      await router.isReady()
      expect(router.currentRoute.value.meta.from).toBe('/')

      await router.push('/clients')
      await router.isReady()
      expect(router.currentRoute.value.meta.from).toBe('/')

      await router.push('/settings')
      await router.isReady()
      expect(router.currentRoute.value.meta.from).toBe('/clients')
    })
  })

  describe('Edge Cases', () => {
    it('should handle rapid navigation without race conditions', async () => {
      const authStore = useAuthStore()
      authStore.clearUser()

      // Rapidly navigate to multiple routes
      const promises = [
        router.push('/'),
        router.push('/clients'),
        router.push('/settings'),
      ]

      await Promise.all(promises)
      await router.isReady()

      // Should end up at login regardless of race conditions
      expect(router.currentRoute.value.path).toBe('/login')
    })

    it('should handle authentication state change during navigation', async () => {
      const authStore = useAuthStore()
      authStore.clearUser()

      // Start navigation while unauthenticated
      const navigationPromise = router.push('/clients')

      // Authenticate during navigation (simulate slow network)
      authStore.setUser({
        id: '123',
        email: 'test@example.com',
        workspace_id: 'ws-123',
        role: 'therapist',
      })

      await navigationPromise
      await router.isReady()

      // Vue Router checks auth state when guard executes
      // If auth state changes during navigation, the latest state is used
      // This is correct behavior - user was authenticated when guard ran
      expect(router.currentRoute.value.path).toBe('/clients')
    })

    it('should handle missing requiresAuth meta (default to true)', async () => {
      const authStore = useAuthStore()
      authStore.clearUser()

      // Add route without explicit requiresAuth meta
      router.addRoute({
        path: '/test',
        name: 'test',
        component: { template: '<div>Test</div>' },
        meta: {},
      })

      await router.push('/test')
      await router.isReady()

      // Should redirect to login (default requiresAuth = true)
      expect(router.currentRoute.value.path).toBe('/login')
    })
  })
})
