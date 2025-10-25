/**
 * Content Security Policy (CSP) Utility Functions
 *
 * This module provides utilities for working with CSP nonces in the frontend.
 *
 * ## Overview
 *
 * The backend generates a cryptographically secure nonce (256-bit entropy) for each request
 * and includes it in:
 * 1. `Content-Security-Policy` header: `script-src 'self' 'nonce-{NONCE}'`
 * 2. `X-CSP-Nonce` response header: Contains the nonce value for frontend access
 * 3. Meta tag in HTML: `<meta name="csp-nonce" content="{NONCE}">` (production only)
 *
 * ## Production vs Development
 *
 * **Production:**
 * - Strict CSP: Only scripts/styles with matching nonce attribute execute
 * - NO `unsafe-inline`, NO `unsafe-eval`
 * - Nonce injected into HTML meta tag by backend
 *
 * **Development:**
 * - Permissive CSP: Allows `unsafe-inline` and `unsafe-eval` for Vite HMR
 * - Nonce still generated but not required for script execution
 * - Vite dev server uses eval() for hot module replacement
 *
 * ## Usage
 *
 * ```typescript
 * import { getCspNonce } from '@/utils/csp'
 *
 * // Get nonce for dynamic script injection
 * const nonce = getCspNonce()
 * if (nonce) {
 *   const script = document.createElement('script')
 *   script.nonce = nonce
 *   script.src = '/some-script.js'
 *   document.head.appendChild(script)
 * }
 * ```
 *
 * ## When to Use Nonce
 *
 * Use nonce when:
 * - Dynamically creating `<script>` or `<style>` elements
 * - Injecting inline scripts or styles programmatically
 * - Using third-party libraries that inject scripts
 *
 * DO NOT use nonce for:
 * - Static scripts in index.html (backend handles this)
 * - Vue component templates (Vite bundles these)
 * - CSS imports (handled by Vite)
 *
 * @module utils/csp
 */

/**
 * Cached nonce value to avoid repeated DOM queries.
 * Nonce is immutable per page load, so we can safely cache it.
 */
let cachedNonce: string | null = null

/**
 * Indicates if we've already attempted to retrieve the nonce.
 * This prevents repeated failed lookups in development mode.
 */
let nonceRetrievalAttempted = false

/**
 * Get the CSP nonce for the current page.
 *
 * This function extracts the nonce from the `<meta name="csp-nonce">` tag
 * injected by the backend in production mode.
 *
 * **Extraction Strategy:**
 * 1. Return cached nonce if already retrieved
 * 2. Look for `<meta name="csp-nonce" content="{NONCE}">` in document head
 * 3. Return `null` if not found (development mode or SSR not yet rendered)
 *
 * **Caching:**
 * The nonce is cached after first retrieval for performance.
 * The nonce is immutable per page load, so caching is safe.
 *
 * **Development vs Production:**
 * - **Production:** Nonce is present in meta tag and required for inline scripts
 * - **Development:** Nonce may be absent (CSP allows unsafe-inline), returns `null`
 *
 * @returns The CSP nonce string, or `null` if not available
 *
 * @example
 * ```typescript
 * const nonce = getCspNonce()
 * if (nonce) {
 *   console.debug('Nonce available:', nonce)
 *   // Use nonce for dynamic script injection
 * } else {
 *   console.debug('No nonce (development mode or CSP disabled)')
 * }
 * ```
 */
export function getCspNonce(): string | null {
  // Return cached nonce if already retrieved
  if (cachedNonce !== null) {
    return cachedNonce
  }

  // If we've already attempted retrieval and found nothing, return null
  // This avoids repeated DOM queries in development mode
  if (nonceRetrievalAttempted) {
    return null
  }

  // Mark that we've attempted retrieval
  nonceRetrievalAttempted = true

  // Try to get nonce from meta tag (SSR/production)
  // Backend injects: <meta name="csp-nonce" content="{NONCE}">
  const metaTag = document.querySelector('meta[name="csp-nonce"]')
  if (metaTag) {
    const nonce = metaTag.getAttribute('content')
    if (nonce && nonce.trim() !== '') {
      cachedNonce = nonce.trim()
      return cachedNonce
    }
  }

  // Nonce not found - this is expected in development mode
  // Development CSP allows 'unsafe-inline', so nonce is optional
  return null
}

/**
 * Reset the cached nonce (for testing purposes only).
 *
 * This function is NOT exported and should only be used in tests.
 * In production, the nonce is immutable per page load.
 *
 * @internal
 */
export function resetCspNonceCache(): void {
  cachedNonce = null
  nonceRetrievalAttempted = false
}

/**
 * Check if CSP nonce is available.
 *
 * Convenience function to check if a nonce is available without
 * retrieving the actual value.
 *
 * @returns `true` if nonce is available, `false` otherwise
 *
 * @example
 * ```typescript
 * if (hasCspNonce()) {
 *   console.debug('Running in production with strict CSP')
 * } else {
 *   console.debug('Running in development mode')
 * }
 * ```
 */
export function hasCspNonce(): boolean {
  return getCspNonce() !== null
}

/**
 * Apply CSP nonce to a script element.
 *
 * Helper function to safely apply nonce to a script element if available.
 * This handles the common pattern of:
 * 1. Get nonce
 * 2. Apply to script element if present
 *
 * @param script - The script element to apply nonce to
 * @returns The modified script element (for chaining)
 *
 * @example
 * ```typescript
 * const script = document.createElement('script')
 * script.src = 'https://example.com/library.js'
 * applyNonceToScript(script)
 * document.head.appendChild(script)
 * ```
 */
export function applyNonceToScript(script: HTMLScriptElement): HTMLScriptElement {
  const nonce = getCspNonce()
  if (nonce) {
    script.nonce = nonce
  }
  return script
}

/**
 * Apply CSP nonce to a style element.
 *
 * Helper function to safely apply nonce to a style element if available.
 *
 * @param style - The style element to apply nonce to
 * @returns The modified style element (for chaining)
 *
 * @example
 * ```typescript
 * const style = document.createElement('style')
 * style.textContent = '.my-class { color: red; }'
 * applyNonceToStyle(style)
 * document.head.appendChild(style)
 * ```
 */
export function applyNonceToStyle(style: HTMLStyleElement): HTMLStyleElement {
  const nonce = getCspNonce()
  if (nonce) {
    style.nonce = nonce
  }
  return style
}
