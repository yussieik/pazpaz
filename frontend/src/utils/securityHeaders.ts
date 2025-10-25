/**
 * Security Headers Verification Utility
 *
 * HIPAA Compliance: §164.312(a)(1) - Technical safeguards verification
 *
 * This utility provides functions to verify that security headers are properly
 * configured and present in HTTP responses.
 */

export interface SecurityHeadersConfig {
  'x-frame-options': string
  'x-content-type-options': string
  'strict-transport-security': string
  'content-security-policy': string
  'referrer-policy': string
  'permissions-policy': string
  'x-xss-protection': string
  'x-request-id': string
  'x-csp-nonce': string
}

/**
 * Required security headers and their expected minimum values
 *
 * Note: Some headers (like HSTS) may be omitted on localhost in development
 */
export const REQUIRED_SECURITY_HEADERS: Partial<SecurityHeadersConfig> = {
  'x-frame-options': 'DENY',
  'x-content-type-options': 'nosniff',
  'x-xss-protection': '1; mode=block',
  'content-security-policy': "default-src 'self'", // Minimum requirement
  'referrer-policy': 'strict-origin-when-cross-origin',
  'permissions-policy': 'geolocation=(), camera=(), microphone=()',
}

/**
 * Optional headers that should be present but may vary by environment
 */
export const OPTIONAL_SECURITY_HEADERS = [
  'strict-transport-security', // Omitted on localhost
  'x-request-id', // Present but value is dynamic
  'x-csp-nonce', // Present but value is dynamic
]

export interface SecurityHeadersVerification {
  valid: boolean
  missing: string[]
  invalid: Array<{
    header: string
    expected: string
    actual: string
  }>
  warnings: Array<{
    header: string
    message: string
  }>
}

/**
 * Verify that security headers are present and correctly configured
 *
 * @param headers - HTTP response headers object
 * @param options - Verification options
 * @returns Verification result with any issues found
 */
export function verifySecurityHeaders(
  headers: Record<string, string>,
  options?: {
    strict?: boolean // If true, require all headers including optional ones
    environment?: 'local' | 'staging' | 'production'
  }
): SecurityHeadersVerification {
  const missing: string[] = []
  const invalid: Array<{ header: string; expected: string; actual: string }> = []
  const warnings: Array<{ header: string; message: string }> = []

  // Normalize headers to lowercase for case-insensitive comparison
  const normalizedHeaders: Record<string, string> = {}
  for (const [key, value] of Object.entries(headers)) {
    normalizedHeaders[key.toLowerCase()] = value
  }

  // Check required headers
  for (const [header, expectedValue] of Object.entries(REQUIRED_SECURITY_HEADERS)) {
    const actualValue = normalizedHeaders[header]

    if (!actualValue) {
      missing.push(header)
    } else if (!actualValue.includes(expectedValue)) {
      invalid.push({
        header,
        expected: expectedValue,
        actual: actualValue,
      })
    }
  }

  // Check optional headers
  for (const header of OPTIONAL_SECURITY_HEADERS) {
    const actualValue = normalizedHeaders[header]

    if (!actualValue) {
      if (header === 'strict-transport-security' && options?.environment === 'local') {
        // HSTS is expected to be omitted on localhost
        warnings.push({
          header,
          message: 'HSTS omitted on localhost (expected in development)',
        })
      } else if (options?.strict) {
        missing.push(header)
      } else {
        warnings.push({
          header,
          message: 'Optional header not present',
        })
      }
    } else {
      // Validate specific optional headers
      if (header === 'x-request-id') {
        // Should be a UUID format
        const uuidRegex =
          /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
        if (!uuidRegex.test(actualValue)) {
          warnings.push({
            header,
            message: `Invalid UUID format: ${actualValue}`,
          })
        }
      }

      if (header === 'strict-transport-security') {
        // Should have max-age >= 1 year
        const match = actualValue.match(/max-age=(\d+)/)
        if (match && match[1]) {
          const maxAge = parseInt(match[1], 10)
          if (maxAge < 31536000) {
            warnings.push({
              header,
              message: `HSTS max-age too short: ${maxAge} < 31536000 (1 year)`,
            })
          }
        }
      }
    }
  }

  return {
    valid: missing.length === 0 && invalid.length === 0,
    missing,
    invalid,
    warnings,
  }
}

/**
 * Format security headers verification result as human-readable report
 *
 * @param verification - Verification result from verifySecurityHeaders()
 * @returns Formatted report string
 */
export function formatSecurityHeadersReport(
  verification: SecurityHeadersVerification
): string {
  if (verification.valid && verification.warnings.length === 0) {
    return '✓ All security headers present and valid'
  }

  const lines: string[] = []

  if (verification.valid && verification.warnings.length > 0) {
    lines.push('✓ All required security headers present and valid')
  } else {
    lines.push('✗ Security headers verification failed:')
  }

  if (verification.missing.length > 0) {
    lines.push('\nMissing headers:')
    verification.missing.forEach((header) => {
      lines.push(`  - ${header}`)
    })
  }

  if (verification.invalid.length > 0) {
    lines.push('\nInvalid headers:')
    verification.invalid.forEach(({ header, expected, actual }) => {
      lines.push(`  - ${header}`)
      lines.push(`    Expected: ${expected}`)
      lines.push(`    Actual: ${actual}`)
    })
  }

  if (verification.warnings.length > 0) {
    lines.push('\nWarnings:')
    verification.warnings.forEach(({ header, message }) => {
      lines.push(`  - ${header}: ${message}`)
    })
  }

  return lines.join('\n')
}

/**
 * Verify CSP (Content-Security-Policy) header specifically
 *
 * @param csp - CSP header value
 * @returns Validation result with any issues found
 */
export function verifyCSP(csp: string): {
  valid: boolean
  issues: string[]
} {
  const issues: string[] = []

  // Required directives
  const requiredDirectives = [
    "default-src 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ]

  for (const directive of requiredDirectives) {
    if (!csp.includes(directive)) {
      issues.push(`Missing required CSP directive: ${directive}`)
    }
  }

  // Dangerous directives (should not be in production)
  const dangerousDirectives = ["'unsafe-inline'", "'unsafe-eval'"]

  for (const directive of dangerousDirectives) {
    if (csp.includes(directive)) {
      issues.push(
        `CSP contains dangerous directive: ${directive} (acceptable in development only)`
      )
    }
  }

  return {
    valid: issues.length === 0,
    issues,
  }
}

/**
 * Verify Permissions-Policy header specifically
 *
 * @param policy - Permissions-Policy header value
 * @returns Validation result with any issues found
 */
export function verifyPermissionsPolicy(policy: string): {
  valid: boolean
  issues: string[]
} {
  const issues: string[] = []

  // Features that should be disabled for HIPAA compliance
  const requiredDisabledFeatures = [
    'geolocation', // Privacy - no location tracking
    'microphone', // PHI - no audio recording
    'camera', // PHI - no video recording
    'payment', // Not needed
    'usb', // Security - no USB access
  ]

  for (const feature of requiredDisabledFeatures) {
    if (!policy.includes(`${feature}=()`)) {
      issues.push(`Permissions-Policy should disable: ${feature}`)
    }
  }

  return {
    valid: issues.length === 0,
    issues,
  }
}

/**
 * Create a security headers report for all headers in a response
 *
 * @param headers - HTTP response headers
 * @returns Comprehensive security headers report
 */
export function createSecurityHeadersReport(headers: Record<string, string>): {
  summary: string
  details: {
    header: string
    value: string
    status: 'present' | 'missing' | 'invalid'
    notes?: string
  }[]
} {
  const verification = verifySecurityHeaders(headers)
  const summary = formatSecurityHeadersReport(verification)

  // Normalize headers
  const normalizedHeaders: Record<string, string> = {}
  for (const [key, value] of Object.entries(headers)) {
    normalizedHeaders[key.toLowerCase()] = value
  }

  const details = [
    ...Object.keys(REQUIRED_SECURITY_HEADERS),
    ...OPTIONAL_SECURITY_HEADERS,
  ].map((header) => {
    const value = normalizedHeaders[header]
    let status: 'present' | 'missing' | 'invalid' = 'present'
    let notes: string | undefined

    if (!value) {
      status = 'missing'
    } else {
      // Check if value is valid
      const invalidEntry = verification.invalid.find((i) => i.header === header)
      if (invalidEntry) {
        status = 'invalid'
        notes = `Expected: ${invalidEntry.expected}`
      }

      // Check for warnings
      const warning = verification.warnings.find((w) => w.header === header)
      if (warning) {
        notes = warning.message
      }
    }

    return {
      header,
      value: value || 'N/A',
      status,
      notes,
    }
  })

  return {
    summary,
    details,
  }
}
