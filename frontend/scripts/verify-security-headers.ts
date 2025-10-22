#!/usr/bin/env tsx
/**
 * Security Headers Verification Script for CI/CD
 *
 * HIPAA Compliance: §164.312(a)(1) - Technical safeguards verification
 *
 * This script verifies that all required security headers are present
 * and correctly configured in API responses. Designed to run in CI/CD
 * pipelines to catch misconfigurations before deployment.
 *
 * Usage:
 *   npm run verify:security-headers
 *   VITE_API_URL=https://staging.api.pazpaz.com npm run verify:security-headers
 */

import axios from 'axios'
import {
  verifySecurityHeaders,
  formatSecurityHeadersReport,
  createSecurityHeadersReport,
  verifyCSP,
  verifyPermissionsPolicy,
} from '../src/utils/securityHeaders'

const API_URL = process.env.VITE_API_URL || 'http://localhost:8000'
const ENVIRONMENT =
  (process.env.ENVIRONMENT as 'local' | 'staging' | 'production') || 'local'

// Color codes for terminal output
const COLORS = {
  reset: '\x1b[0m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  cyan: '\x1b[36m',
}

function colorize(text: string, color: keyof typeof COLORS): string {
  return `${COLORS[color]}${text}${COLORS.reset}`
}

async function verifySecurityConfiguration() {
  console.log(colorize('\n🔒 Security Headers Verification\n', 'cyan'))
  console.log(`API URL: ${colorize(API_URL, 'blue')}`)
  console.log(`Environment: ${colorize(ENVIRONMENT, 'blue')}\n`)

  let exitCode = 0

  try {
    // Test /health endpoint
    console.log(colorize('Testing /health endpoint...', 'cyan'))
    const healthResponse = await axios.get(`${API_URL}/health`, {
      validateStatus: () => true,
      timeout: 5000,
    })

    if (healthResponse.status !== 200) {
      console.error(
        colorize(`✗ Health check failed with status ${healthResponse.status}`, 'red')
      )
      exitCode = 1
    } else {
      console.log(colorize('✓ Health check passed', 'green'))
    }

    // Verify headers
    console.log(colorize('\nVerifying security headers...', 'cyan'))
    const verification = verifySecurityHeaders(healthResponse.headers, {
      environment: ENVIRONMENT,
      strict: ENVIRONMENT === 'production',
    })

    const report = formatSecurityHeadersReport(verification)
    console.log(report)

    if (!verification.valid) {
      console.error(colorize('\n✗ Security headers verification FAILED\n', 'red'))
      exitCode = 1
    } else if (verification.warnings.length > 0) {
      console.log(
        colorize(
          `\n⚠ Security headers verification passed with ${verification.warnings.length} warning(s)\n`,
          'yellow'
        )
      )
    } else {
      console.log(colorize('\n✓ Security headers verification PASSED\n', 'green'))
    }

    // Test /api/v1/health endpoint
    console.log(colorize('Testing /api/v1/health endpoint...', 'cyan'))
    const apiHealthResponse = await axios.get(`${API_URL}/api/v1/health`, {
      validateStatus: () => true,
      timeout: 5000,
    })

    if (apiHealthResponse.status !== 200) {
      console.error(
        colorize(
          `✗ API health check failed with status ${apiHealthResponse.status}`,
          'red'
        )
      )
      exitCode = 1
    } else {
      console.log(colorize('✓ API health check passed', 'green'))
    }

    const apiVerification = verifySecurityHeaders(apiHealthResponse.headers, {
      environment: ENVIRONMENT,
      strict: ENVIRONMENT === 'production',
    })

    if (!apiVerification.valid) {
      console.error(
        colorize('\n✗ API endpoint security headers verification FAILED\n', 'red')
      )
      exitCode = 1
    }

    // Verify CSP specifically
    console.log(colorize('\nVerifying Content-Security-Policy...', 'cyan'))
    const csp = healthResponse.headers['content-security-policy']
    if (!csp) {
      console.error(colorize('✗ CSP header missing', 'red'))
      exitCode = 1
    } else {
      const cspVerification = verifyCSP(csp)
      if (cspVerification.issues.length > 0) {
        console.log(colorize('CSP Issues:', 'yellow'))
        cspVerification.issues.forEach((issue) => {
          // Dangerous directives are warnings in dev, errors in prod
          if (issue.includes('unsafe') && ENVIRONMENT !== 'production') {
            console.log(colorize(`  ⚠ ${issue}`, 'yellow'))
          } else if (issue.includes('unsafe') && ENVIRONMENT === 'production') {
            console.error(colorize(`  ✗ ${issue}`, 'red'))
            exitCode = 1
          } else {
            console.error(colorize(`  ✗ ${issue}`, 'red'))
            exitCode = 1
          }
        })
      } else {
        console.log(colorize('✓ CSP validated', 'green'))
      }
    }

    // Verify Permissions-Policy specifically
    console.log(colorize('\nVerifying Permissions-Policy...', 'cyan'))
    const permissionsPolicy = healthResponse.headers['permissions-policy']
    if (!permissionsPolicy) {
      console.error(colorize('✗ Permissions-Policy header missing', 'red'))
      exitCode = 1
    } else {
      const permissionsVerification = verifyPermissionsPolicy(permissionsPolicy)
      if (permissionsVerification.issues.length > 0) {
        console.log(colorize('Permissions-Policy Issues:', 'red'))
        permissionsVerification.issues.forEach((issue) => {
          console.error(colorize(`  ✗ ${issue}`, 'red'))
        })
        exitCode = 1
      } else {
        console.log(colorize('✓ Permissions-Policy validated', 'green'))
      }
    }

    // Generate comprehensive report
    console.log(colorize('\n📊 Comprehensive Security Headers Report\n', 'cyan'))
    const comprehensiveReport = createSecurityHeadersReport(healthResponse.headers)

    // Print table
    console.log(
      colorize(
        '┌─────────────────────────────┬──────────┬─────────────────────────────┐',
        'blue'
      )
    )
    console.log(
      colorize(
        '│ Header                      │ Status   │ Notes                       │',
        'blue'
      )
    )
    console.log(
      colorize(
        '├─────────────────────────────┼──────────┼─────────────────────────────┤',
        'blue'
      )
    )

    comprehensiveReport.details.forEach((detail) => {
      const header = detail.header.padEnd(27)
      let status = detail.status.padEnd(8)
      const notes = (detail.notes || '').slice(0, 27).padEnd(27)

      // Colorize status
      if (detail.status === 'present') {
        status = colorize(status, 'green')
      } else if (detail.status === 'missing') {
        status = colorize(status, 'red')
      } else if (detail.status === 'invalid') {
        status = colorize(status, 'red')
      }

      console.log(`│ ${header} │ ${status} │ ${notes} │`)
    })

    console.log(
      colorize(
        '└─────────────────────────────┴──────────┴─────────────────────────────┘',
        'blue'
      )
    )

    // HIPAA Compliance Check
    console.log(colorize('\n🏥 HIPAA Compliance Check\n', 'cyan'))

    const hipaaChecks = [
      {
        requirement: '§164.312(a)(1) - Access Control',
        header: 'x-frame-options',
        expectedValue: 'DENY',
      },
      {
        requirement: '§164.312(e)(1) - Transmission Security',
        header: 'referrer-policy',
        expectedValue: 'strict-origin-when-cross-origin',
      },
      {
        requirement: '§164.308(a)(4) - Information Access Management',
        header: 'permissions-policy',
        expectedValue: 'microphone=()',
      },
      {
        requirement: '§164.312(b) - Audit Controls',
        header: 'x-request-id',
        expectedValue: null, // Just needs to be present
      },
    ]

    let hipaaCompliant = true

    hipaaChecks.forEach((check) => {
      const headerValue = healthResponse.headers[check.header]

      if (!headerValue) {
        console.error(
          colorize(`✗ ${check.requirement}: Missing ${check.header}`, 'red')
        )
        hipaaCompliant = false
        exitCode = 1
      } else if (check.expectedValue && !headerValue.includes(check.expectedValue)) {
        console.error(
          colorize(`✗ ${check.requirement}: Invalid ${check.header}`, 'red')
        )
        hipaaCompliant = false
        exitCode = 1
      } else {
        console.log(colorize(`✓ ${check.requirement}`, 'green'))
      }
    })

    if (hipaaCompliant) {
      console.log(colorize('\n✓ HIPAA compliance checks PASSED\n', 'green'))
    } else {
      console.error(colorize('\n✗ HIPAA compliance checks FAILED\n', 'red'))
    }
  } catch (error) {
    console.error(colorize('\n✗ Failed to connect to API\n', 'red'))

    if (axios.isAxiosError(error)) {
      if (error.code === 'ECONNREFUSED') {
        console.error(
          colorize(
            `Cannot connect to ${API_URL}. Ensure the backend is running.`,
            'red'
          )
        )
      } else if (error.code === 'ETIMEDOUT') {
        console.error(
          colorize(
            `Connection to ${API_URL} timed out. Check network connectivity.`,
            'red'
          )
        )
      } else {
        console.error(colorize(`Axios error: ${error.message}`, 'red'))
      }
    } else if (error instanceof Error) {
      console.error(colorize(`Error: ${error.message}`, 'red'))
    } else {
      console.error(colorize(`Unknown error: ${String(error)}`, 'red'))
    }

    exitCode = 1
  }

  // Exit with appropriate code
  if (exitCode === 0) {
    console.log(
      colorize('✅ Security headers verification completed successfully\n', 'green')
    )
  } else {
    console.error(colorize('❌ Security headers verification FAILED\n', 'red'))
  }

  process.exit(exitCode)
}

// Run verification
verifySecurityConfiguration()
