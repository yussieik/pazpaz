<script setup lang="ts">
import { RouterView } from 'vue-router'

/**
 * Root App Component
 *
 * Provides the main application layout with router outlet.
 */
</script>

<template>
  <div id="app" class="min-h-screen bg-gray-50">
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
