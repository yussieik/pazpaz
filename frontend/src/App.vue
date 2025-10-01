<script setup lang="ts">
import { RouterView } from 'vue-router'
import AppNavigation from '@/components/navigation/AppNavigation.vue'

/**
 * Root App Component
 *
 * Provides the main application layout with persistent navigation and router outlet.
 */
</script>

<template>
  <div id="app" class="min-h-screen bg-gray-50">
    <AppNavigation />
    <RouterView />
  </div>
</template>

<style>
/* Global styles */
body {
  margin: 0;
  padding: 0;
}
</style>
