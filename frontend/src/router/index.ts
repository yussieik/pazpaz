import { createRouter, createWebHistory } from 'vue-router'

/**
 * Vue Router Configuration
 *
 * Defines application routes and navigation.
 * Calendar is the landing page (root).
 */

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'calendar',
      component: () => import('@/views/CalendarView.vue'),
    },
    {
      path: '/clients',
      name: 'clients',
      component: () => import('@/views/ClientsView.vue'),
    },
    {
      path: '/clients/:id',
      name: 'client-detail',
      component: () => import('@/views/ClientDetailView.vue'),
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
    },
    {
      path: '/auth/verify',
      name: 'auth-verify',
      component: () => import('@/views/AuthVerifyView.vue'),
    },
    {
      path: '/sessions/:id',
      name: 'session-detail',
      component: () => import('@/views/SessionView.vue'),
    },
    // TODO: Add more routes as features are implemented
    // - /sessions - Session list view
  ],
})

// Track previous route for smart back navigation
// Store the previous route path in the destination route's meta
router.beforeEach((to, from) => {
  to.meta.from = from.path
})

export default router
