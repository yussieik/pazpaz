/**
 * Unit tests for security headers verification utility
 */

import { describe, it, expect } from 'vitest'
import {
  verifySecurityHeaders,
  formatSecurityHeadersReport,
  verifyCSP,
  verifyPermissionsPolicy,
  createSecurityHeadersReport,
  REQUIRED_SECURITY_HEADERS
} from './securityHeaders'

describe('securityHeaders utility', () => {
  describe('verifySecurityHeaders', () => {
    it('returns valid when all required headers present and correct', () => {
      const headers = {
        'x-frame-options': 'DENY',
        'x-content-type-options': 'nosniff',
        'x-xss-protection': '1; mode=block',
        'content-security-policy': "default-src 'self'; script-src 'self'",
        'referrer-policy': 'strict-origin-when-cross-origin',
        'permissions-policy': 'geolocation=(), camera=(), microphone=()'
      }

      const result = verifySecurityHeaders(headers)

      expect(result.valid).toBe(true)
      expect(result.missing).toHaveLength(0)
      expect(result.invalid).toHaveLength(0)
    })

    it('detects missing required headers', () => {
      const headers = {
        'x-frame-options': 'DENY'
        // Missing other required headers
      }

      const result = verifySecurityHeaders(headers)

      expect(result.valid).toBe(false)
      expect(result.missing).toContain('x-content-type-options')
      expect(result.missing).toContain('x-xss-protection')
      expect(result.missing).toContain('content-security-policy')
    })

    it('detects invalid header values', () => {
      const headers = {
        'x-frame-options': 'SAMEORIGIN', // Should be DENY
        'x-content-type-options': 'nosniff',
        'x-xss-protection': '1; mode=block',
        'content-security-policy': "default-src 'self'",
        'referrer-policy': 'strict-origin-when-cross-origin',
        'permissions-policy': 'geolocation=(), camera=(), microphone=()'
      }

      const result = verifySecurityHeaders(headers)

      expect(result.valid).toBe(false)
      expect(result.invalid).toHaveLength(1)
      expect(result.invalid[0].header).toBe('x-frame-options')
      expect(result.invalid[0].expected).toBe('DENY')
      expect(result.invalid[0].actual).toBe('SAMEORIGIN')
    })

    it('handles case-insensitive header names', () => {
      const headers = {
        'X-Frame-Options': 'DENY',
        'X-Content-Type-Options': 'nosniff',
        'X-XSS-Protection': '1; mode=block',
        'Content-Security-Policy': "default-src 'self'",
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'geolocation=(), camera=(), microphone=()'
      }

      const result = verifySecurityHeaders(headers)

      expect(result.valid).toBe(true)
    })

    it('allows partial matches for header values', () => {
      const headers = {
        'x-frame-options': 'DENY',
        'x-content-type-options': 'nosniff',
        'x-xss-protection': '1; mode=block',
        'content-security-policy':
          "default-src 'self'; script-src 'self' 'nonce-abc123'", // More than minimum
        'referrer-policy': 'strict-origin-when-cross-origin',
        'permissions-policy':
          'geolocation=(), camera=(), microphone=(), payment=()' // More features disabled
      }

      const result = verifySecurityHeaders(headers)

      expect(result.valid).toBe(true)
    })

    it('generates warnings for optional headers in non-strict mode', () => {
      const headers = {
        'x-frame-options': 'DENY',
        'x-content-type-options': 'nosniff',
        'x-xss-protection': '1; mode=block',
        'content-security-policy': "default-src 'self'",
        'referrer-policy': 'strict-origin-when-cross-origin',
        'permissions-policy': 'geolocation=(), camera=(), microphone=()'
        // Missing optional headers: strict-transport-security, x-request-id, x-csp-nonce
      }

      const result = verifySecurityHeaders(headers)

      expect(result.valid).toBe(true) // Still valid in non-strict mode
      expect(result.warnings.length).toBeGreaterThan(0)
    })

    it('requires optional headers in strict mode', () => {
      const headers = {
        'x-frame-options': 'DENY',
        'x-content-type-options': 'nosniff',
        'x-xss-protection': '1; mode=block',
        'content-security-policy': "default-src 'self'",
        'referrer-policy': 'strict-origin-when-cross-origin',
        'permissions-policy': 'geolocation=(), camera=(), microphone=()'
        // Missing optional headers
      }

      const result = verifySecurityHeaders(headers, { strict: true })

      expect(result.valid).toBe(false)
      expect(result.missing.length).toBeGreaterThan(0)
    })

    it('allows HSTS to be missing on localhost', () => {
      const headers = {
        'x-frame-options': 'DENY',
        'x-content-type-options': 'nosniff',
        'x-xss-protection': '1; mode=block',
        'content-security-policy': "default-src 'self'",
        'referrer-policy': 'strict-origin-when-cross-origin',
        'permissions-policy': 'geolocation=(), camera=(), microphone=()'
        // Missing HSTS
      }

      const result = verifySecurityHeaders(headers, { environment: 'local' })

      expect(result.valid).toBe(true)
      const hstsWarning = result.warnings.find(
        (w) => w.header === 'strict-transport-security'
      )
      expect(hstsWarning).toBeDefined()
      expect(hstsWarning?.message).toContain('localhost')
    })

    it('validates HSTS max-age is at least 1 year', () => {
      const headers = {
        'x-frame-options': 'DENY',
        'x-content-type-options': 'nosniff',
        'x-xss-protection': '1; mode=block',
        'content-security-policy': "default-src 'self'",
        'referrer-policy': 'strict-origin-when-cross-origin',
        'permissions-policy': 'geolocation=(), camera=(), microphone=()',
        'strict-transport-security': 'max-age=86400' // Only 1 day
      }

      const result = verifySecurityHeaders(headers)

      expect(result.valid).toBe(true) // Still valid
      const hstsWarning = result.warnings.find(
        (w) => w.header === 'strict-transport-security'
      )
      expect(hstsWarning).toBeDefined()
      expect(hstsWarning?.message).toContain('too short')
    })

    it('validates X-Request-ID is a UUID', () => {
      const headers = {
        'x-frame-options': 'DENY',
        'x-content-type-options': 'nosniff',
        'x-xss-protection': '1; mode=block',
        'content-security-policy': "default-src 'self'",
        'referrer-policy': 'strict-origin-when-cross-origin',
        'permissions-policy': 'geolocation=(), camera=(), microphone=()',
        'x-request-id': 'invalid-uuid'
      }

      const result = verifySecurityHeaders(headers)

      expect(result.valid).toBe(true) // Still valid
      const requestIdWarning = result.warnings.find((w) => w.header === 'x-request-id')
      expect(requestIdWarning).toBeDefined()
      expect(requestIdWarning?.message).toContain('Invalid UUID')
    })

    it('accepts valid UUID for X-Request-ID', () => {
      const headers = {
        'x-frame-options': 'DENY',
        'x-content-type-options': 'nosniff',
        'x-xss-protection': '1; mode=block',
        'content-security-policy': "default-src 'self'",
        'referrer-policy': 'strict-origin-when-cross-origin',
        'permissions-policy': 'geolocation=(), camera=(), microphone=()',
        'x-request-id': '123e4567-e89b-12d3-a456-426614174000'
      }

      const result = verifySecurityHeaders(headers)

      expect(result.valid).toBe(true)
      const requestIdWarning = result.warnings.find((w) => w.header === 'x-request-id')
      expect(requestIdWarning).toBeUndefined()
    })
  })

  describe('formatSecurityHeadersReport', () => {
    it('formats valid report with no issues', () => {
      const verification = {
        valid: true,
        missing: [],
        invalid: [],
        warnings: []
      }

      const report = formatSecurityHeadersReport(verification)

      expect(report).toContain('✓')
      expect(report).toContain('valid')
    })

    it('formats report with missing headers', () => {
      const verification = {
        valid: false,
        missing: ['x-frame-options', 'x-content-type-options'],
        invalid: [],
        warnings: []
      }

      const report = formatSecurityHeadersReport(verification)

      expect(report).toContain('✗')
      expect(report).toContain('Missing headers')
      expect(report).toContain('x-frame-options')
      expect(report).toContain('x-content-type-options')
    })

    it('formats report with invalid headers', () => {
      const verification = {
        valid: false,
        missing: [],
        invalid: [
          {
            header: 'x-frame-options',
            expected: 'DENY',
            actual: 'SAMEORIGIN'
          }
        ],
        warnings: []
      }

      const report = formatSecurityHeadersReport(verification)

      expect(report).toContain('✗')
      expect(report).toContain('Invalid headers')
      expect(report).toContain('x-frame-options')
      expect(report).toContain('Expected: DENY')
      expect(report).toContain('Actual: SAMEORIGIN')
    })

    it('formats report with warnings', () => {
      const verification = {
        valid: true,
        missing: [],
        invalid: [],
        warnings: [
          {
            header: 'strict-transport-security',
            message: 'HSTS omitted on localhost'
          }
        ]
      }

      const report = formatSecurityHeadersReport(verification)

      expect(report).toContain('✓')
      expect(report).toContain('Warnings')
      expect(report).toContain('strict-transport-security')
      expect(report).toContain('localhost')
    })

    it('formats comprehensive report with all issue types', () => {
      const verification = {
        valid: false,
        missing: ['x-request-id'],
        invalid: [
          {
            header: 'x-frame-options',
            expected: 'DENY',
            actual: 'SAMEORIGIN'
          }
        ],
        warnings: [
          {
            header: 'strict-transport-security',
            message: 'max-age too short'
          }
        ]
      }

      const report = formatSecurityHeadersReport(verification)

      expect(report).toContain('Missing headers')
      expect(report).toContain('Invalid headers')
      expect(report).toContain('Warnings')
    })
  })

  describe('verifyCSP', () => {
    it('validates CSP with all required directives', () => {
      const csp =
        "default-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"

      const result = verifyCSP(csp)

      expect(result.valid).toBe(true)
      expect(result.issues).toHaveLength(0)
    })

    it('detects missing required directives', () => {
      const csp = "default-src 'self'; script-src 'self'"

      const result = verifyCSP(csp)

      expect(result.valid).toBe(false)
      expect(result.issues.length).toBeGreaterThan(0)
      expect(result.issues.some((i) => i.includes('frame-ancestors'))).toBe(true)
    })

    it('flags dangerous directives', () => {
      const csp =
        "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"

      const result = verifyCSP(csp)

      expect(result.valid).toBe(false)
      expect(result.issues.some((i) => i.includes('unsafe-inline'))).toBe(true)
      expect(result.issues.some((i) => i.includes('unsafe-eval'))).toBe(true)
    })

    it('accepts development CSP with unsafe directives', () => {
      const csp =
        "default-src 'self'; script-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"

      const result = verifyCSP(csp)

      // Issues are flagged, but caller can decide if acceptable in dev
      expect(result.issues.some((i) => i.includes('development only'))).toBe(true)
    })
  })

  describe('verifyPermissionsPolicy', () => {
    it('validates Permissions-Policy with all required disabled features', () => {
      const policy = 'geolocation=(), microphone=(), camera=(), payment=(), usb=()'

      const result = verifyPermissionsPolicy(policy)

      expect(result.valid).toBe(true)
      expect(result.issues).toHaveLength(0)
    })

    it('detects missing feature restrictions', () => {
      const policy = 'geolocation=(), camera=()'

      const result = verifyPermissionsPolicy(policy)

      expect(result.valid).toBe(false)
      expect(result.issues.some((i) => i.includes('microphone'))).toBe(true)
      expect(result.issues.some((i) => i.includes('payment'))).toBe(true)
      expect(result.issues.some((i) => i.includes('usb'))).toBe(true)
    })

    it('accepts policies with additional disabled features', () => {
      const policy =
        'geolocation=(), microphone=(), camera=(), payment=(), usb=(), fullscreen=()'

      const result = verifyPermissionsPolicy(policy)

      expect(result.valid).toBe(true)
    })
  })

  describe('createSecurityHeadersReport', () => {
    it('creates comprehensive report for all headers', () => {
      const headers = {
        'x-frame-options': 'DENY',
        'x-content-type-options': 'nosniff',
        'x-xss-protection': '1; mode=block',
        'content-security-policy': "default-src 'self'",
        'referrer-policy': 'strict-origin-when-cross-origin',
        'permissions-policy': 'geolocation=(), camera=(), microphone=()',
        'strict-transport-security': 'max-age=31536000; includeSubDomains',
        'x-request-id': '123e4567-e89b-12d3-a456-426614174000',
        'x-csp-nonce': 'abc123'
      }

      const report = createSecurityHeadersReport(headers)

      expect(report.summary).toContain('✓')
      expect(report.details.length).toBeGreaterThan(0)

      // All headers should be present
      for (const detail of report.details) {
        expect(detail.status).toBe('present')
      }
    })

    it('reports missing headers', () => {
      const headers = {
        'x-frame-options': 'DENY'
      }

      const report = createSecurityHeadersReport(headers)

      const missingHeaders = report.details.filter((d) => d.status === 'missing')
      expect(missingHeaders.length).toBeGreaterThan(0)
    })

    it('reports invalid headers', () => {
      const headers = {
        'x-frame-options': 'SAMEORIGIN', // Invalid
        'x-content-type-options': 'nosniff',
        'x-xss-protection': '1; mode=block',
        'content-security-policy': "default-src 'self'",
        'referrer-policy': 'strict-origin-when-cross-origin',
        'permissions-policy': 'geolocation=(), camera=(), microphone=()'
      }

      const report = createSecurityHeadersReport(headers)

      const invalidHeader = report.details.find(
        (d) => d.header === 'x-frame-options' && d.status === 'invalid'
      )
      expect(invalidHeader).toBeDefined()
      expect(invalidHeader?.notes).toContain('Expected: DENY')
    })

    it('includes warnings in report notes', () => {
      const headers = {
        'x-frame-options': 'DENY',
        'x-content-type-options': 'nosniff',
        'x-xss-protection': '1; mode=block',
        'content-security-policy': "default-src 'self'",
        'referrer-policy': 'strict-origin-when-cross-origin',
        'permissions-policy': 'geolocation=(), camera=(), microphone=()',
        'strict-transport-security': 'max-age=86400' // Too short
      }

      const report = createSecurityHeadersReport(headers)

      const hstsDetail = report.details.find(
        (d) => d.header === 'strict-transport-security'
      )
      expect(hstsDetail?.notes).toBeDefined()
      expect(hstsDetail?.notes).toContain('too short')
    })
  })

  describe('REQUIRED_SECURITY_HEADERS constant', () => {
    it('defines all critical headers', () => {
      expect(REQUIRED_SECURITY_HEADERS['x-frame-options']).toBe('DENY')
      expect(REQUIRED_SECURITY_HEADERS['x-content-type-options']).toBe('nosniff')
      expect(REQUIRED_SECURITY_HEADERS['x-xss-protection']).toBe('1; mode=block')
      expect(REQUIRED_SECURITY_HEADERS['content-security-policy']).toBeDefined()
      expect(REQUIRED_SECURITY_HEADERS['referrer-policy']).toBe(
        'strict-origin-when-cross-origin'
      )
      expect(REQUIRED_SECURITY_HEADERS['permissions-policy']).toBeDefined()
    })
  })
})
