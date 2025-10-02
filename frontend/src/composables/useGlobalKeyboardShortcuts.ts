import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

/**
 * Global Keyboard Shortcuts Composable
 *
 * Implements global navigation shortcuts using a leader key pattern:
 * - g + c: Go to Calendar
 * - g + l: Go to Clients (list)
 *
 * Features:
 * - Leader key timeout (2 seconds)
 * - Context-aware: Disabled when typing in inputs/textareas
 * - Clean up on unmount
 */
export function useGlobalKeyboardShortcuts() {
  const router = useRouter()
  let leaderKeyActive = false
  let leaderKeyTimeout: number | null = null

  /**
   * Check if user is currently typing in an input context
   */
  function isTypingContext(event: KeyboardEvent): boolean {
    const target = event.target as HTMLElement
    return (
      target.tagName === 'INPUT' ||
      target.tagName === 'TEXTAREA' ||
      target.contentEditable === 'true' ||
      target.closest('[role="textbox"]') !== null
    )
  }

  /**
   * Handle global keyboard shortcuts
   */
  function handleGlobalShortcuts(event: KeyboardEvent) {
    // Ignore shortcuts when typing
    if (isTypingContext(event)) {
      return
    }

    // Handle leader key (g)
    if (event.key === 'g' && !event.metaKey && !event.ctrlKey && !event.altKey) {
      event.preventDefault()
      leaderKeyActive = true

      // Reset leader key after 2 seconds
      if (leaderKeyTimeout) clearTimeout(leaderKeyTimeout)
      leaderKeyTimeout = window.setTimeout(() => {
        leaderKeyActive = false
      }, 2000)

      return
    }

    // Handle leader key sequences
    if (leaderKeyActive) {
      event.preventDefault()
      leaderKeyActive = false
      if (leaderKeyTimeout) clearTimeout(leaderKeyTimeout)

      switch (event.key) {
        case 'c':
          router.push({ name: 'calendar' })
          break
        case 'l':
          router.push({ name: 'clients' })
          break
      }
      return
    }
  }

  onMounted(() => {
    document.addEventListener('keydown', handleGlobalShortcuts)
  })

  onUnmounted(() => {
    document.removeEventListener('keydown', handleGlobalShortcuts)
    if (leaderKeyTimeout) clearTimeout(leaderKeyTimeout)
  })
}
