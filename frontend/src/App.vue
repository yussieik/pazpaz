<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { RouterView } from 'vue-router'
import AppNavigation from '@/components/navigation/AppNavigation.vue'
import KeyboardShortcutsHelp from '@/components/calendar/KeyboardShortcutsHelp.vue'
import { useGlobalKeyboardShortcuts } from '@/composables/useGlobalKeyboardShortcuts'

/**
 * Root App Component
 *
 * Provides the main application layout with persistent navigation and router outlet.
 * Handles global keyboard shortcuts and help modal.
 */

// Enable global shortcuts at app level
useGlobalKeyboardShortcuts()

// Global keyboard shortcuts help modal
const showKeyboardHelp = ref(false)

/**
 * Handle global '?' key to show keyboard shortcuts help
 */
function handleHelpKey(e: KeyboardEvent) {
  // Note: '?' typically requires Shift key, so we allow shiftKey
  if (e.key === '?' && !e.metaKey && !e.ctrlKey) {
    // Only trigger if not typing in input field
    const target = e.target as HTMLElement
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA') return

    e.preventDefault()
    showKeyboardHelp.value = true
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleHelpKey)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleHelpKey)
})
</script>

<template>
  <div id="app" class="min-h-screen bg-gray-50">
    <AppNavigation />
    <RouterView />

    <!-- Global Keyboard Shortcuts Help Modal -->
    <KeyboardShortcutsHelp
      :visible="showKeyboardHelp"
      @update:visible="showKeyboardHelp = $event"
    />
  </div>
</template>

<style>
/* Global styles */
body {
  margin: 0;
  padding: 0;
}
</style>
