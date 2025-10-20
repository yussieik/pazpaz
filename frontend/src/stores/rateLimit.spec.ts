import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useRateLimitStore } from './rateLimit'

/**
 * Rate Limit Store Tests
 *
 * Tests for the rate limit tracking store that manages
 * 429 Too Many Requests responses from the backend.
 *
 * Test coverage:
 * - Setting rate limits
 * - Checking rate limit status
 * - Calculating remaining seconds
 * - Auto-expiry of rate limits
 * - Multiple concurrent rate limits
 */

describe('useRateLimitStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('setRateLimit', () => {
    it('sets rate limit for endpoint', () => {
      const store = useRateLimitStore()
      store.setRateLimit('/api/v1/auth/login', 60)

      expect(store.isEndpointLimited('/api/v1/auth/login')).toBe(true)
      expect(store.hasActiveRateLimits).toBe(true)
    })

    it('stores rate limit info with correct expiry time', () => {
      const store = useRateLimitStore()
      const now = Date.now()

      store.setRateLimit('/api/v1/auth/login', 60)

      const limit = store.rateLimits.get('/api/v1/auth/login')
      expect(limit).toBeDefined()
      expect(limit?.retryAfter).toBe(60)
      expect(limit?.endpoint).toBe('/api/v1/auth/login')
      expect(limit?.expiresAt).toBeGreaterThanOrEqual(now + 60000)
      expect(limit?.isLimited).toBe(true)
    })

    it('auto-clears rate limit after expiry', () => {
      const store = useRateLimitStore()
      store.setRateLimit('/api/v1/auth/login', 2) // 2 seconds

      expect(store.isEndpointLimited('/api/v1/auth/login')).toBe(true)

      // Advance time past expiry
      vi.advanceTimersByTime(2100)

      expect(store.isEndpointLimited('/api/v1/auth/login')).toBe(false)
    })

    it('handles multiple rate limits independently', () => {
      const store = useRateLimitStore()
      store.setRateLimit('/api/v1/auth/login', 60)
      store.setRateLimit('/api/v1/clients', 30)

      expect(store.isEndpointLimited('/api/v1/auth/login')).toBe(true)
      expect(store.isEndpointLimited('/api/v1/clients')).toBe(true)
      expect(store.activeLimits.length).toBe(2)
    })
  })

  describe('clearRateLimit', () => {
    it('clears specific rate limit', () => {
      const store = useRateLimitStore()
      store.setRateLimit('/api/v1/auth/login', 60)
      expect(store.isEndpointLimited('/api/v1/auth/login')).toBe(true)

      store.clearRateLimit('/api/v1/auth/login')
      expect(store.isEndpointLimited('/api/v1/auth/login')).toBe(false)
    })

    it('does not affect other rate limits', () => {
      const store = useRateLimitStore()
      store.setRateLimit('/api/v1/auth/login', 60)
      store.setRateLimit('/api/v1/clients', 30)

      store.clearRateLimit('/api/v1/auth/login')

      expect(store.isEndpointLimited('/api/v1/auth/login')).toBe(false)
      expect(store.isEndpointLimited('/api/v1/clients')).toBe(true)
    })
  })

  describe('clearAllRateLimits', () => {
    it('clears all rate limits', () => {
      const store = useRateLimitStore()
      store.setRateLimit('/api/v1/auth/login', 60)
      store.setRateLimit('/api/v1/clients', 30)
      store.setRateLimit('/api/v1/appointments', 45)

      expect(store.activeLimits.length).toBe(3)

      store.clearAllRateLimits()

      expect(store.activeLimits.length).toBe(0)
      expect(store.hasActiveRateLimits).toBe(false)
    })
  })

  describe('isEndpointLimited', () => {
    it('returns false for non-limited endpoint', () => {
      const store = useRateLimitStore()
      expect(store.isEndpointLimited('/api/v1/auth/login')).toBe(false)
    })

    it('returns true for limited endpoint', () => {
      const store = useRateLimitStore()
      store.setRateLimit('/api/v1/auth/login', 60)
      expect(store.isEndpointLimited('/api/v1/auth/login')).toBe(true)
    })

    it('returns false for expired rate limit', () => {
      const store = useRateLimitStore()
      store.setRateLimit('/api/v1/auth/login', 1)

      expect(store.isEndpointLimited('/api/v1/auth/login')).toBe(true)

      vi.advanceTimersByTime(1100) // Past expiry

      expect(store.isEndpointLimited('/api/v1/auth/login')).toBe(false)
    })

    it('auto-cleans expired limits when checked', () => {
      const store = useRateLimitStore()
      store.setRateLimit('/api/v1/auth/login', 1)

      expect(store.rateLimits.has('/api/v1/auth/login')).toBe(true)

      vi.advanceTimersByTime(1100)
      store.isEndpointLimited('/api/v1/auth/login')

      // Should be cleaned from map
      expect(store.rateLimits.has('/api/v1/auth/login')).toBe(false)
    })
  })

  describe('getRemainingSeconds', () => {
    it('returns 0 for non-limited endpoint', () => {
      const store = useRateLimitStore()
      expect(store.getRemainingSeconds('/api/v1/auth/login')).toBe(0)
    })

    it('calculates remaining seconds correctly', () => {
      const store = useRateLimitStore()
      store.setRateLimit('/api/v1/auth/login', 60)

      const remaining = store.getRemainingSeconds('/api/v1/auth/login')
      expect(remaining).toBeGreaterThan(55)
      expect(remaining).toBeLessThanOrEqual(60)
    })

    it('updates remaining time as time passes', () => {
      const store = useRateLimitStore()
      store.setRateLimit('/api/v1/auth/login', 60)

      const initial = store.getRemainingSeconds('/api/v1/auth/login')
      expect(initial).toBeGreaterThan(55)

      vi.advanceTimersByTime(30000) // 30 seconds

      const after30s = store.getRemainingSeconds('/api/v1/auth/login')
      expect(after30s).toBeGreaterThan(25)
      expect(after30s).toBeLessThan(35)
    })

    it('returns 0 for expired rate limit', () => {
      const store = useRateLimitStore()
      store.setRateLimit('/api/v1/auth/login', 5)

      vi.advanceTimersByTime(6000) // Past expiry

      expect(store.getRemainingSeconds('/api/v1/auth/login')).toBe(0)
    })

    it('rounds up fractional seconds', () => {
      const store = useRateLimitStore()
      store.setRateLimit('/api/v1/auth/login', 60)

      vi.advanceTimersByTime(500) // 0.5 seconds

      const remaining = store.getRemainingSeconds('/api/v1/auth/login')
      // Should round up to 60 (ceiling)
      expect(remaining).toBeGreaterThanOrEqual(59)
    })
  })

  describe('hasActiveRateLimits', () => {
    it('returns false when no rate limits', () => {
      const store = useRateLimitStore()
      expect(store.hasActiveRateLimits).toBe(false)
    })

    it('returns true when rate limits exist', () => {
      const store = useRateLimitStore()
      store.setRateLimit('/api/v1/auth/login', 60)
      expect(store.hasActiveRateLimits).toBe(true)
    })

    it('returns false after all rate limits cleared', () => {
      const store = useRateLimitStore()
      store.setRateLimit('/api/v1/auth/login', 60)
      store.clearRateLimit('/api/v1/auth/login')
      expect(store.hasActiveRateLimits).toBe(false)
    })
  })

  describe('activeLimits', () => {
    it('returns empty array when no rate limits', () => {
      const store = useRateLimitStore()
      expect(store.activeLimits).toEqual([])
    })

    it('returns all active rate limits as array', () => {
      const store = useRateLimitStore()
      store.setRateLimit('/api/v1/auth/login', 60)
      store.setRateLimit('/api/v1/clients', 30)

      const limits = store.activeLimits
      expect(limits).toHaveLength(2)
      expect(limits.some((l) => l.endpoint === '/api/v1/auth/login')).toBe(true)
      expect(limits.some((l) => l.endpoint === '/api/v1/clients')).toBe(true)
    })

    it('includes all rate limit info in array', () => {
      const store = useRateLimitStore()
      store.setRateLimit('/api/v1/auth/login', 60)

      const limits = store.activeLimits
      expect(limits[0]).toMatchObject({
        endpoint: '/api/v1/auth/login',
        retryAfter: 60,
        isLimited: true,
      })
      expect(limits[0].expiresAt).toBeGreaterThan(Date.now())
    })
  })

  describe('edge cases', () => {
    it('handles very short rate limits (1 second)', () => {
      const store = useRateLimitStore()
      store.setRateLimit('/api/v1/auth/login', 1)

      expect(store.isEndpointLimited('/api/v1/auth/login')).toBe(true)

      vi.advanceTimersByTime(1100)

      expect(store.isEndpointLimited('/api/v1/auth/login')).toBe(false)
    })

    it('handles very long rate limits (hours)', () => {
      const store = useRateLimitStore()
      const oneHour = 3600
      store.setRateLimit('/api/v1/auth/login', oneHour)

      expect(store.getRemainingSeconds('/api/v1/auth/login')).toBeGreaterThan(
        3595
      )
    })

    it('handles updating existing rate limit', () => {
      const store = useRateLimitStore()
      store.setRateLimit('/api/v1/auth/login', 30)

      vi.advanceTimersByTime(10000) // 10 seconds

      // Update with new rate limit
      store.setRateLimit('/api/v1/auth/login', 60)

      // Should reset to 60 seconds
      const remaining = store.getRemainingSeconds('/api/v1/auth/login')
      expect(remaining).toBeGreaterThan(55)
      expect(remaining).toBeLessThanOrEqual(60)
    })

    it('handles clearing non-existent rate limit gracefully', () => {
      const store = useRateLimitStore()
      expect(() => {
        store.clearRateLimit('/api/v1/nonexistent')
      }).not.toThrow()
    })
  })
})
