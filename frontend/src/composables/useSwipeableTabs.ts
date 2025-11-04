import { useSwipe } from '@vueuse/core'
import { ref } from 'vue'
import type { Ref } from 'vue'

/**
 * useSwipeableTabs - Touch gesture navigation for tab panels
 *
 * Enables left/right swipe gestures to navigate between tabs on mobile.
 * - Swipe left → navigate to next tab
 * - Swipe right → navigate to previous tab
 *
 * Features:
 * - Minimum swipe distance threshold (80px) to prevent accidental navigation
 * - Only activates on mobile devices (touch-enabled)
 * - Respects reduced motion preferences
 * - Boundary checking (can't swipe beyond first/last tab)
 * - Works with Headless UI TabGroup or any tab system
 *
 * @param target - Ref to the DOM element to attach swipe listeners to (tab panels container)
 * @param currentTabIndex - Ref to the current active tab index (0-based)
 * @param tabCount - Total number of tabs
 * @param onTabChange - Callback function to change tab (receives new index)
 */
export function useSwipeableTabs(
  target: Ref<HTMLElement | null>,
  currentTabIndex: Ref<number>,
  tabCount: number,
  onTabChange: (newIndex: number) => void
) {
  // Track the last swipe direction for potential transition effects
  const swipeDirection = ref<'left' | 'right' | null>(null)

  // Configure swipe behavior
  const { direction } = useSwipe(target, {
    // Minimum distance threshold to trigger swipe (in pixels)
    // Higher threshold for tabs to avoid conflicts with scrolling
    threshold: 80,

    // Only capture horizontal swipes
    passive: true,

    // Handle swipe completion
    onSwipeEnd: (
      _e: TouchEvent,
      direction: 'left' | 'right' | 'up' | 'down' | 'none'
    ) => {
      // Respect reduced motion preference
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        return
      }

      // Only handle horizontal swipes
      if (direction === 'left') {
        // Swipe left → next tab
        const nextIndex = currentTabIndex.value + 1
        if (nextIndex < tabCount) {
          swipeDirection.value = 'left'
          onTabChange(nextIndex)
        }
      } else if (direction === 'right') {
        // Swipe right → previous tab
        const prevIndex = currentTabIndex.value - 1
        if (prevIndex >= 0) {
          swipeDirection.value = 'right'
          onTabChange(prevIndex)
        }
      }
    },
  })

  // Reset direction after a delay (for potential transition effects)
  const resetDirection = () => {
    setTimeout(() => {
      swipeDirection.value = null
    }, 200)
  }

  return {
    direction,
    swipeDirection,
    resetDirection,
  }
}
