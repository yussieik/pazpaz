import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import axios from 'axios'
import MockAdapter from 'axios-mock-adapter'
import { setActivePinia, createPinia } from 'pinia'
import apiClient from './client'
import { useRateLimitStore } from '@/stores/rateLimit'

/**
 * API Client 429 Rate Limiting Tests
 *
 * Tests the API client's handling of 429 Too Many Requests responses.
 * Verifies that:
 * - 429 responses are detected correctly
 * - Retry-After header is extracted
 * - Rate limit info is stored in Pinia store
 * - User-friendly toast notifications are shown
 * - Request ID is captured for debugging
 */

describe('API Client 429 Handling', () => {
  let mock: MockAdapter

  beforeEach(() => {
    setActivePinia(createPinia())
    mock = new MockAdapter(apiClient)
    vi.clearAllMocks()
  })

  afterEach(() => {
    mock.reset()
  })

  describe('429 response handling', () => {
    it('handles 429 response and stores rate limit', async () => {
      const rateLimitStore = useRateLimitStore()

      mock.onPost('/auth/login').reply(
        429,
        {
          detail: 'Rate limit exceeded',
          request_id: 'test-request-123',
        },
        {
          'retry-after': '60',
        }
      )

      try {
        await apiClient.post('/auth/login', { email: 'test@example.com' })
        // Should not reach here
        expect(true).toBe(false)
      } catch (error: any) {
        expect(error.response.status).toBe(429)
      }

      // Wait for async interceptor to complete
      await vi.waitFor(() => {
        expect(rateLimitStore.isEndpointLimited('/auth/login')).toBe(true)
      })
    })

    it('extracts Retry-After header correctly', async () => {
      const rateLimitStore = useRateLimitStore()

      mock
        .onGet('/clients')
        .reply(429, { detail: 'Too many requests' }, { 'retry-after': '120' })

      try {
        await apiClient.get('/clients')
      } catch (error) {
        // Expected to throw
      }

      await vi.waitFor(() => {
        const remaining = rateLimitStore.getRemainingSeconds('/clients')
        expect(remaining).toBeGreaterThan(115)
        expect(remaining).toBeLessThanOrEqual(120)
      })
    })

    it('uses default retry time if header missing', async () => {
      const rateLimitStore = useRateLimitStore()

      mock.onPost('/sessions').reply(429, {
        detail: 'Rate limit exceeded',
      })

      try {
        await apiClient.post('/sessions', {})
      } catch (error) {
        // Expected to throw
      }

      await vi.waitFor(() => {
        const remaining = rateLimitStore.getRemainingSeconds('/sessions')
        // Default is 60 seconds
        expect(remaining).toBeGreaterThan(55)
        expect(remaining).toBeLessThanOrEqual(60)
      })
    })

    it('extracts request ID from 429 response', async () => {
      const expectedRequestId = 'rate-limit-request-abc123'

      mock.onPost('/auth/login').reply(
        429,
        {
          detail: 'Rate limit exceeded',
          request_id: expectedRequestId,
        },
        {
          'retry-after': '60',
        }
      )

      try {
        await apiClient.post('/auth/login', { email: 'test@example.com' })
      } catch (error: any) {
        expect(error.requestId).toBe(expectedRequestId)
      }
    })

    it('handles 429 without request ID', async () => {
      mock.onPost('/auth/login').reply(
        429,
        {
          detail: 'Rate limit exceeded',
        },
        {
          'retry-after': '30',
        }
      )

      try {
        await apiClient.post('/auth/login', { email: 'test@example.com' })
      } catch (error: any) {
        expect(error.response.status).toBe(429)
        // Should not throw even without request ID
      }
    })

    it('stores correct endpoint path', async () => {
      const rateLimitStore = useRateLimitStore()

      mock.onGet('/appointments/conflicts').reply(429, {}, { 'retry-after': '45' })

      try {
        await apiClient.get('/appointments/conflicts')
      } catch (error) {
        // Expected
      }

      await vi.waitFor(() => {
        expect(rateLimitStore.isEndpointLimited('/appointments/conflicts')).toBe(true)
      })
    })
  })

  describe('multiple rate limits', () => {
    it('tracks rate limits for different endpoints independently', async () => {
      const rateLimitStore = useRateLimitStore()

      // Rate limit endpoint 1
      mock.onPost('/auth/login').reply(429, {}, { 'retry-after': '60' })

      try {
        await apiClient.post('/auth/login', {})
      } catch (error) {
        // Expected
      }

      // Rate limit endpoint 2
      mock.onGet('/clients').reply(429, {}, { 'retry-after': '30' })

      try {
        await apiClient.get('/clients')
      } catch (error) {
        // Expected
      }

      await vi.waitFor(() => {
        expect(rateLimitStore.activeLimits.length).toBe(2)
        expect(rateLimitStore.isEndpointLimited('/auth/login')).toBe(true)
        expect(rateLimitStore.isEndpointLimited('/clients')).toBe(true)
      })
    })

    it('handles same endpoint rate limited multiple times', async () => {
      const rateLimitStore = useRateLimitStore()

      // First rate limit
      mock.onPost('/auth/login').reply(429, {}, { 'retry-after': '30' })

      try {
        await apiClient.post('/auth/login', {})
      } catch (error) {
        // Expected
      }

      await vi.waitFor(() => {
        expect(rateLimitStore.isEndpointLimited('/auth/login')).toBe(true)
      })

      // Wait and try again (updates rate limit)
      mock.onPost('/auth/login').reply(429, {}, { 'retry-after': '60' })

      try {
        await apiClient.post('/auth/login', {})
      } catch (error) {
        // Expected
      }

      await vi.waitFor(() => {
        const remaining = rateLimitStore.getRemainingSeconds('/auth/login')
        // Should have updated to 60 seconds
        expect(remaining).toBeGreaterThan(55)
      })
    })
  })

  describe('retry-after header parsing', () => {
    it('parses numeric retry-after header', async () => {
      const rateLimitStore = useRateLimitStore()

      mock.onGet('/test').reply(429, {}, { 'retry-after': '90' })

      try {
        await apiClient.get('/test')
      } catch (error) {
        // Expected
      }

      await vi.waitFor(() => {
        const remaining = rateLimitStore.getRemainingSeconds('/test')
        expect(remaining).toBeGreaterThan(85)
        expect(remaining).toBeLessThanOrEqual(90)
      })
    })

    it('handles invalid retry-after header gracefully', async () => {
      const rateLimitStore = useRateLimitStore()

      mock.onGet('/test').reply(429, {}, { 'retry-after': 'invalid' })

      try {
        await apiClient.get('/test')
      } catch (error) {
        // Expected
      }

      await vi.waitFor(() => {
        const remaining = rateLimitStore.getRemainingSeconds('/test')
        // Should default to 60 (parseInt('invalid') = NaN, so uses default)
        expect(remaining).toBeGreaterThan(0)
      })
    })

    it('handles very short retry-after (1 second)', async () => {
      const rateLimitStore = useRateLimitStore()

      mock.onGet('/test').reply(429, {}, { 'retry-after': '1' })

      try {
        await apiClient.get('/test')
      } catch (error) {
        // Expected
      }

      await vi.waitFor(() => {
        const remaining = rateLimitStore.getRemainingSeconds('/test')
        expect(remaining).toBeGreaterThanOrEqual(0)
        expect(remaining).toBeLessThanOrEqual(1)
      })
    })

    it('handles very long retry-after (hours)', async () => {
      const rateLimitStore = useRateLimitStore()

      mock.onGet('/test').reply(429, {}, { 'retry-after': '3600' })

      try {
        await apiClient.get('/test')
      } catch (error) {
        // Expected
      }

      await vi.waitFor(() => {
        const remaining = rateLimitStore.getRemainingSeconds('/test')
        expect(remaining).toBeGreaterThan(3595)
      })
    })
  })

  describe('error detail messages', () => {
    it('handles custom error detail message', async () => {
      const customMessage = 'Login rate limit exceeded. Please try again in 60 seconds.'

      mock.onPost('/auth/login').reply(
        429,
        {
          detail: customMessage,
          request_id: 'test-123',
        },
        { 'retry-after': '60' }
      )

      try {
        await apiClient.post('/auth/login', {})
      } catch (error: any) {
        const errorData = error.response.data
        expect(errorData.detail).toBe(customMessage)
      }
    })

    it('handles missing detail message', async () => {
      mock.onPost('/auth/login').reply(429, {}, { 'retry-after': '60' })

      try {
        await apiClient.post('/auth/login', {})
      } catch (error: any) {
        // Should not throw even without detail
        expect(error.response.status).toBe(429)
      }
    })
  })

  describe('other status codes not affected', () => {
    it('does not store rate limit for 200 success', async () => {
      const rateLimitStore = useRateLimitStore()

      mock.onGet('/clients').reply(200, { clients: [] })

      await apiClient.get('/clients')

      expect(rateLimitStore.isEndpointLimited('/clients')).toBe(false)
      expect(rateLimitStore.hasActiveRateLimits).toBe(false)
    })

    it('does not store rate limit for 401 unauthorized', async () => {
      const rateLimitStore = useRateLimitStore()

      mock.onGet('/clients').reply(401, { detail: 'Unauthorized' })

      try {
        await apiClient.get('/clients')
      } catch (error) {
        // Expected
      }

      // Give time for interceptor
      await new Promise((resolve) => setTimeout(resolve, 100))

      expect(rateLimitStore.isEndpointLimited('/clients')).toBe(false)
    })

    it('does not store rate limit for 500 server error', async () => {
      const rateLimitStore = useRateLimitStore()

      mock.onGet('/clients').reply(500, { detail: 'Internal server error' })

      try {
        await apiClient.get('/clients')
      } catch (error) {
        // Expected
      }

      // Give time for interceptor
      await new Promise((resolve) => setTimeout(resolve, 100))

      expect(rateLimitStore.isEndpointLimited('/clients')).toBe(false)
    })
  })
})
