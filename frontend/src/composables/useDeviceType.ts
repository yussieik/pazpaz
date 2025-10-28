import { ref, computed, onMounted, onUnmounted } from 'vue'

/**
 * Device type detection composable
 *
 * Detects touch capability and viewport width to determine
 * appropriate keyboard behavior for mobile vs desktop devices.
 *
 * @returns Device type detection state and utilities
 */
export function useDeviceType() {
  const isTouchDevice = ref(false)
  const viewportWidth = ref(window.innerWidth)

  /**
   * Detect touch capability
   * Checks for both touch events and pointer support
   */
  const detectTouch = () => {
    isTouchDevice.value =
      'ontouchstart' in window ||
      navigator.maxTouchPoints > 0 ||
      // @ts-expect-error - msMaxTouchPoints is IE-specific (legacy support)
      navigator.msMaxTouchPoints > 0
  }

  /**
   * Update viewport width on resize
   */
  const updateViewport = () => {
    viewportWidth.value = window.innerWidth
  }

  /**
   * Decision logic: defer keyboard on touch devices <768px
   * This aligns with Tailwind's md: breakpoint (tablets and larger)
   *
   * Desktop (≥768px): Keyboard appears immediately
   * Mobile (<768px): Keyboard deferred until explicit tap
   */
  const shouldDeferKeyboard = computed(() => {
    return isTouchDevice.value && viewportWidth.value < 768
  })

  /**
   * Check if device is mobile based on viewport only
   * Useful for responsive layout decisions
   */
  const isMobile = computed(() => {
    return viewportWidth.value < 768
  })

  /**
   * Check if device is tablet (768px - 1024px)
   */
  const isTablet = computed(() => {
    return viewportWidth.value >= 768 && viewportWidth.value < 1024
  })

  /**
   * Check if device is desktop (≥1024px)
   */
  const isDesktop = computed(() => {
    return viewportWidth.value >= 1024
  })

  onMounted(() => {
    detectTouch()
    window.addEventListener('resize', updateViewport)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', updateViewport)
  })

  return {
    isTouchDevice,
    viewportWidth,
    shouldDeferKeyboard,
    isMobile,
    isTablet,
    isDesktop,
  }
}
