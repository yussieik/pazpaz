import { ref, nextTick } from 'vue'

/**
 * Composable for managing screen reader announcements
 *
 * Provides a reactive announcement string that can be used with
 * an aria-live region for accessibility.
 *
 * Usage:
 * ```vue
 * <template>
 *   <div role="status" aria-live="polite" aria-atomic="true" class="sr-only">
 *     {{ announcement }}
 *   </div>
 * </template>
 *
 * <script setup>
 * const { announcement, announce } = useScreenReader()
 *
 * async function handleAction() {
 *   // ... perform action
 *   await announce('Action completed successfully')
 * }
 * </script>
 * ```
 */
export function useScreenReader() {
  const announcement = ref('')

  /**
   * Announce a message to screen readers
   * Clears the announcement first to ensure it's always read,
   * even if the same message is announced twice in a row
   */
  async function announce(message: string) {
    // Clear first to ensure announcement is always read
    announcement.value = ''
    await nextTick()
    announcement.value = message
  }

  return {
    announcement,
    announce,
  }
}
