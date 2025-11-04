import { useSwipe } from '@vueuse/core'
import { ref } from 'vue'
import type { Ref } from 'vue'
import { useI18n } from '@/composables/useI18n'

/**
 * useCalendarSwipe - Mobile touch gesture navigation for calendar
 *
 * Enables left/right swipe gestures to navigate between calendar periods.
 * - LTR: Swipe left → next period, Swipe right → previous period
 * - RTL: Swipe left → previous period, Swipe right → next period
 *
 * Features:
 * - Minimum swipe distance threshold (50px) to prevent accidental navigation
 * - Only activates on mobile devices (touch-enabled)
 * - Respects reduced motion preferences
 * - RTL-aware swipe direction handling
 * - Directional slide transitions that match swipe direction
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
  const { isRTL } = useI18n()

  // Track the last swipe direction for transition
  const swipeDirection = ref<'left' | 'right' | null>(null)

  // Track if we're currently navigating (prevents loading spinner during swipe)
  const isNavigating = ref(false)

  // Configure swipe behavior
  const { direction, lengthX, lengthY } = useSwipe(target, {
    // Minimum distance threshold to trigger swipe (in pixels)
    // Prevents accidental navigation from small touch movements
    threshold: 50,

    // Use passive: false to allow preventDefault on horizontal swipes
    passive: false,

    // Detect horizontal swipes and prevent page scroll
    onSwipe: (e: TouchEvent) => {
      const absX = Math.abs(lengthX.value)
      const absY = Math.abs(lengthY.value)

      // If horizontal swipe is more dominant than vertical, prevent default scroll
      if (absX > absY && absX > 10) {
        e.preventDefault()
      }
    },

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
        swipeDirection.value = 'left'
        isNavigating.value = true
        // In RTL, swipe left goes to previous; in LTR, swipe left goes to next
        if (isRTL.value) {
          onPrevious()
        } else {
          onNext()
        }
      } else if (direction === 'right') {
        swipeDirection.value = 'right'
        isNavigating.value = true
        // In RTL, swipe right goes to next; in LTR, swipe right goes to previous
        if (isRTL.value) {
          onNext()
        } else {
          onPrevious()
        }
      }
    },
  })

  // Reset direction and navigation state after a delay (transition duration + buffer)
  const resetDirection = () => {
    setTimeout(() => {
      swipeDirection.value = null
      isNavigating.value = false
    }, 200) // Match transition duration (140ms) + 60ms buffer
  }

  return {
    direction,
    swipeDirection,
    isNavigating,
    resetDirection,
  }
}
