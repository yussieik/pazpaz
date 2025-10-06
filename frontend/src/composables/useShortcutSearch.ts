import { ref, computed } from 'vue'
import type { ShortcutConfig } from '@/config/keyboardShortcuts'

/**
 * Composable for searching and filtering keyboard shortcuts
 *
 * Provides instant search functionality across shortcut descriptions,
 * keys, categories, and page names.
 *
 * @param shortcuts - Array of keyboard shortcuts to search
 * @returns Search state and filtering utilities
 */
export function useShortcutSearch(shortcuts: ShortcutConfig[]) {
  const searchQuery = ref('')

  /**
   * Filtered shortcuts based on search query
   *
   * Searches across:
   * - Description text
   * - Keyboard key combinations
   * - Category names
   * - Page names (if applicable)
   */
  const filteredShortcuts = computed(() => {
    const query = searchQuery.value.toLowerCase().trim()
    if (!query) return shortcuts

    return shortcuts.filter((shortcut) => {
      const matchDescription = shortcut.description.toLowerCase().includes(query)
      const matchKeys = shortcut.keys.toLowerCase().includes(query)
      const matchCategory = shortcut.category.toLowerCase().includes(query)
      const matchPage = shortcut.page?.toLowerCase().includes(query) ?? false

      return matchDescription || matchKeys || matchCategory || matchPage
    })
  })

  /**
   * Total number of shortcuts (before filtering)
   */
  const totalCount = computed(() => shortcuts.length)

  /**
   * Number of shortcuts currently displayed (after filtering)
   */
  const filteredCount = computed(() => filteredShortcuts.value.length)

  /**
   * Whether search is currently active (has a query)
   */
  const isSearching = computed(() => searchQuery.value.trim().length > 0)

  /**
   * Clear the search query
   */
  function clearSearch() {
    searchQuery.value = ''
  }

  return {
    searchQuery,
    filteredShortcuts,
    totalCount,
    filteredCount,
    isSearching,
    clearSearch,
  }
}
