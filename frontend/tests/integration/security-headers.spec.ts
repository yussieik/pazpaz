/**
 * E2E Security Headers Verification Tests
 *
 * HIPAA Compliance: §164.312(a)(1) - Technical safeguards verification
 *
 * This test suite verifies that all security headers are properly configured
 * and delivered to the frontend through the entire stack (dev server → backend).
 *
 * Tested Headers:
 * - X-Frame-Options: Clickjacking protection
 * - X-Content-Type-Options: MIME sniffing protection
 * - Strict-Transport-Security: HTTPS enforcement (HSTS)
 * - Content-Security-Policy: XSS/injection protection
 * - Referrer-Policy: Privacy protection
 * - Permissions-Policy: Feature restrictions
 * - X-Request-ID: Request tracing
 * - X-CSP-Nonce: CSP nonce for inline scripts
 */

import { describe, it, expect, beforeAll } from 'vitest'
import axios, { type AxiosInstance } from 'axios'

describe('Security Headers E2E Verification', () => {
  let client: AxiosInstance
  const baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

  beforeAll(() => {
    client = axios.create({
      baseURL,
      validateStatus: () => true, // Accept all status codes
      timeout: 5000
    })
  })

  describe('X-Frame-Options (Clickjacking Protection)', () => {
    it('returns X-Frame-Options: DENY on all responses', async () => {
      const response = await client.get('/health')

      expect(response.headers['x-frame-options']).toBe('DENY')
    })

    it('returns X-Frame-Options on API endpoints', async () => {
      const response = await client.get('/api/v1/health')

      expect(response.headers['x-frame-options']).toBe('DENY')
    })

    it('returns X-Frame-Options on different HTTP methods', async () => {
      // GET
      const getResponse = await client.get('/health')
      expect(getResponse.headers['x-frame-options']).toBe('DENY')

      // HEAD
      const headResponse = await client.head('/health')
      expect(headResponse.headers['x-frame-options']).toBe('DENY')

      // OPTIONS (CORS preflight)
      const optionsResponse = await client.options('/health')
      expect(optionsResponse.headers['x-frame-options']).toBe('DENY')
    })

    it('prevents framing attacks on authenticated endpoints', async () => {
      // Even unauthenticated requests should have security headers
      const response = await client.get('/api/v1/users/me')

      expect(response.headers['x-frame-options']).toBe('DENY')
    })
  })

  describe('X-Content-Type-Options (MIME Sniffing Protection)', () => {
    it('returns X-Content-Type-Options: nosniff', async () => {
      const response = await client.get('/health')

      expect(response.headers['x-content-type-options']).toBe('nosniff')
    })

    it('returns nosniff on API endpoints', async () => {
      const response = await client.get('/api/v1/health')

      expect(response.headers['x-content-type-options']).toBe('nosniff')
    })

    it('prevents MIME type sniffing attacks', async () => {
      // Verify header is present even on JSON responses
      const response = await client.get('/api/v1/health')

      expect(response.headers['x-content-type-options']).toBe('nosniff')
      expect(response.headers['content-type']).toContain('application/json')
    })
  })

  describe('Strict-Transport-Security (HSTS)', () => {
    it('returns HSTS header with max-age (production)', async () => {
      const response = await client.get('/health')

      const hsts = response.headers['strict-transport-security']

      // HSTS should be present on non-localhost domains
      // In development (localhost), it may be omitted
      if (hsts) {
        expect(hsts).toBeTruthy()
        expect(hsts).toContain('max-age=')
      }
    })

    it('HSTS max-age is at least 1 year (31536000 seconds)', async () => {
      const response = await client.get('/health')

      const hsts = response.headers['strict-transport-security']

      // Skip test if HSTS not present (localhost)
      if (!hsts) {
        expect(response.request.host).toMatch(/localhost|127\.0\.0\.1/)
        return
      }

      // Extract max-age value
      const match = hsts.match(/max-age=(\d+)/)
      expect(match).toBeTruthy()

      const maxAge = parseInt(match![1], 10)
      expect(maxAge).toBeGreaterThanOrEqual(31536000) // 1 year minimum
    })

    it('HSTS includes includeSubDomains directive', async () => {
      const response = await client.get('/health')

      const hsts = response.headers['strict-transport-security']

      // Skip if not present (localhost)
      if (!hsts) {
        return
      }

      expect(hsts).toContain('includeSubDomains')
    })
  })

  describe('Content-Security-Policy (XSS Protection)', () => {
    it('returns CSP header on all responses', async () => {
      const response = await client.get('/health')

      const csp = response.headers['content-security-policy']
      expect(csp).toBeTruthy()
    })

    it('CSP includes default-src directive', async () => {
      const response = await client.get('/health')

      const csp = response.headers['content-security-policy']
      expect(csp).toContain("default-src 'self'")
    })

    it('CSP includes frame-ancestors directive', async () => {
      const response = await client.get('/health')

      const csp = response.headers['content-security-policy']
      expect(csp).toContain("frame-ancestors 'none'")
    })

    it('CSP includes base-uri directive', async () => {
      const response = await client.get('/health')

      const csp = response.headers['content-security-policy']
      expect(csp).toContain("base-uri 'self'")
    })

    it('CSP includes form-action directive', async () => {
      const response = await client.get('/health')

      const csp = response.headers['content-security-policy']
      expect(csp).toContain("form-action 'self'")
    })

    it('CSP provides XSS protection on API endpoints', async () => {
      const response = await client.get('/api/v1/health')

      const csp = response.headers['content-security-policy']
      expect(csp).toBeTruthy()
      expect(csp).toContain("default-src 'self'")
    })
  })

  describe('Referrer-Policy (Privacy Protection)', () => {
    it('returns Referrer-Policy header', async () => {
      const response = await client.get('/health')

      const referrerPolicy = response.headers['referrer-policy']
      expect(referrerPolicy).toBeTruthy()
    })

    it('uses strict-origin-when-cross-origin policy', async () => {
      const response = await client.get('/health')

      const referrerPolicy = response.headers['referrer-policy']
      expect(referrerPolicy).toBe('strict-origin-when-cross-origin')
    })

    it('protects PHI in URLs from referrer leakage', async () => {
      const response = await client.get('/api/v1/health')

      // Verify policy would prevent cross-origin full URL leakage
      const referrerPolicy = response.headers['referrer-policy']
      expect(referrerPolicy).toBe('strict-origin-when-cross-origin')

      // This ensures that if PHI is in a URL (bad practice, but defense-in-depth),
      // it won't be leaked to third-party sites via the Referer header
    })

    it('returns Referrer-Policy on all endpoint types', async () => {
      const endpoints = ['/health', '/api/v1/health']

      for (const endpoint of endpoints) {
        const response = await client.get(endpoint)
        expect(response.headers['referrer-policy']).toBe(
          'strict-origin-when-cross-origin'
        )
      }
    })
  })

  describe('Permissions-Policy (Feature Restrictions)', () => {
    it('returns Permissions-Policy header', async () => {
      const response = await client.get('/health')

      const permissionsPolicy = response.headers['permissions-policy']
      expect(permissionsPolicy).toBeTruthy()
    })

    it('restricts geolocation API (HIPAA privacy)', async () => {
      const response = await client.get('/health')

      const policy = response.headers['permissions-policy']
      expect(policy).toContain('geolocation=()')
    })

    it('restricts microphone API (PHI protection)', async () => {
      const response = await client.get('/health')

      const policy = response.headers['permissions-policy']
      expect(policy).toContain('microphone=()')
    })

    it('restricts camera API (PHI protection)', async () => {
      const response = await client.get('/health')

      const policy = response.headers['permissions-policy']
      expect(policy).toContain('camera=()')
    })

    it('restricts payment API', async () => {
      const response = await client.get('/health')

      const policy = response.headers['permissions-policy']
      expect(policy).toContain('payment=()')
    })

    it('restricts USB API (security)', async () => {
      const response = await client.get('/health')

      const policy = response.headers['permissions-policy']
      expect(policy).toContain('usb=()')
    })

    it('protects against unauthorized recording', async () => {
      const response = await client.get('/health')

      const policy = response.headers['permissions-policy']

      // Verify all privacy-sensitive features are disabled
      expect(policy).toContain('microphone=()')
      expect(policy).toContain('camera=()')

      // This ensures therapy sessions cannot be recorded via browser APIs
    })
  })

  describe('X-Request-ID (Request Tracing)', () => {
    it('returns X-Request-ID on all responses', async () => {
      const response = await client.get('/health')

      const requestId = response.headers['x-request-id']
      expect(requestId).toBeTruthy()
    })

    it('X-Request-ID is a valid UUID format', async () => {
      const response = await client.get('/health')

      const requestId = response.headers['x-request-id']

      // UUID v4 format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
      const uuidRegex =
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
      expect(requestId).toMatch(uuidRegex)
    })

    it('returns unique X-Request-ID for each request', async () => {
      const response1 = await client.get('/health')
      const response2 = await client.get('/health')

      const requestId1 = response1.headers['x-request-id']
      const requestId2 = response2.headers['x-request-id']

      expect(requestId1).not.toBe(requestId2)
    })

    it('includes X-Request-ID on error responses', async () => {
      const response = await client.get('/nonexistent-endpoint')

      const requestId = response.headers['x-request-id']
      expect(requestId).toBeTruthy()
    })
  })

  describe('X-CSP-Nonce (CSP Nonce)', () => {
    it('returns X-CSP-Nonce header', async () => {
      const response = await client.get('/health')

      const nonce = response.headers['x-csp-nonce']
      expect(nonce).toBeTruthy()
    })

    it('X-CSP-Nonce is cryptographically random', async () => {
      const response = await client.get('/health')

      const nonce = response.headers['x-csp-nonce']

      // Should be a base64url-encoded string (no padding)
      // Length should be reasonable (32+ characters for 256-bit entropy)
      expect(nonce.length).toBeGreaterThanOrEqual(32)
      expect(nonce).toMatch(/^[A-Za-z0-9_-]+$/) // Base64url alphabet
    })

    it('returns unique nonce for each request', async () => {
      const response1 = await client.get('/health')
      const response2 = await client.get('/health')

      const nonce1 = response1.headers['x-csp-nonce']
      const nonce2 = response2.headers['x-csp-nonce']

      expect(nonce1).not.toBe(nonce2)
    })
  })

  describe('X-XSS-Protection (Legacy XSS Protection)', () => {
    it('returns X-XSS-Protection header', async () => {
      const response = await client.get('/health')

      const xssProtection = response.headers['x-xss-protection']
      expect(xssProtection).toBeTruthy()
    })

    it('X-XSS-Protection is set to block mode', async () => {
      const response = await client.get('/health')

      const xssProtection = response.headers['x-xss-protection']
      expect(xssProtection).toBe('1; mode=block')
    })
  })

  describe('Security Headers on Multiple Endpoints', () => {
    const endpoints = [
      '/health',
      '/api/v1/health',
      '/api/v1/users/me',
      '/api/v1/workspaces'
    ]

    endpoints.forEach((endpoint) => {
      it(`returns all security headers on ${endpoint}`, async () => {
        const response = await client.get(endpoint)

        // Core security headers (should be on ALL responses)
        expect(response.headers['x-frame-options']).toBe('DENY')
        expect(response.headers['x-content-type-options']).toBe('nosniff')
        expect(response.headers['x-xss-protection']).toBe('1; mode=block')
        expect(response.headers['referrer-policy']).toBe(
          'strict-origin-when-cross-origin'
        )
        expect(response.headers['content-security-policy']).toBeTruthy()
        expect(response.headers['permissions-policy']).toBeTruthy()
        expect(response.headers['x-request-id']).toBeTruthy()
        expect(response.headers['x-csp-nonce']).toBeTruthy()
      })
    })
  })

  describe('Security Headers Not Leaked', () => {
    it('does not expose Server header with sensitive info', async () => {
      const response = await client.get('/health')

      const server = response.headers['server']

      // Server header should not expose framework/version
      if (server) {
        expect(server.toLowerCase()).not.toContain('uvicorn')
        expect(server.toLowerCase()).not.toContain('python')
        expect(server.toLowerCase()).not.toContain('fastapi')
      }
    })

    it('does not expose X-Powered-By header', async () => {
      const response = await client.get('/health')

      expect(response.headers['x-powered-by']).toBeUndefined()
    })

    it('does not expose Via header', async () => {
      const response = await client.get('/health')

      expect(response.headers['via']).toBeUndefined()
    })
  })

  describe('Security Headers on Error Responses', () => {
    it('returns security headers on 404 Not Found', async () => {
      const response = await client.get('/nonexistent-endpoint')

      expect(response.status).toBe(404)
      expect(response.headers['x-frame-options']).toBe('DENY')
      expect(response.headers['x-content-type-options']).toBe('nosniff')
      expect(response.headers['content-security-policy']).toBeTruthy()
    })

    it('returns security headers on 401 Unauthorized', async () => {
      const response = await client.get('/api/v1/users/me')

      expect(response.status).toBe(401)
      expect(response.headers['x-frame-options']).toBe('DENY')
      expect(response.headers['referrer-policy']).toBe(
        'strict-origin-when-cross-origin'
      )
    })

    it('returns security headers on validation errors', async () => {
      // POST with invalid data
      const response = await client.post('/api/v1/auth/magic-link/request', {
        email: 'invalid-email' // Invalid email format
      })

      // Should be validation error (422) or other error
      expect(response.headers['x-frame-options']).toBe('DENY')
      expect(response.headers['x-content-type-options']).toBe('nosniff')
    })
  })

  describe('HIPAA Compliance Verification', () => {
    it('provides defense-in-depth security headers for PHI protection', async () => {
      const response = await client.get('/health')

      // HIPAA §164.312(a)(1) - Access Control
      expect(response.headers['x-frame-options']).toBe('DENY') // Prevent clickjacking

      // HIPAA §164.312(e)(1) - Transmission Security
      expect(response.headers['referrer-policy']).toBe(
        'strict-origin-when-cross-origin'
      ) // Prevent PHI leakage

      // HIPAA §164.308(a)(4) - Information Access Management
      const permissionsPolicy = response.headers['permissions-policy']
      expect(permissionsPolicy).toContain('microphone=()') // Prevent recording
      expect(permissionsPolicy).toContain('camera=()') // Prevent recording
      expect(permissionsPolicy).toContain('geolocation=()') // Prevent tracking

      // Defense-in-depth XSS protection (prevents PHI exfiltration)
      expect(response.headers['content-security-policy']).toBeTruthy()
      expect(response.headers['x-xss-protection']).toBe('1; mode=block')
    })

    it('verifies request traceability for audit logs', async () => {
      const response = await client.get('/health')

      // HIPAA §164.312(b) - Audit Controls
      const requestId = response.headers['x-request-id']
      expect(requestId).toBeTruthy()
      expect(requestId).toMatch(
        /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
      )

      // Request ID enables correlation of security events in audit logs
    })

    it('prevents browser-based PHI exfiltration attacks', async () => {
      const response = await client.get('/health')

      // CSP prevents XSS-based data exfiltration
      const csp = response.headers['content-security-policy']
      expect(csp).toContain("default-src 'self'")
      expect(csp).toContain("frame-ancestors 'none'")

      // Permissions-Policy prevents device API misuse
      const permissionsPolicy = response.headers['permissions-policy']
      expect(permissionsPolicy).toContain('microphone=()')
      expect(permissionsPolicy).toContain('camera=()')

      // X-Frame-Options prevents embedding in malicious iframes
      expect(response.headers['x-frame-options']).toBe('DENY')
    })
  })

  describe('Security Headers Comprehensive Report', () => {
    it('generates complete security headers report', async () => {
      const response = await client.get('/health')

      const report = {
        'X-Frame-Options': response.headers['x-frame-options'],
        'X-Content-Type-Options': response.headers['x-content-type-options'],
        'X-XSS-Protection': response.headers['x-xss-protection'],
        'Strict-Transport-Security':
          response.headers['strict-transport-security'] || 'N/A (localhost)',
        'Content-Security-Policy': response.headers['content-security-policy']
          ? 'Present'
          : 'Missing',
        'Referrer-Policy': response.headers['referrer-policy'],
        'Permissions-Policy': response.headers['permissions-policy']
          ? 'Present'
          : 'Missing',
        'X-Request-ID': response.headers['x-request-id'] ? 'Present' : 'Missing',
        'X-CSP-Nonce': response.headers['x-csp-nonce'] ? 'Present' : 'Missing'
      }

      // Log report for debugging
      console.log('Security Headers Report:', JSON.stringify(report, null, 2))

      // Verify all required headers are present
      expect(report['X-Frame-Options']).toBe('DENY')
      expect(report['X-Content-Type-Options']).toBe('nosniff')
      expect(report['X-XSS-Protection']).toBe('1; mode=block')
      expect(report['Content-Security-Policy']).toBe('Present')
      expect(report['Referrer-Policy']).toBe('strict-origin-when-cross-origin')
      expect(report['Permissions-Policy']).toBe('Present')
      expect(report['X-Request-ID']).toBe('Present')
      expect(report['X-CSP-Nonce']).toBe('Present')
    })
  })
})
