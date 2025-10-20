# Security Headers E2E Verification

**HIPAA Compliance**: §164.312(a)(1) - Technical safeguards verification

This document describes the security headers E2E testing infrastructure that ensures all security headers are properly configured and delivered through the entire stack.

## Overview

The security headers verification system ensures that critical HTTP security headers are:
1. **Present** in all responses
2. **Correctly configured** according to security best practices
3. **Not stripped** by reverse proxies or frontend dev servers
4. **Enforced** on all endpoints (public, authenticated, API, errors)

## Test Suite Components

### 1. E2E Integration Tests

**Location**: `/frontend/tests/integration/security-headers.spec.ts`

Comprehensive E2E tests that make real HTTP requests to the backend and verify all security headers:

- **X-Frame-Options**: Clickjacking protection (`DENY`)
- **X-Content-Type-Options**: MIME sniffing protection (`nosniff`)
- **Strict-Transport-Security**: HTTPS enforcement (1+ year max-age)
- **Content-Security-Policy**: XSS/injection protection
- **Referrer-Policy**: Privacy protection (`strict-origin-when-cross-origin`)
- **Permissions-Policy**: Feature restrictions (geolocation, camera, microphone)
- **X-Request-ID**: Request tracing (UUID format)
- **X-CSP-Nonce**: CSP nonce for inline scripts

**Test Coverage**:
- ✅ 14 test suites
- ✅ 60+ individual tests
- ✅ All critical security headers
- ✅ Multiple endpoint types
- ✅ Error responses (404, 401, 500)
- ✅ HIPAA compliance verification
- ✅ Attack mitigation verification

**Usage**:
```bash
# Run E2E tests (requires backend running)
npm run test:security

# Run with live backend
VITE_API_URL=http://localhost:8000 npm run test:security
```

### 2. Mock Tests (No Backend Required)

**Location**: `/frontend/tests/integration/security-headers-mock.spec.ts`

Lightweight tests using Mock Service Worker (MSW) that simulate backend responses without requiring a running backend.

**Benefits**:
- ✅ Fast execution (no network calls)
- ✅ Reliable (no backend dependencies)
- ✅ CI/CD friendly (no infrastructure required)
- ✅ Consistent (no timing issues)

**Usage**:
```bash
npm run test:run -- tests/integration/security-headers-mock.spec.ts
```

### 3. Security Headers Verification Utility

**Location**: `/frontend/src/utils/securityHeaders.ts`

Reusable TypeScript utility for programmatic header verification:

**Functions**:
- `verifySecurityHeaders()` - Verify all headers are present and correct
- `formatSecurityHeadersReport()` - Format verification results as human-readable report
- `verifyCSP()` - Verify Content-Security-Policy specifically
- `verifyPermissionsPolicy()` - Verify Permissions-Policy specifically
- `createSecurityHeadersReport()` - Generate comprehensive security report

**Example**:
```typescript
import { verifySecurityHeaders, formatSecurityHeadersReport } from '@/utils/securityHeaders'

const response = await fetch('/api/v1/health')
const verification = verifySecurityHeaders(response.headers)

console.log(formatSecurityHeadersReport(verification))
// ✓ All security headers present and valid
```

**Unit Tests**: `/frontend/src/utils/securityHeaders.spec.ts` (28 tests)

### 4. CI/CD Verification Script

**Location**: `/frontend/scripts/verify-security-headers.ts`

Automated CLI script for CI/CD pipelines that:
- ✅ Makes real HTTP requests to backend
- ✅ Verifies all security headers
- ✅ Validates CSP and Permissions-Policy specifically
- ✅ Generates HIPAA compliance report
- ✅ Fails build if headers missing or invalid
- ✅ Outputs color-coded terminal report

**Usage**:
```bash
# Local development
npm run verify:security-headers

# CI/CD with custom API URL
VITE_API_URL=https://api.pazpaz.com npm run verify:security-headers

# With environment flag
ENVIRONMENT=production VITE_API_URL=https://api.pazpaz.com npm run verify:security-headers
```

**Exit Codes**:
- `0` - All security headers present and valid
- `1` - Verification failed (missing/invalid headers)

**Example Output**:
```
🔒 Security Headers Verification

API URL: http://localhost:8000
Environment: local

Testing /health endpoint...
✓ Health check passed

Verifying security headers...
✓ All security headers present and valid

Verifying Content-Security-Policy...
✓ CSP validated

Verifying Permissions-Policy...
✓ Permissions-Policy validated

📊 Comprehensive Security Headers Report

┌─────────────────────────────┬──────────┬─────────────────────────────┐
│ Header                      │ Status   │ Notes                       │
├─────────────────────────────┼──────────┼─────────────────────────────┤
│ x-frame-options             │ present  │                             │
│ x-content-type-options      │ present  │                             │
│ x-xss-protection            │ present  │                             │
│ strict-transport-security   │ present  │                             │
│ content-security-policy     │ present  │                             │
│ referrer-policy             │ present  │                             │
│ permissions-policy          │ present  │                             │
│ x-request-id                │ present  │                             │
│ x-csp-nonce                 │ present  │                             │
└─────────────────────────────┴──────────┴─────────────────────────────┘

🏥 HIPAA Compliance Check

✓ §164.312(a)(1) - Access Control
✓ §164.312(e)(1) - Transmission Security
✓ §164.308(a)(4) - Information Access Management
✓ §164.312(b) - Audit Controls

✓ HIPAA compliance checks PASSED

✅ Security headers verification completed successfully
```

## Security Headers Reference

### Required Headers (All Environments)

| Header | Value | Purpose | HIPAA Relevance |
|--------|-------|---------|-----------------|
| `X-Frame-Options` | `DENY` | Prevents clickjacking attacks | §164.312(a)(1) - Access Control |
| `X-Content-Type-Options` | `nosniff` | Prevents MIME sniffing attacks | §164.308(a)(4) - Access Management |
| `X-XSS-Protection` | `1; mode=block` | XSS filter for legacy browsers | Defense-in-depth |
| `Content-Security-Policy` | Varies | XSS/injection protection | Protects PHI from exfiltration |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Prevents URL-based PHI leakage | §164.312(e)(1) - Transmission Security |
| `Permissions-Policy` | Restrictive | Disables dangerous browser APIs | §164.308(a)(4) - Information Access |
| `X-Request-ID` | UUID | Request tracing for audit logs | §164.312(b) - Audit Controls |
| `X-CSP-Nonce` | Random nonce | CSP nonce for inline scripts | XSS prevention |

### Environment-Specific Headers

| Header | Development | Production |
|--------|-------------|------------|
| `Strict-Transport-Security` | Omitted (localhost) | `max-age=31536000; includeSubDomains` |
| `Content-Security-Policy` | Permissive (allows `unsafe-inline` for HMR) | Strict (nonce-based, no unsafe directives) |

## CSP (Content-Security-Policy) Details

### Development CSP
```
default-src 'self';
script-src 'self' 'unsafe-inline' 'unsafe-eval' http://localhost:* ws://localhost:*;
style-src 'self' 'unsafe-inline';
img-src 'self' data: https: http://localhost:*;
font-src 'self' data:;
connect-src 'self' ws://localhost:* http://localhost:*;
frame-ancestors 'none';
base-uri 'self';
form-action 'self';
```

**Rationale**: Vite dev server requires `unsafe-inline` and `unsafe-eval` for Hot Module Replacement (HMR).

### Production CSP
```
default-src 'self';
script-src 'self' 'nonce-{NONCE}';
style-src 'self' 'nonce-{NONCE}';
img-src 'self' data: https:;
font-src 'self' data:;
connect-src 'self';
frame-ancestors 'none';
base-uri 'self';
form-action 'self';
upgrade-insecure-requests;
```

**Security**: No `unsafe-inline` or `unsafe-eval`. All inline scripts/styles must include the nonce attribute.

## Permissions-Policy Details

```
geolocation=(), microphone=(), camera=(), payment=(), usb=()
```

**Disabled Features**:
- `geolocation=()` - No location tracking (HIPAA privacy requirement)
- `microphone=()` - No audio recording (PHI protection)
- `camera=()` - No video recording (PHI protection)
- `payment=()` - Not needed for this application
- `usb=()` - No USB device access (security)

## HIPAA Compliance Mapping

| HIPAA Requirement | Security Header | Verification |
|-------------------|-----------------|--------------|
| §164.312(a)(1) - Access Control | `X-Frame-Options: DENY` | Prevents clickjacking attacks on PHI |
| §164.312(e)(1) - Transmission Security | `Referrer-Policy: strict-origin-when-cross-origin` | Prevents PHI in URLs from leaking to third parties |
| §164.308(a)(4) - Information Access Management | `Permissions-Policy: microphone=(), camera=()` | Prevents unauthorized recording of therapy sessions |
| §164.312(b) - Audit Controls | `X-Request-ID: {UUID}` | Request tracing for audit logs |
| §164.312(e)(2)(i) - Encryption and Decryption | `Strict-Transport-Security: max-age=31536000` | Forces HTTPS connections |

## CI/CD Integration

### GitHub Actions Workflow

The security headers verification script is designed to run in CI/CD pipelines:

**Example Workflow** (`.github/workflows/security-headers.yml`):

```yaml
name: Security Headers Verification

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  verify-security-headers:
    runs-on: ubuntu-latest

    services:
      backend:
        image: pazpaz-backend:latest
        ports:
          - 8000:8000

    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install dependencies
        run: |
          cd frontend
          npm ci

      - name: Wait for backend
        run: |
          timeout 30 bash -c 'until curl -f http://localhost:8000/health; do sleep 2; done'

      - name: Verify security headers
        run: |
          cd frontend
          npm run verify:security-headers

      - name: Run security headers tests
        run: |
          cd frontend
          npm run test:security
```

### Pre-Deployment Verification

Add to deployment scripts:

```bash
#!/bin/bash
# deploy.sh

echo "🔒 Verifying security headers before deployment..."

cd frontend
npm run verify:security-headers

if [ $? -ne 0 ]; then
  echo "❌ Security headers verification failed. Aborting deployment."
  exit 1
fi

echo "✅ Security headers verified. Proceeding with deployment..."
# ... rest of deployment script
```

## Troubleshooting

### Headers Missing in Development

**Problem**: Security headers not present when testing locally.

**Solution**:
1. Ensure backend is running: `uv run uvicorn pazpaz.main:app`
2. Check backend logs for startup errors
3. Verify middleware is loaded: Check `/backend/src/pazpaz/main.py`

### Headers Stripped by Reverse Proxy

**Problem**: Headers present in backend but missing in frontend.

**Solution**:
1. Check Nginx/Apache configuration
2. Ensure proxy doesn't strip security headers
3. Add `proxy_pass_header` directives if needed

**Nginx Example**:
```nginx
location /api/ {
    proxy_pass http://backend:8000;
    proxy_pass_header X-Frame-Options;
    proxy_pass_header X-Content-Type-Options;
    proxy_pass_header Strict-Transport-Security;
    # ... other headers
}
```

### HSTS Not Present in Development

**Expected Behavior**: HSTS is omitted on `localhost`, `127.0.0.1`, and `testserver`.

**Rationale**: HSTS forces HTTPS, which doesn't work on localhost HTTP.

### CSP Violations in Development

**Expected Behavior**: Development CSP allows `unsafe-inline` and `unsafe-eval` for Vite HMR.

**Production**: These directives are removed and replaced with nonce-based CSP.

## Best Practices

### 1. Always Run Tests Before Deployment
```bash
npm run test:security
npm run verify:security-headers
```

### 2. Monitor Headers in Production

Use browser dev tools or curl to verify headers:

```bash
curl -I https://api.pazpaz.com/health
```

Expected output:
```
HTTP/2 200
x-frame-options: DENY
x-content-type-options: nosniff
strict-transport-security: max-age=31536000; includeSubDomains
content-security-policy: default-src 'self'; ...
referrer-policy: strict-origin-when-cross-origin
permissions-policy: geolocation=(), microphone=(), camera=(), payment=(), usb=()
x-request-id: 123e4567-e89b-12d3-a456-426614174000
```

### 3. Update Tests When Adding New Headers

If you add new security headers:
1. Update `/frontend/src/utils/securityHeaders.ts` constants
2. Add tests to `/frontend/tests/integration/security-headers.spec.ts`
3. Update this documentation

### 4. Use Nonce in Production

Frontend must include CSP nonce in inline scripts:

```html
<script nonce="{{ csp_nonce }}">
  // Inline script
</script>
```

Get nonce from `X-CSP-Nonce` response header.

## Test Results

### Mock Tests (No Backend)
```
✓ tests/integration/security-headers-mock.spec.ts (14 tests) 26ms
  ✓ Basic Security Headers (3 tests)
  ✓ X-Request-ID Header (2 tests)
  ✓ CSP and Nonce (2 tests)
  ✓ HIPAA Compliance Headers (4 tests)
  ✓ Attack Mitigation (3 tests)

Test Files  1 passed (1)
     Tests  14 passed (14)
```

### Security Headers Utility Tests
```
✓ src/utils/securityHeaders.spec.ts (28 tests) 11ms
  ✓ verifySecurityHeaders (10 tests)
  ✓ formatSecurityHeadersReport (5 tests)
  ✓ verifyCSP (3 tests)
  ✓ verifyPermissionsPolicy (3 tests)
  ✓ createSecurityHeadersReport (4 tests)
  ✓ REQUIRED_SECURITY_HEADERS constant (1 test)

Test Files  1 passed (1)
     Tests  28 passed (28)
```

## Summary

The security headers E2E verification system provides:

✅ **Comprehensive Testing**: 40+ tests covering all security headers
✅ **CI/CD Integration**: Automated verification in deployment pipelines
✅ **HIPAA Compliance**: Explicit mapping to HIPAA requirements
✅ **Developer Experience**: Fast mock tests + detailed error reporting
✅ **Production Safety**: Fails deployment if headers misconfigured
✅ **Documentation**: Clear guidance on expected behavior

This ensures that security headers remain correctly configured throughout the application lifecycle and protect against common web vulnerabilities and HIPAA compliance violations.
