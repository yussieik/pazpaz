import { onMounted, onUnmounted } from 'vue'

/**
 * Use Immersive Viewport
 *
 * Progressive enhancement for mobile viewport optimization.
 * Provides fallback viewport height calculation for older browsers that don't support
 * modern CSS viewport units (dvh).
 *
 * Modern Approach:
 * - CSS `100dvh` handles viewport adaptation automatically (iOS Safari 15.4+, Chrome 108+)
 * - Browser naturally hides address bar on user scroll (no forced scroll needed)
 * - This composable only provides fallback for legacy browsers
 *
 * What this composable does:
 * - Sets --app-height CSS variable for browsers without dvh support
 * - Updates on resize/orientation change for responsive behavior
 * - No scroll tricks or forced UI manipulation
 *
 * Browser Support:
 * - Modern: Relies on 100dvh from style.css (iOS Safari 15.4+, Chrome 108+)
 * - Legacy: Calculates --app-height manually as fallback
 *
 * Why no scroll trick:
 * - Modern browsers handle address bar hiding naturally on user scroll
 * - Forced scrolling can be jarring and interferes with scroll restoration
 * - Users expect to see address bar on page load (security, UX)
 * - Browser's native behavior is more reliable and accessible
 *
 * Usage:
 * ```ts
 * import { useImmersiveViewport } from '@/composables/useImmersiveViewport'
 *
 * // In App.vue setup()
 * useImmersiveViewport()
 * ```
 *
 * Accessibility:
 * - Does not interfere with browser controls or user preferences
 * - Respects natural scroll behavior
 * - Compatible with screen readers and assistive technologies
 * - No animation or forced movement
 *
 * @example
 * // In App.vue
 * useImmersiveViewport()
 *
 * @see {@link https://web.dev/viewport-units/}
 * @see {@link https://kilianvalkhof.com/2020/css-html/using-css-env-for-safe-area-inset/}
 * @see {@link https://caniuse.com/viewport-unit-variants}
 */
export function useImmersiveViewport() {
  /**
   * Update the --app-height CSS custom property with current viewport height.
   * This serves as a fallback for browsers that don't support dvh units.
   *
   * Modern browsers will ignore this and use 100dvh from CSS.
   * Older browsers will use this calculated value.
   */
  const updateViewportHeight = (): void => {
    const vh = window.innerHeight * 0.01
    document.documentElement.style.setProperty('--app-height', `${vh * 100}px`)
  }

  /**
   * Handle orientation change with slight delay to ensure
   * accurate viewport measurements after rotation.
   */
  const handleOrientationChange = (): void => {
    // Delay allows browser to complete orientation change
    setTimeout(updateViewportHeight, 100)
  }

  onMounted(() => {
    // Initialize viewport height for legacy browsers
    updateViewportHeight()

    // Update viewport height on window resize
    // Handles: keyboard open/close, browser chrome visibility changes
    window.addEventListener('resize', updateViewportHeight)

    // Handle orientation changes (mobile rotation)
    window.addEventListener('orientationchange', handleOrientationChange)
  })

  onUnmounted(() => {
    // Clean up event listeners
    window.removeEventListener('resize', updateViewportHeight)
    window.removeEventListener('orientationchange', handleOrientationChange)
  })
}
