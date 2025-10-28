<script setup lang="ts">
/**
 * Integrations Settings View
 *
 * Manages third-party integrations for PazPaz.
 * Currently supports:
 * - Google Calendar OAuth integration
 *
 * Future integrations:
 * - Zoom/Google Meet for online appointments
 * - Email marketing platforms
 * - SMS/messaging services
 */

import GoogleCalendarSettings from '@/components/settings/GoogleCalendarSettings.vue'
</script>

<template>
  <div>
    <!-- Page Header -->
    <div class="mb-8">
      <h1 class="text-2xl font-bold text-slate-900">Integrations</h1>
      <p class="mt-2 text-sm text-slate-600">
        Connect PazPaz with your favorite tools to streamline your workflow
      </p>
    </div>

    <!-- Integrations List -->
    <div class="space-y-8">
      <!-- Google Calendar Integration -->
      <section>
        <h2 class="mb-4 text-lg font-semibold text-slate-900">Calendar Sync</h2>
        <GoogleCalendarSettings />
      </section>

      <!-- Future integrations will be added here -->
      <!-- Example:
      <section>
        <h2 class="mb-4 text-lg font-semibold text-slate-900">Video Conferencing</h2>
        <ZoomSettings />
        <GoogleMeetSettings />
      </section>
      -->
    </div>
  </div>
</template>
