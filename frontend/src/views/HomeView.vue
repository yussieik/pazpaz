<script setup lang="ts">
import { RouterLink } from 'vue-router'

/**
 * Home View
 *
 * Landing page with navigation to main features.
 */
</script>

<template>
  <div class="container mx-auto px-4 py-8">
    <header class="mb-8">
      <h1 class="mb-2 text-4xl font-bold text-gray-900">PazPaz</h1>
      <p class="text-lg text-gray-600">Practice management for independent therapists</p>
    </header>

    <div class="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      <RouterLink
        to="/calendar"
        class="block rounded-lg border border-gray-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md"
      >
        <h2 class="mb-2 text-xl font-semibold text-gray-900">Calendar</h2>
        <p class="text-gray-600">Manage appointments and schedule</p>
      </RouterLink>

      <div
        class="block rounded-lg border border-gray-200 bg-gray-50 p-6 opacity-60 shadow-sm"
      >
        <h2 class="mb-2 text-xl font-semibold text-gray-900">Clients</h2>
        <p class="text-gray-600">Coming soon - Client management</p>
      </div>

      <div
        class="block rounded-lg border border-gray-200 bg-gray-50 p-6 opacity-60 shadow-sm"
      >
        <h2 class="mb-2 text-xl font-semibold text-gray-900">Session Notes</h2>
        <p class="text-gray-600">Coming soon - SOAP documentation</p>
      </div>
    </div>
  </div>
</template>
