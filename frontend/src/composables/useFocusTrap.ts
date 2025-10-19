/**
 * Focus Trap Composable
 *
 * Traps keyboard focus within a container element (typically a modal).
 * Ensures accessibility by preventing focus from leaving the modal while it's open.
 *
 * Features:
 * - Traps Tab and Shift+Tab navigation
 * - Automatically focuses first focusable element on activation
 * - Returns focus to trigger element on deactivation
 * - Works with dynamic content
 *
 * Usage:
 *   const containerRef = ref<HTMLElement | null>(null)
 *   const { activate, deactivate } = useFocusTrap(containerRef)
 *
 *   watch(() => props.open, (isOpen) => {
 *     if (isOpen) {
 *       activate()
 *     } else {
 *       deactivate()
 *     }
 *   })
 */

import { ref, type Ref } from 'vue'

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

export function useFocusTrap(containerRef: Ref<HTMLElement | null>) {
  const previouslyFocusedElement = ref<HTMLElement | null>(null)

  /**
   * Get all focusable elements within the container
   */
  function getFocusableElements(): HTMLElement[] {
    if (!containerRef.value) return []

    const elements = Array.from(
      containerRef.value.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
    )

    // Filter out invisible elements
    return elements.filter((el) => {
      return el.offsetParent !== null && !el.hasAttribute('aria-hidden')
    })
  }

  /**
   * Handle Tab key press to trap focus
   */
  function handleTabKey(event: KeyboardEvent) {
    const focusableElements = getFocusableElements()

    if (focusableElements.length === 0) {
      event.preventDefault()
      return
    }

    const firstElement = focusableElements[0]
    const lastElement = focusableElements[focusableElements.length - 1]

    if (!firstElement || !lastElement) return

    // Shift + Tab (backwards)
    if (event.shiftKey) {
      if (document.activeElement === firstElement) {
        event.preventDefault()
        lastElement.focus()
      }
    }
    // Tab (forwards)
    else {
      if (document.activeElement === lastElement) {
        event.preventDefault()
        firstElement.focus()
      }
    }
  }

  /**
   * Keyboard event listener
   */
  function handleKeyDown(event: KeyboardEvent) {
    if (event.key === 'Tab') {
      handleTabKey(event)
    }
  }

  /**
   * Activate focus trap
   */
  function activate() {
    // Store the currently focused element
    previouslyFocusedElement.value = document.activeElement as HTMLElement

    // Wait for next tick to ensure modal is rendered
    setTimeout(() => {
      const focusableElements = getFocusableElements()
      if (focusableElements.length > 0) {
        // Focus the first focusable element
        focusableElements[0]?.focus()
      }

      // Add event listener for Tab key
      document.addEventListener('keydown', handleKeyDown)
    }, 0)
  }

  /**
   * Deactivate focus trap and return focus
   */
  function deactivate() {
    // Remove event listener
    document.removeEventListener('keydown', handleKeyDown)

    // Return focus to previously focused element
    setTimeout(() => {
      if (
        previouslyFocusedElement.value &&
        typeof previouslyFocusedElement.value.focus === 'function'
      ) {
        previouslyFocusedElement.value.focus()
      }
    }, 0)
  }

  return {
    activate,
    deactivate,
  }
}
