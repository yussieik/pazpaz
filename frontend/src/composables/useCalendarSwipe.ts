import { useSwipe } from '@vueuse/core'
import type { Ref } from 'vue'

/**
 * useCalendarSwipe - Mobile touch gesture navigation for calendar
 *
 * Enables left/right swipe gestures to navigate between calendar periods.
 * - Swipe left → navigate to next period
 * - Swipe right → navigate to previous period
 *
 * Features:
 * - Minimum swipe distance threshold (50px) to prevent accidental navigation
 * - Only activates on mobile devices (touch-enabled)
 * - Respects reduced motion preferences
 * - Clean composable pattern for easy integration
 *
 * @param target - Ref to the DOM element to attach swipe listeners to (typically calendar container)
 * @param onPrevious - Callback function to navigate to previous period
 * @param onNext - Callback function to navigate to next period
 */
export function useCalendarSwipe(
  target: Ref<HTMLElement | null>,
  onPrevious: () => void,
  onNext: () => void
) {
  // Configure swipe behavior
  const { direction } = useSwipe(target, {
    // Minimum distance threshold to trigger swipe (in pixels)
    // Prevents accidental navigation from small touch movements
    threshold: 50,

    // Only capture horizontal swipes
    passive: true,

    // Handle swipe completion
    onSwipeEnd: (_e: TouchEvent, direction: 'left' | 'right' | 'up' | 'down' | 'none') => {
      // Respect reduced motion preference
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        return
      }

      // Only handle horizontal swipes
      if (direction === 'left') {
        // Swipe left → next period
        onNext()
      } else if (direction === 'right') {
        // Swipe right → previous period
        onPrevious()
      }
    },
  })

  return {
    direction,
  }
}
