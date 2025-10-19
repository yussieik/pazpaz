/**
 * Tests for CSP utility functions
 *
 * These tests verify the nonce extraction logic works correctly in both
 * production and development environments.
 */

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import {
  getCspNonce,
  resetCspNonceCache,
  hasCspNonce,
  applyNonceToScript,
  applyNonceToStyle,
} from './csp'

describe('getCspNonce', () => {
  beforeEach(() => {
    // Reset cache before each test
    resetCspNonceCache()

    // Clean up any existing meta tags
    const existingMeta = document.querySelector('meta[name="csp-nonce"]')
    if (existingMeta) {
      existingMeta.remove()
    }
  })

  afterEach(() => {
    // Clean up meta tags after each test
    const meta = document.querySelector('meta[name="csp-nonce"]')
    if (meta) {
      meta.remove()
    }
    resetCspNonceCache()
  })

  it('should return null when no meta tag exists (development mode)', () => {
    const nonce = getCspNonce()
    expect(nonce).toBeNull()
  })

  it('should return null when meta tag exists but content is empty', () => {
    const meta = document.createElement('meta')
    meta.name = 'csp-nonce'
    meta.content = ''
    document.head.appendChild(meta)

    const nonce = getCspNonce()
    expect(nonce).toBeNull()
  })

  it('should extract nonce from meta tag when present', () => {
    const expectedNonce = 'test-nonce-12345'
    const meta = document.createElement('meta')
    meta.name = 'csp-nonce'
    meta.content = expectedNonce
    document.head.appendChild(meta)

    const nonce = getCspNonce()
    expect(nonce).toBe(expectedNonce)
  })

  it('should trim whitespace from nonce value', () => {
    const meta = document.createElement('meta')
    meta.name = 'csp-nonce'
    meta.content = '  test-nonce-whitespace  '
    document.head.appendChild(meta)

    const nonce = getCspNonce()
    expect(nonce).toBe('test-nonce-whitespace')
  })

  it('should cache nonce after first retrieval', () => {
    const expectedNonce = 'cached-nonce-12345'
    const meta = document.createElement('meta')
    meta.name = 'csp-nonce'
    meta.content = expectedNonce
    document.head.appendChild(meta)

    // First retrieval
    const nonce1 = getCspNonce()
    expect(nonce1).toBe(expectedNonce)

    // Remove meta tag to test caching
    meta.remove()

    // Second retrieval should return cached value (even though meta tag is gone)
    const nonce2 = getCspNonce()
    expect(nonce2).toBe(expectedNonce)
  })

  it('should return null on subsequent calls if nonce not found initially', () => {
    // First call - no meta tag
    const nonce1 = getCspNonce()
    expect(nonce1).toBeNull()

    // Add meta tag after first retrieval
    const meta = document.createElement('meta')
    meta.name = 'csp-nonce'
    meta.content = 'late-nonce'
    document.head.appendChild(meta)

    // Second call - should still return null (cached retrieval attempt)
    const nonce2 = getCspNonce()
    expect(nonce2).toBeNull()
  })

  it('should handle base64url encoded nonces (production format)', () => {
    // Simulate production nonce from backend (secrets.token_urlsafe(32))
    const productionNonce = 'AbC123-_XyZ789AbC123-_XyZ789AbC123-_XyZ789'
    const meta = document.createElement('meta')
    meta.name = 'csp-nonce'
    meta.content = productionNonce
    document.head.appendChild(meta)

    const nonce = getCspNonce()
    expect(nonce).toBe(productionNonce)
    expect(nonce).toMatch(/^[A-Za-z0-9_-]+$/) // Base64url format
  })
})

describe('resetCspNonceCache', () => {
  it('should clear cached nonce', () => {
    const meta = document.createElement('meta')
    meta.name = 'csp-nonce'
    meta.content = 'test-nonce'
    document.head.appendChild(meta)

    // Cache the nonce
    const nonce1 = getCspNonce()
    expect(nonce1).toBe('test-nonce')

    // Reset cache
    resetCspNonceCache()

    // Remove meta tag
    meta.remove()

    // Should return null now (cache cleared, meta tag gone)
    const nonce2 = getCspNonce()
    expect(nonce2).toBeNull()
  })

  it('should reset retrieval attempted flag', () => {
    // First retrieval with no meta tag
    const nonce1 = getCspNonce()
    expect(nonce1).toBeNull()

    // Reset cache
    resetCspNonceCache()

    // Add meta tag
    const meta = document.createElement('meta')
    meta.name = 'csp-nonce'
    meta.content = 'new-nonce'
    document.head.appendChild(meta)

    // Second retrieval should find the nonce (retrieval flag reset)
    const nonce2 = getCspNonce()
    expect(nonce2).toBe('new-nonce')

    meta.remove()
  })
})

describe('hasCspNonce', () => {
  beforeEach(() => {
    resetCspNonceCache()
    const existingMeta = document.querySelector('meta[name="csp-nonce"]')
    if (existingMeta) {
      existingMeta.remove()
    }
  })

  afterEach(() => {
    const meta = document.querySelector('meta[name="csp-nonce"]')
    if (meta) {
      meta.remove()
    }
    resetCspNonceCache()
  })

  it('should return false when no nonce is available', () => {
    expect(hasCspNonce()).toBe(false)
  })

  it('should return true when nonce is available', () => {
    const meta = document.createElement('meta')
    meta.name = 'csp-nonce'
    meta.content = 'test-nonce'
    document.head.appendChild(meta)

    expect(hasCspNonce()).toBe(true)
  })
})

describe('applyNonceToScript', () => {
  beforeEach(() => {
    resetCspNonceCache()
    const existingMeta = document.querySelector('meta[name="csp-nonce"]')
    if (existingMeta) {
      existingMeta.remove()
    }
  })

  afterEach(() => {
    const meta = document.querySelector('meta[name="csp-nonce"]')
    if (meta) {
      meta.remove()
    }
    resetCspNonceCache()
  })

  it('should apply nonce to script element when nonce is available', () => {
    const meta = document.createElement('meta')
    meta.name = 'csp-nonce'
    meta.content = 'script-nonce-123'
    document.head.appendChild(meta)

    const script = document.createElement('script')
    const result = applyNonceToScript(script)

    expect(result).toBe(script) // Should return same element for chaining
    expect(script.nonce).toBe('script-nonce-123')
  })

  it('should not apply nonce when nonce is not available', () => {
    const script = document.createElement('script')
    applyNonceToScript(script)

    // When nonce is not set, HTMLScriptElement.nonce is empty string by default
    // but our code doesn't set it, so it remains undefined
    expect(script.nonce).toBeFalsy() // Accepts both '' and undefined
  })

  it('should allow chaining for fluent API', () => {
    const meta = document.createElement('meta')
    meta.name = 'csp-nonce'
    meta.content = 'chain-nonce'
    document.head.appendChild(meta)

    const script = document.createElement('script')
    const result = applyNonceToScript(script).setAttribute('src', '/test.js')

    expect(script.nonce).toBe('chain-nonce')
    expect(script.getAttribute('src')).toBe('/test.js')
  })
})

describe('applyNonceToStyle', () => {
  beforeEach(() => {
    resetCspNonceCache()
    const existingMeta = document.querySelector('meta[name="csp-nonce"]')
    if (existingMeta) {
      existingMeta.remove()
    }
  })

  afterEach(() => {
    const meta = document.querySelector('meta[name="csp-nonce"]')
    if (meta) {
      meta.remove()
    }
    resetCspNonceCache()
  })

  it('should apply nonce to style element when nonce is available', () => {
    const meta = document.createElement('meta')
    meta.name = 'csp-nonce'
    meta.content = 'style-nonce-456'
    document.head.appendChild(meta)

    const style = document.createElement('style')
    const result = applyNonceToStyle(style)

    expect(result).toBe(style) // Should return same element for chaining
    expect(style.nonce).toBe('style-nonce-456')
  })

  it('should not apply nonce when nonce is not available', () => {
    const style = document.createElement('style')
    applyNonceToStyle(style)

    // When nonce is not set, HTMLStyleElement.nonce is empty string by default
    // but our code doesn't set it, so it remains undefined
    expect(style.nonce).toBeFalsy() // Accepts both '' and undefined
  })

  it('should allow chaining for fluent API', () => {
    const meta = document.createElement('meta')
    meta.name = 'csp-nonce'
    meta.content = 'chain-style-nonce'
    document.head.appendChild(meta)

    const style = document.createElement('style')
    applyNonceToStyle(style)
    style.textContent = '.test { color: red; }'

    expect(style.nonce).toBe('chain-style-nonce')
    expect(style.textContent).toBe('.test { color: red; }')
  })
})

describe('CSP Integration Scenarios', () => {
  beforeEach(() => {
    resetCspNonceCache()
    const existingMeta = document.querySelector('meta[name="csp-nonce"]')
    if (existingMeta) {
      existingMeta.remove()
    }
  })

  afterEach(() => {
    const meta = document.querySelector('meta[name="csp-nonce"]')
    if (meta) {
      meta.remove()
    }
    resetCspNonceCache()
  })

  it('should handle production scenario (nonce present)', () => {
    // Simulate production: backend injects nonce
    const productionNonce = 'AbC123-_XyZ789AbC123-_XyZ789AbC123-_'
    const meta = document.createElement('meta')
    meta.name = 'csp-nonce'
    meta.content = productionNonce
    document.head.appendChild(meta)

    // Frontend extracts nonce
    expect(hasCspNonce()).toBe(true)
    expect(getCspNonce()).toBe(productionNonce)

    // Frontend applies nonce to dynamic script
    const script = document.createElement('script')
    applyNonceToScript(script)
    expect(script.nonce).toBe(productionNonce)
  })

  it('should handle development scenario (no nonce)', () => {
    // Simulate development: no backend, no nonce
    expect(hasCspNonce()).toBe(false)
    expect(getCspNonce()).toBeNull()

    // Frontend still works (CSP allows unsafe-inline in dev)
    const script = document.createElement('script')
    applyNonceToScript(script)
    expect(script.nonce).toBeFalsy() // No nonce applied (undefined or '')
  })

  it('should handle SSR scenario (meta tag injected server-side)', () => {
    // Simulate SSR: meta tag present on initial page load
    const ssrNonce = 'ssr-nonce-server-generated'
    const meta = document.createElement('meta')
    meta.name = 'csp-nonce'
    meta.content = ssrNonce
    document.head.appendChild(meta)

    // Client-side hydration extracts nonce
    const nonce = getCspNonce()
    expect(nonce).toBe(ssrNonce)

    // Subsequent dynamic injections use same nonce
    const script1 = document.createElement('script')
    const script2 = document.createElement('script')
    applyNonceToScript(script1)
    applyNonceToScript(script2)

    expect(script1.nonce).toBe(ssrNonce)
    expect(script2.nonce).toBe(ssrNonce)
  })
})
