<script setup lang="ts">
/**
 * Settings Layout Component
 *
 * Provides a dedicated layout for the Settings page with:
 * - Left sidebar navigation for settings categories
 * - Main content area for active category
 * - Header with "Settings" title
 * - Mobile-responsive (sidebar → horizontal tabs)
 * - Swipe navigation between tabs on mobile
 *
 * This layout is ONLY used for the settings page. When users navigate to /settings,
 * they see this settings-specific layout instead of the main app layout.
 */

import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSwipe } from '@vueuse/core'
import { useI18n } from '@/composables/useI18n'
import SettingsSidebar from '@/components/settings/SettingsSidebar.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

// Settings tabs in order
const settingsTabs = [
  '/settings/notifications',
  '/settings/integrations',
  '/settings/payments',
  '/settings/language',
]

// Get current tab index based on route
const currentTabIndex = computed(() => {
  const index = settingsTabs.indexOf(route.path)
  return index >= 0 ? index : 0
})

// Main content ref for swipe detection
const mainContentRef = ref<HTMLElement | null>(null)

// Swipe navigation
useSwipe(mainContentRef, {
  threshold: 80,
  passive: true,
  onSwipeEnd: (_e: TouchEvent, direction: 'left' | 'right' | 'up' | 'down' | 'none') => {
    // Respect reduced motion preference
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return
    }

    if (direction === 'left') {
      // Swipe left → next tab
      const nextIndex = currentTabIndex.value + 1
      const nextTab = settingsTabs[nextIndex]
      if (nextTab) {
        router.push(nextTab)
      }
    } else if (direction === 'right') {
      // Swipe right → previous tab
      const prevIndex = currentTabIndex.value - 1
      const prevTab = settingsTabs[prevIndex]
      if (prevTab) {
        router.push(prevTab)
      }
    }
  },
})
</script>

<template>
  <div class="flex h-screen bg-slate-50">
    <!-- Settings Sidebar (desktop only, hidden on mobile) -->
    <SettingsSidebar class="hidden lg:block" />

    <!-- Content Area -->
    <div class="flex flex-1 flex-col overflow-hidden">
      <!-- Mobile Horizontal Tabs (visible on mobile only) -->
      <nav class="border-b border-slate-200 bg-white px-4 lg:hidden">
        <ul class="flex gap-2 overflow-x-auto">
          <li>
            <RouterLink
              to="/settings/notifications"
              class="flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors"
              :class="{
                'border-emerald-600 text-emerald-700':
                  $route.path === '/settings/notifications',
                'border-transparent text-slate-600 hover:text-slate-900':
                  $route.path !== '/settings/notifications',
              }"
            >
              <svg
                class="h-5 w-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
                />
              </svg>
              <span>{{ t('settings.layout.notifications') }}</span>
            </RouterLink>
          </li>
          <li>
            <RouterLink
              to="/settings/integrations"
              class="flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors"
              :class="{
                'border-emerald-600 text-emerald-700':
                  $route.path === '/settings/integrations',
                'border-transparent text-slate-600 hover:text-slate-900':
                  $route.path !== '/settings/integrations',
              }"
            >
              <svg
                class="h-5 w-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"
                />
              </svg>
              <span>{{ t('settings.layout.integrations') }}</span>
            </RouterLink>
          </li>
          <li>
            <RouterLink
              to="/settings/payments"
              class="flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors"
              :class="{
                'border-emerald-600 text-emerald-700':
                  $route.path === '/settings/payments',
                'border-transparent text-slate-600 hover:text-slate-900':
                  $route.path !== '/settings/payments',
              }"
            >
              <svg
                class="h-5 w-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"
                />
              </svg>
              <span>{{ t('settings.layout.payments') }}</span>
            </RouterLink>
          </li>
          <li>
            <RouterLink
              to="/settings/language"
              class="flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors"
              :class="{
                'border-emerald-600 text-emerald-700': $route.path === '/settings/language',
                'border-transparent text-slate-600 hover:text-slate-900':
                  $route.path !== '/settings/language',
              }"
            >
              <svg
                class="h-5 w-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <span>{{ t('settings.layout.language') }}</span>
            </RouterLink>
          </li>
          <!-- Future categories will be added here -->
          <!-- Example:
          <li>
            <RouterLink to="/settings/account" class="...">
              <AccountIcon />
              <span>Account</span>
            </RouterLink>
          </li>
          -->
        </ul>
      </nav>

      <!-- Router View (category content) -->
      <main ref="mainContentRef" class="flex-1 overflow-y-auto bg-slate-50">
        <div class="mx-auto max-w-4xl px-4 py-6 sm:px-6 lg:px-8">
          <RouterView />
        </div>
      </main>
    </div>
  </div>
</template>
