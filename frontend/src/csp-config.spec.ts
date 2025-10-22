import { describe, it, expect } from 'vitest'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

/**
 * CSP Configuration Tests
 * ========================
 * Validates that index.html contains proper Content Security Policy meta tags
 * for HIPAA §164.312 compliance (XSS protection).
 *
 * These tests ensure:
 * 1. CSP meta tag exists as fallback if HTTP headers are stripped
 * 2. Required security directives are present
 * 3. Third-party resources (Google Fonts) are allowed
 * 4. Environment-specific placeholders exist for Vite transformation
 */
describe('CSP Configuration', () => {
  // Get path to index.html (one level up from src/)
  const __dirname = path.dirname(fileURLToPath(import.meta.url))
  const indexPath = path.resolve(__dirname, '../index.html')
  let indexHtml: string

  // Read index.html once for all tests
  try {
    indexHtml = fs.readFileSync(indexPath, 'utf-8')
  } catch (error) {
    throw new Error(`Failed to read index.html at ${indexPath}: ${error}`)
  }

  it('should contain CSP meta tag with http-equiv attribute', () => {
    expect(indexHtml).toContain('http-equiv="Content-Security-Policy"')
  })

  it('should include required security directives', () => {
    const requiredDirectives = [
      "default-src 'self'", // Only load resources from same origin
      "script-src 'self'", // Only execute scripts from same origin
      "frame-ancestors 'none'", // Prevent clickjacking (no iframe embedding)
      "base-uri 'self'", // Prevent base tag injection attacks
      "form-action 'self'", // Forms can only submit to same origin
      'upgrade-insecure-requests', // Auto-upgrade HTTP to HTTPS
    ]

    requiredDirectives.forEach((directive) => {
      expect(indexHtml).toContain(directive)
    })
  })

  it('should allow necessary third-party resources', () => {
    // Google Fonts should be explicitly allowed
    expect(indexHtml).toContain('fonts.googleapis.com')
    expect(indexHtml).toContain('fonts.gstatic.com')
  })

  it('should allow data URIs and blob URLs for images', () => {
    // Allow data: URIs for inline images (e.g., base64 encoded)
    // Allow blob: URLs for client-side generated images
    expect(indexHtml).toContain('img-src')
    expect(indexHtml).toMatch(/img-src[^;]*data:/)
    expect(indexHtml).toMatch(/img-src[^;]*blob:/)
  })

  it('should contain Vite placeholder for environment-specific script-src', () => {
    // %VITE_CSP_SCRIPT_SRC% is replaced at build time:
    // - Development: 'unsafe-eval' (for Vite HMR)
    // - Production: '' (strict CSP, no eval)
    expect(indexHtml).toContain('%VITE_CSP_SCRIPT_SRC%')
  })

  it('should contain Vite placeholder for API URL in connect-src', () => {
    // %VITE_API_URL% is replaced at build time:
    // - Development: http://localhost:8000
    // - Production: https://api.pazpaz.com
    expect(indexHtml).toContain('%VITE_API_URL%')
  })

  it('should allow unsafe-inline for scripts and styles (development compatibility)', () => {
    // Vue 3 SFC and Vite HMR require 'unsafe-inline'
    // In production, nonce-based CSP from backend provides stricter security
    expect(indexHtml).toMatch(/script-src[^;]*'unsafe-inline'/)
    expect(indexHtml).toMatch(/style-src[^;]*'unsafe-inline'/)
  })

  it('should allow WebSocket connections for development HMR', () => {
    // Development needs ws://localhost:* for Vite HMR
    expect(indexHtml).toContain('ws://localhost:*')
  })

  it('should not contain dangerous CSP bypass patterns', () => {
    // Should NOT allow 'unsafe-eval' by default (only via placeholder)
    // Should NOT allow wildcard origins like * or https://*
    const dangerousPatterns = [
      'default-src *', // Wildcard allows any origin
      'script-src *', // Wildcard allows any script
      'script-src https:', // Too permissive (allows any HTTPS script)
    ]

    dangerousPatterns.forEach((pattern) => {
      // Check that dangerous patterns don't appear in the static CSP
      // (except as part of valid directives like 'img-src ... https:')
      if (!pattern.includes('img-src')) {
        const escapedPattern = pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
        const regex = new RegExp(escapedPattern, 'i')
        expect(indexHtml).not.toMatch(regex)
      }
    })
  })

  it('should have CSP meta tag before title tag', () => {
    // CSP should be applied early in the HTML parsing
    const cspIndex = indexHtml.indexOf('http-equiv="Content-Security-Policy"')
    const titleIndex = indexHtml.indexOf('<title>')

    expect(cspIndex).toBeGreaterThan(0) // CSP exists
    expect(titleIndex).toBeGreaterThan(0) // Title exists
    expect(cspIndex).toBeLessThan(titleIndex) // CSP comes before title
  })

  it('should include documentation comment explaining CSP purpose', () => {
    // Should have clear documentation for developers
    expect(indexHtml).toContain('Content Security Policy')
    expect(indexHtml).toContain('HIPAA §164.312')
  })
})
