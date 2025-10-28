import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Toast, { POSITION } from 'vue-toastification'
import type { PluginOptions } from 'vue-toastification/dist/types/types'
import 'vue-toastification/dist/index.css'
import router from './router'
import './style.css'
import './assets/calendar-patterns.css'
import App from './App.vue'
import { useAuthStore } from './stores/auth'
import { configureApiClient } from './api/config'
import { vRtl } from './directives/rtl'

/**
 * Application Bootstrap
 *
 * HIPAA REQUIREMENT: Initialize authentication before mounting app.
 * This ensures route guards have access to auth state and can protect PHI/PII routes.
 *
 * Flow:
 * 1. Create Vue app and Pinia store
 * 2. Initialize authentication (check if user has valid session)
 * 3. Mount app with router (route guards now have auth state)
 */

const app = createApp(App)
const pinia = createPinia()

// Configure the generated API client (CSRF tokens, credentials, base URL)
configureApiClient()

// Configure toast notifications
const toastOptions: PluginOptions = {
  position: POSITION.TOP_RIGHT, // Consistent position for all toasts
  timeout: 3000, // Default timeout (overridden per toast type)
  closeOnClick: true,
  pauseOnFocusLoss: true,
  pauseOnHover: true,
  draggable: true,
  draggablePercent: 0.6,
  showCloseButtonOnHover: false,
  hideProgressBar: false,
  closeButton: 'button',
  icon: true,
  rtl: false,
  transition: 'Vue-Toastification__slideBlurred', // Smooth slide transition
  maxToasts: 3, // Maximum 3 toasts visible to avoid clutter
  newestOnTop: true,
  filterBeforeCreate: (toast, _toasts) => {
    // Completely disable deduplication and caching
    // Each toast is treated as unique, even after dismissal
    // This is essential for practice management where users perform repeated actions
    return toast
  },
  filterToasts: (toasts) => {
    // Don't filter any toasts - allow all to show
    // This prevents the library from caching dismissed toasts
    // Critical fix for: toasts not appearing after first one completes
    return toasts
  },
}

// Install plugins
app.use(pinia)
app.use(Toast, toastOptions)

// Register global directives
app.directive('rtl', vRtl)

// Initialize authentication BEFORE mounting router
// This ensures route guards have access to auth state
const authStore = useAuthStore()

authStore.initializeAuth().finally(() => {
  // Mount app after auth check completes (success or failure)
  app.use(router)
  app.mount('#app')

  console.debug('[App] Mounted with authentication state:', {
    isAuthenticated: authStore.isAuthenticated,
    userId: authStore.user?.id,
  })
})

// Force cache invalidation for Content-Type fix deployment (2025-10-27)
// This comment forces Vite to rebuild fresh, bypassing GitHub Actions build cache
