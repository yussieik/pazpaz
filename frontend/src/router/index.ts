import { createRouter, createWebHistory } from 'vue-router'

/**
 * Vue Router Configuration
 *
 * Defines application routes and navigation.
 */

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue'),
    },
    {
      path: '/calendar',
      name: 'calendar',
      component: () => import('@/views/CalendarView.vue'),
    },
    // TODO: Add more routes as features are implemented
    // - /clients - Client management
    // - /clients/:id - Client detail
    // - /sessions - Session notes
    // - /sessions/:id - Session detail
  ],
})

export default router
