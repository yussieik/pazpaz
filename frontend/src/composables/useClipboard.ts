import { ref } from 'vue'

/**
 * Composable for copying text to clipboard
 *
 * Provides a simple interface to copy text using the modern Clipboard API
 * with automatic state management and error handling.
 *
 * @example
 * const { copied, error, copy } = useClipboard()
 * await copy('Hello world')
 * // copied.value === true for 2 seconds
 */
export function useClipboard() {
  const copied = ref(false)
  const error = ref<string | null>(null)

  /**
   * Copy text to clipboard
   * @param text - Text to copy
   * @returns Promise resolving to true if successful, false otherwise
   */
  async function copy(text: string): Promise<boolean> {
    try {
      await navigator.clipboard.writeText(text)
      copied.value = true
      error.value = null

      // Reset copied state after 2 seconds
      setTimeout(() => {
        copied.value = false
      }, 2000)

      return true
    } catch (err) {
      console.error('Failed to copy to clipboard:', err)
      error.value = 'Failed to copy to clipboard'
      copied.value = false
      return false
    }
  }

  return {
    copied,
    error,
    copy,
  }
}
