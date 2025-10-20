# Magic Link Token Handling - Security Requirements

## Overview

Magic link tokens are sensitive authentication credentials that MUST be handled securely to prevent leakage via browser history, server logs, or referrer headers.

**Vulnerability**: CWE-598 - Use of GET Request Method With Sensitive Query Strings

**Risk Level**: HIGH - Token leakage can lead to unauthorized account access

## Security Requirement

**CRITICAL**: The frontend MUST immediately remove magic link tokens from the URL after reading them.

## Backend Implementation (Completed)

### 1. POST-Based Token Verification

The `/api/v1/auth/verify` endpoint **only accepts POST requests** with token in request body:

```python
# ✅ SECURE: Token in POST body
POST /api/v1/auth/verify
Content-Type: application/json

{
  "token": "abc123...xyz789"
}

# ❌ INSECURE: Token in URL (method not allowed)
GET /api/v1/auth/verify?token=abc123...xyz789
# Returns: 405 Method Not Allowed
```

### 2. Rate Limiting

Rate limiting prevents brute force attacks on magic link tokens:

- **10 verification attempts per 5 minutes per IP address**
- Returns `429 Too Many Requests` after limit exceeded
- Fail-closed on Redis failure (security-critical)

```python
# Example rate limit response
HTTP/1.1 429 Too Many Requests
Content-Type: application/json

{
  "detail": "Too many verification attempts. Please try again later."
}
```

### 3. Referrer-Policy Header

Backend sets `Referrer-Policy: strict-origin-when-cross-origin` on all responses:

- **Same-origin navigation**: Full URL sent (including path)
- **Cross-origin HTTPS**: Only origin sent (`https://app.pazpaz.com`, no path)
- **HTTP downgrade**: No referrer sent

This prevents tokens from leaking via referrer headers when users navigate away.

### 4. Security Headers Summary

All responses include these security headers:

```http
Content-Security-Policy: script-src 'self' 'nonce-...'; ...
Referrer-Policy: strict-origin-when-cross-origin
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

## Frontend Implementation (Required)

### Verify Page Implementation

**File**: `frontend/src/views/auth/VerifyView.vue` (or similar)

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const loading = ref(true);
const error = ref<string | null>(null);

onMounted(async () => {
  // 1. Extract token from URL query parameter
  const urlParams = new URLSearchParams(window.location.search);
  const token = urlParams.get('token');

  if (!token) {
    error.value = 'Invalid magic link';
    loading.value = false;
    return;
  }

  // 2. CRITICAL: Immediately remove token from URL
  //    This prevents token from being logged or persisting in browser history
  //    MUST happen BEFORE any API call (in case API call fails)
  window.history.replaceState({}, document.title, '/auth/verify');

  // 3. Verify token via POST request (token in body, not URL)
  try {
    const response = await fetch('/api/v1/auth/verify', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include',  // Include cookies for session
      body: JSON.stringify({ token }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Verification failed');
    }

    // 4. Redirect to dashboard on success
    router.push('/dashboard');
  } catch (err) {
    error.value = err instanceof Error
      ? err.message
      : 'Invalid or expired magic link';
    loading.value = false;
  }
});
</script>

<template>
  <div class="verify-page">
    <div v-if="loading" class="loading">
      <div class="spinner" />
      <p>Verifying your login...</p>
    </div>
    <div v-else-if="error" class="error">
      <h2>Verification Failed</h2>
      <p>{{ error }}</p>
      <router-link to="/auth/login" class="btn-primary">
        Request New Login Link
      </router-link>
    </div>
  </div>
</template>

<style scoped>
.verify-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 2rem;
}

.loading, .error {
  text-align: center;
  max-width: 400px;
}

.spinner {
  border: 4px solid rgba(0, 0, 0, 0.1);
  border-top-color: #3b82f6;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 1s linear infinite;
  margin: 0 auto 1rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error h2 {
  color: #ef4444;
  margin-bottom: 0.5rem;
}

.error p {
  color: #6b7280;
  margin-bottom: 1.5rem;
}

.btn-primary {
  display: inline-block;
  padding: 0.75rem 1.5rem;
  background: #3b82f6;
  color: white;
  text-decoration: none;
  border-radius: 0.5rem;
  transition: background 0.2s;
}

.btn-primary:hover {
  background: #2563eb;
}
</style>
```

### Critical Security Steps

1. **Extract token from URL**: `urlParams.get('token')`
2. **Immediately remove from URL**: `window.history.replaceState({}, document.title, '/auth/verify')`
3. **Verify via POST**: Send token in request body, not URL
4. **Handle errors gracefully**: Show user-friendly error messages

### Router Configuration

**File**: `frontend/src/router/index.ts`

```typescript
import { createRouter, createWebHistory } from 'vue-router';
import VerifyView from '@/views/auth/VerifyView.vue';

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/auth/verify',
      name: 'verify',
      component: VerifyView,
      meta: {
        requiresAuth: false,
        title: 'Verify Login',
      },
    },
    // ... other routes
  ],
});

export default router;
```

## Security Properties

### ✅ What This Protects Against

1. **Browser History Leakage**: Token removed from URL before user navigates away
2. **Server Log Leakage**: Token sent in POST body, not logged in access logs
3. **Referrer Leakage**: Backend sets `Referrer-Policy: strict-origin-when-cross-origin`
4. **Shoulder Surfing**: Token not visible in URL bar after immediate removal
5. **Brute Force**: Rate limiting (10 attempts / 5 min per IP)

### ⚠️ What This Does NOT Protect Against

1. **Man-in-the-Middle (MITM)**: Use HTTPS in production (enforced by backend)
2. **Malware**: If user's machine is compromised, token can be stolen
3. **Email Compromise**: If attacker has email access, they can click magic link
4. **Phishing**: User may click malicious link disguised as magic link

## Testing

### Manual Testing Checklist

- [ ] **Test Token Removal**:
  - Click magic link from email
  - Check browser URL bar - should NOT contain `?token=...`
  - Open browser history - magic link should not appear with token

- [ ] **Test POST Verification**:
  - Open browser DevTools → Network tab
  - Click magic link
  - Verify `/api/v1/auth/verify` is POST request
  - Verify token is in request body, not URL

- [ ] **Test Rate Limiting**:
  - Make 10 failed verification attempts
  - 11th attempt should return `429 Too Many Requests`
  - Wait 5 minutes, should be able to retry

- [ ] **Test Referrer Policy**:
  - After successful login, navigate to external site
  - Check request headers in DevTools
  - Referrer should be `https://app.pazpaz.com` (no path)

- [ ] **Test Error Handling**:
  - Try expired token → should show error
  - Try invalid token → should show error
  - Try without token → should show error

### Automated Testing

Backend tests validate:
- Rate limiting (10 attempts / 5 min per IP)
- POST-only verification (GET returns 405)
- Token in body validation (missing token returns 422)
- Referrer-Policy header present on all responses

See: `/Users/yussieik/Desktop/projects/pazpaz/backend/tests/security/test_magic_link_security.py`

## Alternative: POST-Based Magic Links (Future Enhancement)

Instead of sending a URL with token in query parameter, email could contain a form:

```html
<!-- Email body -->
<form method="POST" action="https://app.pazpaz.com/auth/verify" id="magic-form">
  <input type="hidden" name="token" value="{token}">
  <button type="submit">Click to Login</button>
</form>
<script>
  // Auto-submit on load (optional)
  document.getElementById('magic-form').submit();
</script>
```

**Benefits**:
- Token never in URL
- No browser history leakage
- No server log leakage

**Drawbacks**:
- More complex email template
- Requires JavaScript (degrades gracefully)
- Some email clients may block auto-submit
- CSRF token required for form submission

**Recommendation**: Implement current solution first (token in URL, immediately removed). Consider POST-based magic links as future enhancement if needed.

## Deployment Checklist

Before deploying to production:

- [ ] Frontend removes token from URL via `window.history.replaceState()`
- [ ] Backend verify endpoint uses POST (not GET)
- [ ] Backend rate limits verify endpoint (10 attempts / 5 min)
- [ ] Backend sets `Referrer-Policy: strict-origin-when-cross-origin`
- [ ] HTTPS enforced in production (no HTTP)
- [ ] Manual testing completed (all items above)
- [ ] Automated tests passing (backend rate limiting, POST-only)

## Monitoring and Alerts

### Metrics to Monitor

1. **Rate Limit Hits**: Track `magic_link_verify_rate_limit_exceeded` log events
   - High rate may indicate brute force attack
   - Set alert threshold: >10 rate limit hits per hour

2. **Failed Verifications**: Track `magic_link_verification_failed` log events
   - High rate may indicate token expiry issues or attacks
   - Set alert threshold: >5% failure rate

3. **Verification Latency**: Track p95/p99 latency for `/api/v1/auth/verify`
   - Should be <150ms (PazPaz target)
   - Alert if p95 >200ms

### Example Log Queries

```bash
# Rate limit events
grep "magic_link_verify_rate_limit_exceeded" /var/log/pazpaz/api.log

# Failed verifications
grep "magic_link_verification_failed" /var/log/pazpaz/api.log

# Successful verifications
grep "user_authenticated" /var/log/pazpaz/api.log
```

## References

- **CWE-598**: [Use of GET Request Method With Sensitive Query Strings](https://cwe.mitre.org/data/definitions/598.html)
- **OWASP**: [Sensitive Data Exposure](https://owasp.org/www-project-top-ten/2017/A3_2017-Sensitive_Data_Exposure)
- **Referrer-Policy**: [MDN Web Docs](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Referrer-Policy)

## Security Audit History

| Date | Auditor | Findings | Status |
|------|---------|----------|--------|
| 2025-10-20 | Initial Security Audit | CWE-598: Token in URL | **FIXED** - Backend enhanced, frontend docs created |

## Contact

For security concerns or questions, contact:
- **Security Team**: security@pazpaz.app
- **Backend Lead**: backend@pazpaz.app
