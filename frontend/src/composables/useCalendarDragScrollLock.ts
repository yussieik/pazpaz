import { ref } from 'vue'
import { useDeviceType } from './useDeviceType'

/**
 * Scroll isolation state
 */
interface ScrollIsolationState {
  isActive: boolean
  originalScrollPosition: number
  calendarContainer: HTMLElement | null
}

/**
 * Composable for mobile drag-and-drop scroll isolation
 *
 * Phase 1 Features:
 * - Body scroll lock when dragging on mobile
 * - Position: fixed technique for iOS Safari compatibility
 * - Scroll position restoration after drag ends
 * - Only activates on mobile devices (<768px)
 *
 * Phase 2+ (Future):
 * - Auto-scroll near edges
 * - Visual feedback (overlay dimming)
 * - Haptic feedback at boundaries
 *
 * @see /docs/frontend/mobile-drag-scroll-isolation.md for complete spec
 */
export function useCalendarDragScrollLock() {
  const { isMobile } = useDeviceType()

  const scrollIsolation = ref<ScrollIsolationState>({
    isActive: false,
    originalScrollPosition: 0,
    calendarContainer: null,
  })

  /**
   * Activate scroll isolation mode
   * Locks body scroll, enables calendar-only scrolling
   *
   * Strategy:
   * 1. Store current scroll position
   * 2. Apply position: fixed to body (iOS Safari compatible)
   * 3. Add visual feedback class
   */
  function activateScrollIsolation(calendarEl: HTMLElement) {
    // Only activate on mobile devices
    if (!isMobile.value) return

    // Store current scroll position
    scrollIsolation.value.originalScrollPosition = window.scrollY

    // Lock body scroll (iOS Safari compatible technique)
    document.body.style.overflow = 'hidden'
    document.body.style.position = 'fixed'
    document.body.style.width = '100%'
    document.body.style.top = `-${scrollIsolation.value.originalScrollPosition}px`

    // Add visual feedback class
    document.body.classList.add('drag-mode-active')
    calendarEl.classList.add('drag-active')

    // Store calendar container for future auto-scroll feature (Phase 2)
    scrollIsolation.value.calendarContainer =
      calendarEl.querySelector('.calendar-container')
    scrollIsolation.value.isActive = true
  }

  /**
   * Deactivate scroll isolation mode
   * Unlocks body scroll, restores original scroll position
   */
  function deactivateScrollIsolation() {
    // Only proceed if scroll isolation was active
    if (!scrollIsolation.value.isActive) return

    // Unlock body scroll
    document.body.style.overflow = ''
    document.body.style.position = ''
    document.body.style.width = ''
    document.body.style.top = ''

    // Restore scroll position
    window.scrollTo(0, scrollIsolation.value.originalScrollPosition)

    // Remove visual feedback classes
    document.body.classList.remove('drag-mode-active')

    // Find and remove drag-active class from calendar
    const calendarContentArea = document.querySelector('.calendar-content-area')
    if (calendarContentArea) {
      calendarContentArea.classList.remove('drag-active')
    }

    // Reset state
    scrollIsolation.value.isActive = false
    scrollIsolation.value.calendarContainer = null
  }

  /**
   * Check if scroll isolation is currently active
   */
  const isScrollIsolationActive = () => scrollIsolation.value.isActive

  return {
    scrollIsolation,
    activateScrollIsolation,
    deactivateScrollIsolation,
    isScrollIsolationActive,
  }
}
