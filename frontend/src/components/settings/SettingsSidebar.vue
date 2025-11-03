<script setup lang="ts">
/**
 * Settings Sidebar Component
 *
 * Navigation sidebar for settings categories.
 * Features:
 * - List of category links with icons
 * - Active state styling (emerald background)
 * - Keyboard navigation support
 * - Currently shows only "Notifications" category
 * - Future categories commented out for easy addition
 */

import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from '@/composables/useI18n'

const { t } = useI18n()

/**
 * Settings category definition
 */
interface SettingsCategory {
  id: string
  name: string
  path: string
  icon: string
  description: string
}

/**
 * Settings categories
 * Future categories are commented out and ready to be enabled
 */
const categories = computed<SettingsCategory[]>(() => [
  {
    id: 'notifications',
    name: t('settings.sidebar.notifications.name'),
    path: '/settings/notifications',
    icon: 'bell',
    description: t('settings.sidebar.notifications.description'),
  },
  {
    id: 'integrations',
    name: t('settings.sidebar.integrations.name'),
    path: '/settings/integrations',
    icon: 'link',
    description: t('settings.sidebar.integrations.description'),
  },
  {
    id: 'payments',
    name: t('settings.sidebar.payments.name'),
    path: '/settings/payments',
    icon: 'credit-card',
    description: t('settings.sidebar.payments.description'),
  },
  // Future categories - uncomment when ready to enable
  // {
  //   id: 'account',
  //   name: 'Account',
  //   path: '/settings/account',
  //   icon: 'user',
  //   description: 'Profile, email, and password',
  // },
  // {
  //   id: 'workspace',
  //   name: 'Workspace',
  //   path: '/settings/workspace',
  //   icon: 'briefcase',
  //   description: 'Workspace name and preferences',
  // },
  // {
  //   id: 'privacy',
  //   name: 'Privacy & Security',
  //   path: '/settings/privacy',
  //   icon: 'shield',
  //   description: 'Data privacy and security settings',
  // },
  // {
  //   id: 'billing',
  //   name: 'Billing',
  //   path: '/settings/billing',
  //   icon: 'credit-card',
  //   description: 'Subscription and payment methods',
  // },
])

const route = useRoute()

/**
 * Check if a category is currently active
 */
function isActive(categoryPath: string): boolean {
  return route.path === categoryPath
}

/**
 * Get icon SVG path based on icon name
 */
function getIconPath(iconName: string): string {
  const icons: Record<string, string> = {
    bell: 'M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9',
    user: 'M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z',
    briefcase:
      'M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z',
    shield:
      'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z',
    link: 'M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1',
    'credit-card':
      'M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z',
  }
  return icons[iconName] ?? icons.bell!
}
</script>

<template>
  <nav
    class="w-48 border-r border-slate-200 bg-slate-50 px-3 py-6"
    :aria-label="t('settings.sidebar.ariaLabel')"
  >
    <ul class="space-y-1" role="list">
      <li v-for="category in categories" :key="category.id">
        <RouterLink
          :to="category.path"
          class="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-1 focus-visible:outline-none"
          :class="{
            'bg-emerald-50 text-emerald-700': isActive(category.path),
            'text-slate-700 hover:bg-slate-100': !isActive(category.path),
          }"
          :aria-current="isActive(category.path) ? 'page' : undefined"
        >
          <!-- Icon -->
          <svg
            class="h-5 w-5 flex-shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              :d="getIconPath(category.icon)"
            />
          </svg>

          <!-- Category Name -->
          <span>{{ category.name }}</span>
        </RouterLink>
      </li>
    </ul>
  </nav>
</template>
