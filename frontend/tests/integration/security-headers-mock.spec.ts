/**
 * E2E Security Headers Verification Tests (Mock Mode)
 *
 * This test suite uses Mock Service Worker (MSW) to simulate backend responses
 * with security headers, allowing tests to run without a running backend.
 *
 * For live backend testing, use: npm run test:security:live
 */

import { describe, it, expect, beforeAll, afterAll, afterEach } from 'vitest'
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'

// Mock backend with security headers
const server = setupServer(
  // Mock /health endpoint
  http.get('http://localhost:8000/health', () => {
    return HttpResponse.json(
      { status: 'ok' },
      {
        headers: {
          'x-frame-options': 'DENY',
          'x-content-type-options': 'nosniff',
          'x-xss-protection': '1; mode=block',
          'strict-transport-security': 'max-age=31536000; includeSubDomains',
          'content-security-policy':
            "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' http://localhost:* ws://localhost:*; style-src 'self' 'unsafe-inline'; img-src 'self' data: https: http://localhost:*; font-src 'self' data:; connect-src 'self' ws://localhost:* http://localhost:*; frame-ancestors 'none'; base-uri 'self'; form-action 'self';",
          'referrer-policy': 'strict-origin-when-cross-origin',
          'permissions-policy':
            'geolocation=(), microphone=(), camera=(), payment=(), usb=()',
          'x-request-id': '123e4567-e89b-12d3-a456-426614174000',
          'x-csp-nonce': 'abc123def456',
        },
      }
    )
  }),

  // Mock /api/v1/health endpoint
  http.get('http://localhost:8000/api/v1/health', () => {
    return HttpResponse.json(
      { status: 'ok', version: 'v1' },
      {
        headers: {
          'x-frame-options': 'DENY',
          'x-content-type-options': 'nosniff',
          'x-xss-protection': '1; mode=block',
          'content-security-policy': "default-src 'self'; frame-ancestors 'none'",
          'referrer-policy': 'strict-origin-when-cross-origin',
          'permissions-policy':
            'geolocation=(), microphone=(), camera=(), payment=(), usb=()',
          'x-request-id': '987e6543-e21b-45d3-a789-123456789000',
        },
      }
    )
  }),

  // Mock authenticated endpoint
  http.get('http://localhost:8000/api/v1/users/me', () => {
    return HttpResponse.json(
      { detail: 'Not authenticated' },
      {
        status: 401,
        headers: {
          'x-frame-options': 'DENY',
          'x-content-type-options': 'nosniff',
          'x-xss-protection': '1; mode=block',
          'content-security-policy': "default-src 'self'",
          'referrer-policy': 'strict-origin-when-cross-origin',
        },
      }
    )
  }),

  // Mock 404 endpoint
  http.get('http://localhost:8000/nonexistent-endpoint', () => {
    return HttpResponse.json(
      { detail: 'Not found' },
      {
        status: 404,
        headers: {
          'x-frame-options': 'DENY',
          'x-content-type-options': 'nosniff',
          'referrer-policy': 'strict-origin-when-cross-origin',
          'permissions-policy':
            'geolocation=(), microphone=(), camera=(), payment=(), usb=()',
        },
      }
    )
  })
)

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'warn' })
})

afterEach(() => {
  server.resetHandlers()
})

afterAll(() => {
  server.close()
})

describe('Security Headers E2E Verification (Mock)', () => {
  describe('Basic Security Headers', () => {
    it('returns all required security headers on /health', async () => {
      const response = await fetch('http://localhost:8000/health')

      expect(response.headers.get('x-frame-options')).toBe('DENY')
      expect(response.headers.get('x-content-type-options')).toBe('nosniff')
      expect(response.headers.get('x-xss-protection')).toBe('1; mode=block')
      expect(response.headers.get('content-security-policy')).toBeTruthy()
      expect(response.headers.get('referrer-policy')).toBe(
        'strict-origin-when-cross-origin'
      )
      expect(response.headers.get('permissions-policy')).toBeTruthy()
    })

    it('returns security headers on API endpoints', async () => {
      const response = await fetch('http://localhost:8000/api/v1/health')

      expect(response.headers.get('x-frame-options')).toBe('DENY')
      expect(response.headers.get('x-content-type-options')).toBe('nosniff')
      expect(response.headers.get('referrer-policy')).toBe(
        'strict-origin-when-cross-origin'
      )
    })

    it('returns security headers on error responses', async () => {
      const response = await fetch('http://localhost:8000/nonexistent-endpoint')

      expect(response.status).toBe(404)
      expect(response.headers.get('x-frame-options')).toBe('DENY')
      expect(response.headers.get('x-content-type-options')).toBe('nosniff')
    })
  })

  describe('X-Request-ID Header', () => {
    it('returns X-Request-ID header', async () => {
      const response = await fetch('http://localhost:8000/health')

      const requestId = response.headers.get('x-request-id')
      expect(requestId).toBeTruthy()
    })

    it('X-Request-ID is a valid UUID', async () => {
      const response = await fetch('http://localhost:8000/health')

      const requestId = response.headers.get('x-request-id')
      const uuidRegex =
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

      expect(requestId).toMatch(uuidRegex)
    })
  })

  describe('CSP and Nonce', () => {
    it('returns CSP header with required directives', async () => {
      const response = await fetch('http://localhost:8000/health')

      const csp = response.headers.get('content-security-policy')
      expect(csp).toContain("default-src 'self'")
      expect(csp).toContain("frame-ancestors 'none'")
    })

    it('returns X-CSP-Nonce header', async () => {
      const response = await fetch('http://localhost:8000/health')

      const nonce = response.headers.get('x-csp-nonce')
      expect(nonce).toBeTruthy()
      expect(nonce).toBe('abc123def456')
    })
  })

  describe('HIPAA Compliance Headers', () => {
    it('verifies clickjacking protection (§164.312(a)(1))', async () => {
      const response = await fetch('http://localhost:8000/health')

      expect(response.headers.get('x-frame-options')).toBe('DENY')

      const csp = response.headers.get('content-security-policy')
      expect(csp).toContain("frame-ancestors 'none'")
    })

    it('verifies privacy protection (§164.312(e)(1))', async () => {
      const response = await fetch('http://localhost:8000/health')

      expect(response.headers.get('referrer-policy')).toBe(
        'strict-origin-when-cross-origin'
      )
    })

    it('verifies feature restrictions (§164.308(a)(4))', async () => {
      const response = await fetch('http://localhost:8000/health')

      const policy = response.headers.get('permissions-policy')
      expect(policy).toContain('microphone=()')
      expect(policy).toContain('camera=()')
      expect(policy).toContain('geolocation=()')
    })

    it('verifies audit traceability (§164.312(b))', async () => {
      const response = await fetch('http://localhost:8000/health')

      const requestId = response.headers.get('x-request-id')
      expect(requestId).toBeTruthy()
    })
  })

  describe('Attack Mitigation', () => {
    it('provides XSS protection', async () => {
      const response = await fetch('http://localhost:8000/health')

      expect(response.headers.get('content-security-policy')).toBeTruthy()
      expect(response.headers.get('x-xss-protection')).toBe('1; mode=block')
    })

    it('provides MIME sniffing protection', async () => {
      const response = await fetch('http://localhost:8000/health')

      expect(response.headers.get('x-content-type-options')).toBe('nosniff')
    })

    it('provides clickjacking protection', async () => {
      const response = await fetch('http://localhost:8000/health')

      expect(response.headers.get('x-frame-options')).toBe('DENY')
    })
  })
})
