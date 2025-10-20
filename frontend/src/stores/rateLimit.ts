import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * Rate Limit Store
 *
 * Tracks active rate limits per API endpoint for frontend UX feedback.
 * When backend returns 429 (Too Many Requests), store the rate limit
 * and display countdown timer to users.
 *
 * HIPAA Compliance: Clear communication about system behavior
 * Security: Prevents credential stuffing by enforcing client-side awareness
 */

export interface RateLimitInfo {
  isLimited: boolean
  retryAfter: number // seconds until rate limit expires
  endpoint: string
  expiresAt: number // timestamp (Date.now() + retryAfter * 1000)
}

export const useRateLimitStore = defineStore('rateLimit', () => {
  // Track rate limits per endpoint
  const rateLimits = ref<Map<string, RateLimitInfo>>(new Map())

  /**
   * Set rate limit for an endpoint
   *
   * @param endpoint - API endpoint path (e.g., /api/v1/auth/login)
   * @param retryAfter - Seconds until rate limit expires
   */
  function setRateLimit(endpoint: string, retryAfter: number) {
    const expiresAt = Date.now() + retryAfter * 1000

    rateLimits.value.set(endpoint, {
      isLimited: true,
      retryAfter,
      endpoint,
      expiresAt,
    })

    // Auto-clear after expiry
    setTimeout(() => {
      clearRateLimit(endpoint)
    }, retryAfter * 1000)
  }

  /**
   * Clear rate limit for an endpoint
   *
   * @param endpoint - API endpoint path
   */
  function clearRateLimit(endpoint: string) {
    rateLimits.value.delete(endpoint)
  }

  /**
   * Check if endpoint is currently rate limited
   *
   * @param endpoint - API endpoint path
   * @returns true if rate limited, false otherwise
   */
  function isEndpointLimited(endpoint: string): boolean {
    const limit = rateLimits.value.get(endpoint)
    if (!limit) return false

    // Check if still valid (not expired)
    if (Date.now() > limit.expiresAt) {
      clearRateLimit(endpoint)
      return false
    }

    return true
  }

  /**
   * Get remaining seconds until rate limit expires
   *
   * @param endpoint - API endpoint path
   * @returns remaining seconds (0 if not rate limited)
   */
  function getRemainingSeconds(endpoint: string): number {
    const limit = rateLimits.value.get(endpoint)
    if (!limit) return 0

    const remaining = Math.ceil((limit.expiresAt - Date.now()) / 1000)
    return Math.max(0, remaining)
  }

  /**
   * Check if any rate limits are active
   */
  const hasActiveRateLimits = computed(() => rateLimits.value.size > 0)

  /**
   * Get all active rate limits as array
   */
  const activeLimits = computed(() => Array.from(rateLimits.value.values()))

  /**
   * Clear all rate limits (useful for testing or reset)
   */
  function clearAllRateLimits() {
    rateLimits.value.clear()
  }

  return {
    rateLimits,
    setRateLimit,
    clearRateLimit,
    clearAllRateLimits,
    isEndpointLimited,
    getRemainingSeconds,
    hasActiveRateLimits,
    activeLimits,
  }
})
