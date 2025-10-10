import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Toast, { POSITION } from 'vue-toastification'
import type { PluginOptions } from 'vue-toastification/dist/types/types'
import 'vue-toastification/dist/index.css'
import router from './router'
import './style.css'
import './assets/calendar-patterns.css'
import App from './App.vue'

const app = createApp(App)

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

app.use(createPinia())
app.use(router)
app.use(Toast, toastOptions)

app.mount('#app')
