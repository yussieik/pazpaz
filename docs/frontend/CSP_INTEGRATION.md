# CSP Integration - Frontend

**Last Updated:** 2025-10-19
**Status:** ✅ Implemented
**Security Task:** Task 4.1 - Tighten CSP (Nonce-Based) for Production

---

## Overview

This document describes the frontend integration with the backend's nonce-based Content Security Policy (CSP) implementation. The CSP prevents XSS attacks by blocking inline scripts and styles unless they include a cryptographically secure nonce.

**Key Points:**
- ✅ **Production:** Strict CSP with nonce-based script/style execution
- ✅ **Development:** Permissive CSP to support Vite HMR (Hot Module Replacement)
- ✅ **Build:** Vite 5+ generates CSP-compliant production builds by default
- ✅ **Utilities:** Helper functions available for dynamic script/style injection

---

## Architecture

### Backend Responsibilities

1. **Generate Nonce** (per request):
   ```python
   # backend/src/pazpaz/main.py - SecurityHeadersMiddleware
   nonce = secrets.token_urlsafe(32)  # 256-bit entropy
   request.state.csp_nonce = nonce
   ```

2. **Set CSP Header** (production):
   ```http
   Content-Security-Policy:
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

3. **Return Nonce to Frontend**:
   ```http
   X-CSP-Nonce: AbC123-_XyZ789AbC123-_XyZ789AbC123-_
   ```

4. **Inject Nonce into HTML** (Server-Side Rendering):
   ```html
   <meta name="csp-nonce" content="AbC123-_XyZ789AbC123-_XyZ789AbC123-_">
   ```

### Frontend Responsibilities

1. **Extract Nonce** from meta tag:
   ```typescript
   import { getCspNonce } from '@/utils/csp'
   const nonce = getCspNonce()  // Reads from <meta name="csp-nonce">
   ```

2. **Apply Nonce** to dynamic scripts/styles:
   ```typescript
   import { applyNonceToScript } from '@/utils/csp'

   const script = document.createElement('script')
   script.src = '/dynamic-library.js'
   applyNonceToScript(script)  // Adds nonce if available
   document.head.appendChild(script)
   ```

---

## Production vs Development

### Production Mode

**Environment:**
- `DEBUG=false` or `ENVIRONMENT=production`
- Backend serves built frontend from `dist/`

**CSP Policy:**
```
script-src 'self' 'nonce-{NONCE}'  (NO unsafe-inline, NO unsafe-eval)
style-src 'self' 'nonce-{NONCE}'   (NO unsafe-inline)
```

**Behavior:**
- ✅ External scripts load normally (`<script src="/assets/index.js">`)
- ✅ Inline scripts with correct nonce execute (`<script nonce="{NONCE}">`)
- ❌ Inline scripts without nonce are **BLOCKED**
- ❌ `eval()` is **BLOCKED**
- ❌ `new Function()` is **BLOCKED**

### Development Mode

**Environment:**
- `DEBUG=true` or `ENVIRONMENT=local`
- Vite dev server at `http://localhost:5173`

**CSP Policy:**
```
script-src 'self' 'unsafe-inline' 'unsafe-eval' http://localhost:* ws://localhost:*
style-src 'self' 'unsafe-inline'
```

**Behavior:**
- ✅ Vite HMR works (requires `unsafe-eval`)
- ✅ All inline scripts execute (for development convenience)
- ✅ `getCspNonce()` returns `null` (nonce not required)
- ⚠️ **NOT SECURE** - Only use in development

---

## Usage Guide

### Basic Usage

#### 1. Extract Nonce

```typescript
import { getCspNonce } from '@/utils/csp'

// Get nonce (null in development, string in production)
const nonce = getCspNonce()

if (nonce) {
  console.log('Production mode - nonce available:', nonce)
} else {
  console.log('Development mode - nonce not required')
}
```

#### 2. Check if Nonce is Available

```typescript
import { hasCspNonce } from '@/utils/csp'

if (hasCspNonce()) {
  console.log('Running in production with strict CSP')
} else {
  console.log('Running in development mode')
}
```

#### 3. Apply Nonce to Dynamic Script

```typescript
import { applyNonceToScript } from '@/utils/csp'

// Load external JavaScript library
const script = document.createElement('script')
script.src = 'https://cdn.example.com/library.js'
script.async = true
script.onload = () => console.log('Library loaded')
script.onerror = () => console.error('Failed to load library')

// Apply nonce (automatically handles production vs development)
applyNonceToScript(script)

// Add to document
document.head.appendChild(script)
```

#### 4. Apply Nonce to Dynamic Style

```typescript
import { applyNonceToStyle } from '@/utils/csp'

// Inject critical CSS
const style = document.createElement('style')
style.textContent = `
  .critical-banner {
    position: fixed;
    top: 0;
    width: 100%;
    background: red;
    color: white;
    padding: 10px;
    text-align: center;
  }
`

// Apply nonce
applyNonceToStyle(style)

// Add to document
document.head.appendChild(style)
```

---

## Advanced Patterns

### Pattern 1: Conditional Script Loading

```typescript
import { getCspNonce } from '@/utils/csp'

function loadAnalytics() {
  const script = document.createElement('script')
  script.src = 'https://analytics.example.com/tracker.js'
  script.async = true

  // Apply nonce if available
  const nonce = getCspNonce()
  if (nonce) {
    script.nonce = nonce
  }

  // Error handling for CSP violations
  script.onerror = (error) => {
    console.error('Failed to load analytics (CSP violation?)', error)
  }

  document.head.appendChild(script)
}

// Only load in production
if (import.meta.env.PROD) {
  loadAnalytics()
}
```

### Pattern 2: Third-Party Library Integration

```typescript
import { applyNonceToScript } from '@/utils/csp'

// Load third-party library with CSP support
async function loadThirdPartyLibrary(url: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = url
    script.async = true

    script.onload = () => resolve()
    script.onerror = () => reject(new Error(`Failed to load ${url}`))

    // Ensure CSP compliance
    applyNonceToScript(script)

    document.head.appendChild(script)
  })
}

// Usage
try {
  await loadThirdPartyLibrary('https://cdn.example.com/library.js')
  console.log('Library loaded successfully')
} catch (error) {
  console.error('Library loading failed:', error)
}
```

### Pattern 3: Dynamic Inline Script (Avoid if Possible)

```typescript
import { getCspNonce } from '@/utils/csp'

// ⚠️ WARNING: Avoid inline scripts in production
// This pattern should only be used if absolutely necessary

function injectInlineScript(code: string) {
  const script = document.createElement('script')

  // Apply nonce for CSP compliance
  const nonce = getCspNonce()
  if (nonce) {
    script.nonce = nonce
  }

  // Set script content
  script.textContent = code

  document.head.appendChild(script)

  // Clean up immediately (optional)
  script.remove()
}

// Better alternative: Use external scripts or module imports
```

### Pattern 4: Composable for Vue Components

```typescript
// composables/useThirdPartyScript.ts
import { ref, onMounted } from 'vue'
import { applyNonceToScript } from '@/utils/csp'

export function useThirdPartyScript(url: string) {
  const isLoaded = ref(false)
  const error = ref<Error | null>(null)

  onMounted(() => {
    const script = document.createElement('script')
    script.src = url
    script.async = true

    script.onload = () => {
      isLoaded.value = true
    }

    script.onerror = () => {
      error.value = new Error(`Failed to load ${url}`)
    }

    // CSP-compliant injection
    applyNonceToScript(script)
    document.head.appendChild(script)
  })

  return { isLoaded, error }
}
```

**Usage in Component:**
```vue
<script setup lang="ts">
import { useThirdPartyScript } from '@/composables/useThirdPartyScript'

const { isLoaded, error } = useThirdPartyScript('https://example.com/library.js')
</script>

<template>
  <div v-if="isLoaded">Library loaded!</div>
  <div v-else-if="error">Error: {{ error.message }}</div>
  <div v-else>Loading...</div>
</template>
```

---

## CSP Violation Debugging

### Common CSP Violations

#### 1. Inline Script Without Nonce

**Error:**
```
Refused to execute inline script because it violates the following
Content Security Policy directive: "script-src 'self' 'nonce-...'".
Either the 'unsafe-inline' keyword, a hash ('sha256-...'), or a nonce ('nonce-...') is required to enable inline execution.
```

**Solution:**
```typescript
// ❌ BAD: Inline script without nonce
const script = document.createElement('script')
script.textContent = 'console.log("test")'
document.head.appendChild(script)  // CSP violation!

// ✅ GOOD: Apply nonce to inline script
import { applyNonceToScript } from '@/utils/csp'
const script = document.createElement('script')
script.textContent = 'console.log("test")'
applyNonceToScript(script)
document.head.appendChild(script)
```

#### 2. eval() Usage

**Error:**
```
Refused to evaluate a string as JavaScript because 'unsafe-eval' is not
an allowed source of script in the following Content Security Policy directive: "script-src 'self' 'nonce-...'".
```

**Solution:**
```typescript
// ❌ BAD: eval() is blocked by CSP
eval('console.log("test")')  // CSP violation!

// ✅ GOOD: Refactor to avoid eval()
const code = () => console.log("test")
code()
```

#### 3. Third-Party Library Without Nonce

**Error:**
```
Refused to load the script 'https://cdn.example.com/library.js' because it
violates the following Content Security Policy directive: "script-src 'self' 'nonce-...'".
```

**Wait, this shouldn't happen!** External scripts from HTTPS sources are allowed by `script-src 'self'` if served from same origin. If the script is from a third-party domain, you need to:

1. **Option A:** Add the domain to CSP (backend change):
   ```
   script-src 'self' https://cdn.example.com 'nonce-{NONCE}'
   ```

2. **Option B:** Self-host the library (recommended):
   ```bash
   npm install library-name
   ```

   ```typescript
   import { library } from 'library-name'
   ```

---

## Testing CSP Integration

### Unit Tests

Run CSP utility tests:
```bash
cd frontend
npm run test:run -- src/utils/csp.spec.ts
```

**Expected Output:**
```
✓ getCspNonce (7 tests)
✓ resetCspNonceCache (2 tests)
✓ hasCspNonce (2 tests)
✓ applyNonceToScript (3 tests)
✓ applyNonceToStyle (3 tests)
✓ CSP Integration Scenarios (3 tests)

Total: 20 tests passed
```

### Manual Testing (Production Build)

1. **Build Production Assets:**
   ```bash
   npm run build
   ```

2. **Start Preview Server:**
   ```bash
   npm run preview
   ```

3. **Open Test Page:**
   ```
   http://localhost:4173/test-csp.html
   ```

4. **Open Browser DevTools:**
   - **Console:** Should show 1 CSP violation (inline script without nonce)
   - **Network:** All scripts load successfully
   - **Visual:** Green "CSP TEST PASSED" banner appears

### Integration Testing (With Backend)

1. **Start Backend (Production Mode):**
   ```bash
   cd backend
   ENVIRONMENT=production DEBUG=false uv run uvicorn pazpaz.main:app
   ```

2. **Verify CSP Headers:**
   ```bash
   curl -I http://localhost:8000/
   ```

   **Expected Headers:**
   ```http
   Content-Security-Policy: script-src 'self' 'nonce-AbC123...'
   X-CSP-Nonce: AbC123-_XyZ789AbC123-_XyZ789AbC123-_
   ```

3. **Verify Frontend Extraction:**
   - Open browser DevTools Console
   - Run:
     ```javascript
     import { getCspNonce } from '/assets/index-CPKsce4T.js'
     console.log(getCspNonce())  // Should print nonce
     ```

---

## Files Reference

### Core Files

- **`/frontend/src/utils/csp.ts`** (195 lines)
  - CSP utility functions
  - Nonce extraction and caching
  - Helper functions for script/style injection

- **`/frontend/src/utils/csp.spec.ts`** (374 lines)
  - Comprehensive test suite
  - 20 tests covering all CSP utilities

- **`/frontend/index.html`** (27 lines)
  - Meta tag for nonce injection: `<meta name="csp-nonce" content="">`
  - Backend injects nonce into this tag in production

- **`/frontend/vite.config.ts`** (63 lines)
  - CSP-compatible build configuration
  - Manual chunks for optimal caching
  - Hidden sourcemaps for production debugging

### Documentation

- **`/frontend/CSP_PRODUCTION_BUILD_VERIFICATION.md`**
  - Comprehensive verification report
  - Build analysis and test results

- **`/docs/frontend/CSP_INTEGRATION.md`** (this file)
  - Integration guide and usage patterns

### Backend Reference

- **`/backend/src/pazpaz/main.py`** (lines 141-249)
  - `SecurityHeadersMiddleware`: Generates nonce and sets CSP headers

- **`/backend/tests/test_middleware/test_csp_nonce.py`**
  - Backend CSP tests (482 lines)

---

## API Reference

### getCspNonce()

Extract the CSP nonce from the meta tag.

```typescript
function getCspNonce(): string | null
```

**Returns:**
- `string`: Nonce value (production mode)
- `null`: No nonce available (development mode)

**Example:**
```typescript
const nonce = getCspNonce()
if (nonce) {
  console.log('Nonce:', nonce)
}
```

---

### hasCspNonce()

Check if CSP nonce is available.

```typescript
function hasCspNonce(): boolean
```

**Returns:**
- `true`: Nonce is available (production mode)
- `false`: Nonce not available (development mode)

**Example:**
```typescript
if (hasCspNonce()) {
  console.log('Production mode')
} else {
  console.log('Development mode')
}
```

---

### applyNonceToScript()

Apply CSP nonce to a script element.

```typescript
function applyNonceToScript(script: HTMLScriptElement): HTMLScriptElement
```

**Parameters:**
- `script`: Script element to apply nonce to

**Returns:**
- Modified script element (for chaining)

**Example:**
```typescript
const script = document.createElement('script')
script.src = '/library.js'
applyNonceToScript(script)
document.head.appendChild(script)
```

---

### applyNonceToStyle()

Apply CSP nonce to a style element.

```typescript
function applyNonceToStyle(style: HTMLStyleElement): HTMLStyleElement
```

**Parameters:**
- `style`: Style element to apply nonce to

**Returns:**
- Modified style element (for chaining)

**Example:**
```typescript
const style = document.createElement('style')
style.textContent = '.test { color: red; }'
applyNonceToStyle(style)
document.head.appendChild(style)
```

---

### resetCspNonceCache() [Internal]

Reset cached nonce (testing only).

```typescript
function resetCspNonceCache(): void
```

**⚠️ WARNING:** Only use in tests. Do not call in production code.

**Example:**
```typescript
// In test file
import { resetCspNonceCache } from '@/utils/csp'

afterEach(() => {
  resetCspNonceCache()
})
```

---

## Security Best Practices

### DO ✅

1. **Use External Scripts:**
   ```html
   <!-- External scripts are CSP-compliant -->
   <script src="/assets/app.js"></script>
   ```

2. **Apply Nonce to Dynamic Scripts:**
   ```typescript
   import { applyNonceToScript } from '@/utils/csp'
   const script = document.createElement('script')
   applyNonceToScript(script)
   ```

3. **Self-Host Third-Party Libraries:**
   ```typescript
   // Install and import (bundled by Vite)
   import library from 'library-name'
   ```

4. **Test Production Build:**
   ```bash
   npm run build && npm run preview
   ```

### DON'T ❌

1. **Inline Scripts Without Nonce:**
   ```html
   <!-- ❌ Will be BLOCKED by CSP -->
   <script>console.log('test')</script>
   ```

2. **Use eval() or new Function():**
   ```typescript
   // ❌ Blocked by CSP
   eval('console.log("test")')
   new Function('return 42')()
   ```

3. **Load External Scripts from Arbitrary Domains:**
   ```typescript
   // ❌ Requires CSP policy update
   script.src = 'https://random-cdn.com/script.js'
   ```

4. **Bypass CSP with unsafe-inline:**
   ```typescript
   // ❌ NEVER add 'unsafe-inline' in production
   // This defeats the entire purpose of CSP
   ```

---

## Troubleshooting

### Issue: "getCspNonce() returns null in production"

**Cause:** Backend is not injecting nonce into meta tag.

**Solution:**
1. Verify backend is running in production mode (`ENVIRONMENT=production`)
2. Check backend serves `dist/index.html` as template (not static file)
3. Verify `SecurityHeadersMiddleware` is enabled
4. Check `X-CSP-Nonce` header in response

---

### Issue: "CSP violation: Refused to execute inline script"

**Cause:** Inline script without nonce attribute.

**Solution:**
```typescript
// Add nonce to inline script
import { applyNonceToScript } from '@/utils/csp'
const script = document.createElement('script')
script.textContent = 'console.log("test")'
applyNonceToScript(script)
document.head.appendChild(script)
```

**Better Solution:**
```typescript
// Avoid inline scripts - use external files or modules
import { myFunction } from './module.js'
myFunction()
```

---

### Issue: "Third-party library fails to load"

**Cause:** Library injects inline scripts or uses eval().

**Solution:**
1. **Option A:** Self-host the library (recommended)
   ```bash
   npm install library-name
   import library from 'library-name'
   ```

2. **Option B:** Update CSP policy (backend change)
   ```python
   # Add library's CDN to script-src
   # NOT RECOMMENDED: increases attack surface
   ```

3. **Option C:** Find CSP-compatible alternative
   ```bash
   # Research CSP-friendly alternatives
   ```

---

## Migration Guide

If you're adding CSP to existing code that dynamically creates scripts:

### Before (No CSP)

```typescript
// Old code without CSP consideration
const script = document.createElement('script')
script.src = 'https://example.com/library.js'
document.head.appendChild(script)
```

### After (CSP-Compliant)

```typescript
// New code with CSP support
import { applyNonceToScript } from '@/utils/csp'

const script = document.createElement('script')
script.src = 'https://example.com/library.js'
applyNonceToScript(script)  // Add this line
document.head.appendChild(script)
```

**That's it!** The `applyNonceToScript()` function handles production vs development automatically.

---

## Further Reading

- **Backend CSP Implementation:** `/backend/src/pazpaz/main.py` (SecurityHeadersMiddleware)
- **Backend CSP Tests:** `/backend/tests/test_middleware/test_csp_nonce.py`
- **MDN CSP Guide:** https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP
- **OWASP CSP Cheat Sheet:** https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html
- **Vite CSP Compatibility:** https://vitejs.dev/guide/features.html#content-security-policy-csp

---

**Document Maintained By:** fullstack-frontend-specialist
**Last Review:** 2025-10-19
**Next Review:** When CSP policy changes or new frontend patterns emerge
