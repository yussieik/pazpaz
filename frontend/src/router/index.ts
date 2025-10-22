import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

/**
 * Vue Router Configuration
 *
 * Defines application routes and navigation guards.
 * Implements HIPAA-compliant authentication protection for all PHI/PII routes.
 *
 * Security Features:
 * - All routes require authentication by default (requiresAuth: true)
 * - Public routes must explicitly opt out (requiresAuth: false)
 * - Unauthenticated users redirected to /login
 * - Post-login redirect to intended destination
 * - Logged-in users skip login page
 */

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    // Public Routes (No Authentication Required)
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: {
        title: 'Sign In - PazPaz',
        requiresAuth: false,
      },
    },
    {
      path: '/auth/verify',
      name: 'auth-verify',
      component: () => import('@/views/AuthVerifyView.vue'),
      meta: {
        title: 'Verifying Login - PazPaz',
        requiresAuth: false,
      },
    },

    // Protected Routes (Authentication Required - PHI/PII Access)
    {
      path: '/',
      name: 'calendar',
      component: () => import('@/views/CalendarView.vue'),
      meta: {
        title: 'Calendar - PazPaz',
        requiresAuth: true,
      },
    },
    {
      path: '/clients',
      name: 'clients',
      component: () => import('@/views/ClientsView.vue'),
      meta: {
        title: 'Clients - PazPaz',
        requiresAuth: true,
      },
    },
    {
      path: '/clients/:id',
      name: 'client-detail',
      component: () => import('@/views/ClientDetailView.vue'),
      meta: {
        title: 'Client Details - PazPaz',
        requiresAuth: true,
      },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
      meta: {
        title: 'Settings - PazPaz',
        requiresAuth: true,
      },
    },
    {
      path: '/sessions/:id',
      name: 'session-detail',
      component: () => import('@/views/SessionView.vue'),
      meta: {
        title: 'Session - PazPaz',
        requiresAuth: true,
      },
    },

    // Platform Admin Routes
    {
      path: '/platform-admin',
      name: 'platform-admin',
      component: () => import('@/views/PlatformAdminPage.vue'),
      meta: {
        title: 'Platform Admin - PazPaz',
        requiresAuth: true,
        requiresPlatformAdmin: true, // Will be enforced in navigation guard
      },
    },

    // 404 Catch-All (for now, redirect to calendar)
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      redirect: '/',
    },
  ],
})

/**
 * Global Navigation Guard - Authentication Check
 *
 * HIPAA REQUIREMENT: Prevents unauthorized access to PHI/PII routes.
 *
 * Flow:
 * 1. Check if route requires authentication (default: true)
 * 2. If auth required and user not authenticated → redirect to /login
 * 3. If user tries to access /login while authenticated → redirect to /
 * 4. Update page title from route meta
 * 5. Track previous route for back navigation
 * 6. Allow navigation
 */
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  // Default to requiring auth unless explicitly set to false
  const requiresAuth = to.meta.requiresAuth !== false

  // Update page title
  if (to.meta.title) {
    document.title = to.meta.title as string
  }

  // Track previous route for smart back navigation
  to.meta.from = from.path

  // Authentication check
  if (requiresAuth && !authStore.isAuthenticated) {
    // Unauthenticated user trying to access protected route
    const redirectPath = to.fullPath !== '/login' ? to.fullPath : '/'

    console.warn('[Router] Unauthenticated access attempt:', {
      path: to.path,
      requiresAuth,
      isAuthenticated: authStore.isAuthenticated,
      redirectTo: '/login',
    })

    // Redirect to login with return URL
    next({
      path: '/login',
      query: { redirect: redirectPath },
      replace: true,
    })
  } else if (to.path === '/login' && authStore.isAuthenticated) {
    // Already logged in, skip login page
    console.debug('[Router] Already authenticated, redirecting to home')

    next({
      path: '/',
      replace: true,
    })
  } else if (to.meta.requiresPlatformAdmin && !authStore.user?.is_platform_admin) {
    // Authenticated user trying to access platform admin route without permission
    console.warn('[Router] Platform admin access denied:', {
      path: to.path,
      userId: authStore.user?.id,
      isPlatformAdmin: authStore.user?.is_platform_admin,
    })

    // Redirect to home page with 403 equivalent
    next({
      path: '/',
      replace: true,
    })
  } else {
    // Allow navigation
    next()
  }
})

/**
 * After Navigation - Scroll to Top
 *
 * Scrolls to top on route change unless navigating to hash anchor.
 */
router.afterEach((to) => {
  if (!to.hash) {
    window.scrollTo(0, 0)
  }
})

export default router
// Named export for use in other modules (e.g., API client interceptors)
export { router }
