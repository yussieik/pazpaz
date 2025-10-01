<script setup lang="ts">
/**
 * Settings View - Placeholder for M3
 *
 * Future features:
 * - Account settings (profile, password, 2FA)
 * - Workspace configuration
 * - Services and locations management
 * - Preferences (calendar defaults, notifications)
 */
</script>

<template>
  <div class="container mx-auto px-4 py-8">
    <div class="mx-auto max-w-2xl text-center">
      <div class="mb-4 flex justify-center">
        <svg
          class="h-16 w-16 text-gray-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
          />
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
          />
        </svg>
      </div>
      <h1 class="mb-3 text-2xl font-semibold text-slate-900">Settings</h1>
      <p class="text-gray-600">
        Settings and preferences will be available in M3. This page will include
        account, workspace, and service configuration.
      </p>
      <div
        class="mt-6 rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-700"
      >
        <strong>Planned sections:</strong>
        <ul class="mt-2 space-y-1 text-left">
          <li>• Account settings (profile, password, 2FA)</li>
          <li>• Workspace configuration</li>
          <li>• Services and locations management</li>
          <li>• Preferences (calendar defaults, notifications)</li>
        </ul>
      </div>
    </div>
  </div>
</template>
