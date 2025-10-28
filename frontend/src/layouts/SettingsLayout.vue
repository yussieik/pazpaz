<script setup lang="ts">
/**
 * Settings Layout Component
 *
 * Provides a dedicated layout for the Settings page with:
 * - Left sidebar navigation for settings categories
 * - Main content area for active category
 * - Header with "Settings" title
 * - Mobile-responsive (sidebar → horizontal tabs)
 *
 * This layout is ONLY used for the settings page. When users navigate to /settings,
 * they see this settings-specific layout instead of the main app layout.
 */

import SettingsSidebar from '@/components/settings/SettingsSidebar.vue'
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
              <span>Notifications</span>
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
              <span>Integrations</span>
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
      <main class="flex-1 overflow-y-auto bg-slate-50">
        <div class="mx-auto max-w-4xl px-4 py-6 sm:px-6 lg:px-8">
          <RouterView />
        </div>
      </main>
    </div>
  </div>
</template>
